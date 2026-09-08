/// Black-box tests for appointment corrections.
///
/// The property under test is IDENTITY STABILITY. appointmentKey is built
/// from provider, specialty and date, and the done-tick in
/// AppointmentStatusStore is keyed the same way. Date is also the field most
/// likely to be corrected - a reschedule is the main reason to edit at all.
///
/// So if an edit were keyed by its own new values, saving a date change would
/// move the key, orphan the edit, and silently detach the tick. The patient
/// would tick off a visit and watch the tick vanish, or worse, see it land on
/// an appointment they had not attended.
///
/// Every test here exists to hold that line.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/appointment_edits.dart';
import 'package:dischargeiq_mobile/services/appointment_status.dart';

Map _appt({
  String provider = 'Dr. Chen',
  String specialty = 'Cardiology',
  String date = '2026-09-20',
  String reason = 'Heart check',
}) =>
    {
      'provider': provider,
      'specialty': specialty,
      'date': date,
      'reason': reason,
    };

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('an edit stays attached to the appointment it edits', () {
    test('changing the date does not move the key', () async {
      final original = _appt();
      final key = appointmentKey(original);
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2026-09-27'},
      );
      expect(edits[key], isNotNull,
          reason: 'the edit must still be found under the ORIGINAL key');
      expect(edits[key]!.changes['date'], '2026-09-27');
    });

    test('the edit is not stored under the NEW values', () async {
      final original = _appt();
      await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2026-09-27'},
      );
      final edits = await AppointmentEditsStore.load('doc1');
      final movedKey = appointmentKey(_appt(date: '2026-09-27'));
      expect(edits[movedKey], isNull,
          reason: 'keying by the edited values is the bug this guards');
    });

    test('changing the provider does not move the key either', () async {
      final original = _appt();
      final key = appointmentKey(original);
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'provider': 'Dr. Okafor'},
      );
      expect(edits[key], isNotNull);
    });

    test('the done tick still matches after an edit', () async {
      // The two stores must agree on identity, or a ticked appointment loses
      // its tick the moment it is corrected.
      final original = _appt();
      await AppointmentStatusStore.markDone('doc1', original);
      await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2026-09-27'},
      );
      final done = await AppointmentStatusStore.load('doc1');
      final edits = await AppointmentEditsStore.load('doc1');
      final key = appointmentKey(original);
      expect(done.contains(key), isTrue, reason: 'the tick was orphaned');
      expect(edits[key], isNotNull);
    });
  });

  group('what the document said is preserved', () {
    test('the original value is recorded, not the caller\'s claim about it',
        () async {
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: _appt(date: '2026-09-20'),
        changes: {'date': '2026-09-27'},
      );
      final edit = edits[appointmentKey(_appt())]!;
      expect(edit.originals['date'], '2026-09-20');
    });

    test('a field absent from the document records as empty, not missing',
        () async {
      // "Your document did not say" is information the patient should see.
      final original = _appt(reason: '');
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'reason': 'Post-op review'},
      );
      final edit = edits[appointmentKey(original)]!;
      expect(edit.originals.containsKey('reason'), isTrue);
      expect(edit.originals['reason'], '');
    });

    test('undo restores the document values', () async {
      final original = _appt();
      final key = appointmentKey(original);
      await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2026-09-27'},
      );
      final after = await AppointmentEditsStore.remove('doc1', key);
      expect(after[key], isNull);
      expect(applyAppointmentEdit(original, after[key])['date'], '2026-09-20');
    });
  });

  group('merging for display', () {
    test('no edit leaves the appointment untouched', () {
      final original = _appt();
      expect(applyAppointmentEdit(original, null), same(original));
    });

    test('only the changed fields are replaced', () async {
      final original = _appt();
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2026-09-27'},
      );
      final shown = applyAppointmentEdit(original, edits[appointmentKey(original)]);
      expect(shown['date'], '2026-09-27');
      expect(shown['provider'], 'Dr. Chen');
      expect(shown['reason'], 'Heart check');
    });

    test('a corrected future date stops the visit reading as past', () async {
      // The reason isPast is computed from the merged appointment: a visit
      // moved to next month is not history because the document's date passed.
      final original = _appt(date: '2020-01-01');
      expect(isAppointmentPast(original), isTrue);
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: original,
        changes: {'date': '2099-01-01'},
      );
      final shown =
          applyAppointmentEdit(original, edits[appointmentKey(original)]);
      expect(isAppointmentPast(shown), isFalse);
    });
  });

  group('storage refuses what it cannot use', () {
    test('an empty change set stores nothing', () async {
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: _appt(),
        changes: const {},
      );
      expect(edits, isEmpty);
    });

    test('an appointment with nothing identifying is not editable', () async {
      // appointmentKey returns '' - there is nothing to anchor an edit to.
      final blank = {'provider': '', 'specialty': '', 'date': ''};
      expect(appointmentKey(blank), isEmpty);
      final edits = await AppointmentEditsStore.save(
        docId: 'doc1',
        original: blank,
        changes: {'reason': 'something'},
      );
      expect(edits, isEmpty);
    });

    test('an unsaved run stores nothing and does not throw', () async {
      final edits = await AppointmentEditsStore.save(
        docId: '',
        original: _appt(),
        changes: {'date': '2026-09-27'},
      );
      expect(edits, isEmpty);
    });

    test('a corrupt blob degrades to no edits, not a crash', () async {
      SharedPreferences.setMockInitialValues(
          {'appointment_edits_doc1': 'not json'});
      expect(await AppointmentEditsStore.load('doc1'), isEmpty);
    });

    test('a stored row with an unknown field is dropped', () async {
      SharedPreferences.setMockInitialValues({
        'appointment_edits_doc1':
            '[{"originalKey":"dr. chen|cardiology|2026-09-20",'
                '"changes":{"cost":"500"},"originals":{"cost":"0"}}]',
      });
      expect(
        await AppointmentEditsStore.load('doc1'),
        isEmpty,
        reason: 'only the four editable fields may round-trip',
      );
    });

    test('re-editing replaces rather than stacks', () async {
      final original = _appt();
      final key = appointmentKey(original);
      await AppointmentEditsStore.save(
          docId: 'doc1', original: original, changes: {'date': '2026-09-27'});
      final edits = await AppointmentEditsStore.save(
          docId: 'doc1', original: original, changes: {'date': '2026-10-04'});
      expect(edits.length, 1);
      expect(edits[key]!.changes['date'], '2026-10-04');
    });
  });

  group('documents stay isolated', () {
    test('an edit on one document does not appear on another', () async {
      await AppointmentEditsStore.save(
          docId: 'doc1', original: _appt(), changes: {'date': '2026-09-27'});
      expect(await AppointmentEditsStore.load('doc2'), isEmpty);
    });
  });
}
