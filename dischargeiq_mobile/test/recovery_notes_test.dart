/// Black-box tests for recovery annotations.
///
/// The property under test throughout is ATTRIBUTION: after any sequence of
/// operations, text on the recovery screen is either the hospital's, or is
/// marked as changed and still carries what it replaced. There is no third
/// state, and a bug that produced one would put the patient's own guess on
/// screen in the hospital's voice.
///
/// Written against the public surface only - construct, store, read back -
/// so a rewrite of the storage format cannot quietly pass these.

library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/recovery_notes.dart';

RecoveryEdit _edit({
  RecoveryEditKind kind = RecoveryEditKind.patientEdit,
  String phase = 'Week 1-2',
  String text = 'Walk 20 minutes twice a day',
  int? bulletIndex = 0,
  String? original = 'Walk 10 minutes twice a day',
  String? author,
  DateTime? createdAt,
}) =>
    RecoveryEdit(
      kind: kind,
      phase: phase,
      text: text,
      bulletIndex: bulletIndex,
      original: original,
      author: author,
      createdAt: createdAt,
    );

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('an override must be attributable', () {
    test('a patient edit keeps what it replaced', () {
      expect(_edit().isValid, isTrue);
      expect(_edit().original, 'Walk 10 minutes twice a day');
    });

    test('an override with no original is rejected', () {
      // This is the dangerous shape: replacement text with nothing to
      // compare it against reads exactly like the document's own wording.
      expect(_edit(original: null).isValid, isFalse);
    });

    test('an override with no bullet index is rejected', () {
      // Without an index it cannot be attached to a line, so it would render
      // as an unanchored instruction.
      expect(_edit(bulletIndex: null).isValid, isFalse);
    });

    test('a correction with no author is rejected', () {
      expect(
        _edit(kind: RecoveryEditKind.correction).isValid,
        isFalse,
        reason: 'a clinical correction that names nobody carries no authority',
      );
    });

    test('a correction with a whitespace-only author is rejected', () {
      expect(
        _edit(kind: RecoveryEditKind.correction, author: '   ').isValid,
        isFalse,
      );
    });

    test('a correction naming someone is accepted', () {
      expect(
        _edit(kind: RecoveryEditKind.correction, author: 'Nurse J. Patel')
            .isValid,
        isTrue,
      );
    });

    test('a note needs neither original nor index', () {
      // Notes are additive - they replace nothing, so there is nothing to
      // attribute beyond the patient.
      expect(
        _edit(
          kind: RecoveryEditKind.note,
          text: 'Physio said no stairs until Friday',
          bulletIndex: null,
          original: null,
        ).isValid,
        isTrue,
      );
    });

    test('empty text is never valid, whatever the kind', () {
      for (final kind in RecoveryEditKind.values) {
        expect(_edit(kind: kind, text: '  ', author: 'RN X').isValid, isFalse);
      }
    });
  });

  group('every kind says who changed it', () {
    test('the label names the patient or the clinician', () {
      expect(_edit(kind: RecoveryEditKind.note).attribution, 'Your note');
      expect(_edit().attribution, 'You changed this');
      expect(
        _edit(kind: RecoveryEditKind.correction, author: 'Nurse J. Patel')
            .attribution,
        contains('Nurse J. Patel'),
      );
    });

    test('no attribution label is ever empty', () {
      for (final kind in RecoveryEditKind.values) {
        expect(_edit(kind: kind, author: 'RN X').attribution, isNotEmpty);
      }
    });
  });

  group('storage refuses what it cannot attribute', () {
    test('an invalid override is not persisted', () async {
      await RecoveryNotesStore.add('doc1', _edit(original: null));
      final loaded = await RecoveryNotesStore.load('doc1');
      expect(loaded.all, isEmpty);
    });

    test('an unsaved run (no document id) stores nothing and does not throw',
        () async {
      final result = await RecoveryNotesStore.add('', _edit());
      expect(result.all, isEmpty);
    });

    test('a valid override survives a round trip with its original', () async {
      await RecoveryNotesStore.add('doc1', _edit());
      final loaded = await RecoveryNotesStore.load('doc1');
      expect(loaded.all, hasLength(1));
      expect(loaded.all.first.original, 'Walk 10 minutes twice a day');
      expect(loaded.all.first.text, 'Walk 20 minutes twice a day');
    });

    test('a corrupt stored blob degrades to empty, not a crash', () async {
      SharedPreferences.setMockInitialValues(
          {'recovery_edits_doc1': 'not json at all'});
      expect((await RecoveryNotesStore.load('doc1')).all, isEmpty);
    });

    test('a stored row missing its original is dropped on read', () async {
      // Simulates a row written by an older build with weaker validation.
      SharedPreferences.setMockInitialValues({
        'recovery_edits_doc1':
            '[{"kind":"patientEdit","phase":"Week 1","text":"x",'
                '"bulletIndex":0,"createdAt":"2026-09-01T00:00:00.000"}]',
      });
      expect(
        (await RecoveryNotesStore.load('doc1')).all,
        isEmpty,
        reason: 'unattributable text must not reach the screen',
      );
    });

    test('one bad row does not discard the good rows beside it', () async {
      SharedPreferences.setMockInitialValues({
        'recovery_edits_doc1': '['
            '{"kind":"nonsense","phase":"Week 1","text":"x"},'
            '{"kind":"note","phase":"Week 1","text":"real note",'
            '"createdAt":"2026-09-01T00:00:00.000"}'
            ']',
      });
      final loaded = await RecoveryNotesStore.load('doc1');
      expect(loaded.all, hasLength(1));
      expect(loaded.all.first.text, 'real note');
    });
  });

  group('which override is in force', () {
    test('the document stands when nothing overrides the line', () async {
      final edits = await RecoveryNotesStore.load('doc1');
      expect(edits.overrideFor('Week 1-2', 0), isNull);
    });

    test('a clinician correcting after a patient edit wins', () async {
      await RecoveryNotesStore.add(
          'doc1', _edit(createdAt: DateTime(2026, 9, 1)));
      final edits = await RecoveryNotesStore.add(
        'doc1',
        _edit(
          kind: RecoveryEditKind.correction,
          text: 'Walk 5 minutes twice a day',
          author: 'Nurse J. Patel',
          createdAt: DateTime(2026, 9, 3),
        ),
      );
      final winner = edits.overrideFor('Week 1-2', 0);
      expect(winner?.kind, RecoveryEditKind.correction);
      expect(winner?.text, 'Walk 5 minutes twice a day');
    });

    test('an override applies only to its own line', () async {
      final edits = await RecoveryNotesStore.add('doc1', _edit(bulletIndex: 0));
      expect(edits.overrideFor('Week 1-2', 1), isNull);
    });

    test('an override applies only to its own phase', () async {
      // Phases are matched by title because a re-run of Agent 4 can return a
      // different number of them; an index would land on the wrong week.
      final edits = await RecoveryNotesStore.add('doc1', _edit());
      expect(edits.overrideFor('Week 3-4', 0), isNull);
    });

    test('a note never overrides a line', () async {
      final edits = await RecoveryNotesStore.add(
        'doc1',
        _edit(
          kind: RecoveryEditKind.note,
          text: 'ask about physio',
          bulletIndex: null,
          original: null,
        ),
      );
      expect(
        edits.overrideFor('Week 1-2', 0),
        isNull,
        reason: 'notes sit beside the instructions, never replace them',
      );
    });
  });

  group('undo restores the hospital wording', () {
    test('removing the override leaves the line unmodified', () async {
      final added = await RecoveryNotesStore.add('doc1', _edit());
      final override = added.overrideFor('Week 1-2', 0)!;
      final after = await RecoveryNotesStore.remove('doc1', override);
      expect(after.overrideFor('Week 1-2', 0), isNull);
    });

    test('removing one override leaves the others alone', () async {
      await RecoveryNotesStore.add('doc1', _edit(bulletIndex: 0));
      final added =
          await RecoveryNotesStore.add('doc1', _edit(bulletIndex: 1));
      final first = added.overrideFor('Week 1-2', 0)!;
      final after = await RecoveryNotesStore.remove('doc1', first);
      expect(after.overrideFor('Week 1-2', 0), isNull);
      expect(after.overrideFor('Week 1-2', 1), isNotNull);
    });
  });

  group('notes belong to their phase', () {
    test('notes are returned oldest first', () async {
      await RecoveryNotesStore.add(
        'doc1',
        _edit(
          kind: RecoveryEditKind.note,
          text: 'second',
          bulletIndex: null,
          original: null,
          createdAt: DateTime(2026, 9, 5),
        ),
      );
      final edits = await RecoveryNotesStore.add(
        'doc1',
        _edit(
          kind: RecoveryEditKind.note,
          text: 'first',
          bulletIndex: null,
          original: null,
          createdAt: DateTime(2026, 9, 1),
        ),
      );
      expect(
        edits.notesFor('Week 1-2').map((e) => e.text).toList(),
        ['first', 'second'],
      );
    });

    test('a note on one phase does not appear on another', () async {
      final edits = await RecoveryNotesStore.add(
        'doc1',
        _edit(
          kind: RecoveryEditKind.note,
          text: 'week one only',
          bulletIndex: null,
          original: null,
        ),
      );
      expect(edits.notesFor('Week 3-4'), isEmpty);
    });
  });

  group('documents are isolated from each other', () {
    test('an edit on one document does not leak into another', () async {
      await RecoveryNotesStore.add('doc1', _edit());
      expect((await RecoveryNotesStore.load('doc2')).all, isEmpty);
    });
  });
}
