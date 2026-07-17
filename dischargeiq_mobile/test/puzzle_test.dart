/// test/puzzle_test.dart
///
/// Unit checks for the medical matching puzzle builder (services/puzzle.dart):
/// grounded pair construction (verbatim schedule, no fabrication), the diagnosis
/// meaning reusing Agent 2 text, level trimming with kind variety, and the
/// skip rules for missing fields. Pure Dart.
library;

import 'package:dischargeiq_mobile/services/puzzle.dart';
import 'package:flutter_test/flutter_test.dart';

const _extraction = {
  'primary_diagnosis': 'Heart failure',
  'medications': [
    {'name': 'Furosemide', 'dose': '40 mg', 'frequency': 'every morning'},
    {'name': 'Lisinopril', 'dose': '10 mg', 'frequency': 'once daily'},
    {'name': 'MysteryPill'}, // no schedule -> no pair
  ],
  'follow_up_appointments': [
    {'specialty': 'Cardiology', 'date': 'July 22', 'reason': 'medication review'},
    {'provider': 'Dr. Patel'}, // no date -> no pair
  ],
};

void main() {
  test('builds grounded pairs, skips fields with nothing to match', () {
    final pairs = buildPuzzlePairs(_extraction,
        diagnosisExplanation: 'Your heart is not pumping as well as it should. '
            'This causes fluid to build up.');
    // 2 meds (MysteryPill skipped) + 1 appt (Dr. Patel skipped) + 1 diagnosis
    expect(pairs.length, 4);

    final med = pairs.firstWhere((p) => p.kind == PuzzleKind.medication);
    expect(med.left, 'Furosemide');
    expect(med.right, '40 mg · every morning'); // verbatim schedule
    expect(med.teach, contains('40 mg · every morning'));

    final appt = pairs.firstWhere((p) => p.kind == PuzzleKind.appointment);
    expect(appt.right, 'July 22');
    expect(appt.teach, contains('medication review'));

    final dx = pairs.firstWhere((p) => p.kind == PuzzleKind.diagnosis);
    expect(dx.left, 'Heart failure');
    // Meaning is the FIRST sentence of the grounded explanation, not generated.
    expect(dx.teach, 'Your heart is not pumping as well as it should.');
  });

  test('no diagnosis pair without grounded explanation text', () {
    final pairs = buildPuzzlePairs(_extraction); // no diagnosisExplanation
    expect(pairs.any((p) => p.kind == PuzzleKind.diagnosis), isFalse);
  });

  test('extraction-failed diagnosis is never turned into a pair', () {
    final pairs = buildPuzzlePairs(
      {'primary_diagnosis': 'Extraction failed', 'medications': []},
      diagnosisExplanation: 'anything',
    );
    expect(pairs, isEmpty);
  });

  test('level trims to pair count and keeps kind variety', () {
    final pool = buildPuzzlePairs(_extraction,
        diagnosisExplanation: 'Your heart is weak. It needs help.');
    final easy = pairsForLevel(pool, PuzzleLevel.easy);
    expect(easy.length, 3);
    // Easy pulls across kinds, not 3 medications in a row.
    expect(easy.map((p) => p.kind).toSet().length, greaterThan(1));

    // A pool smaller than the level count returns everything, no padding.
    final hard = pairsForLevel(pool, PuzzleLevel.hard);
    expect(hard.length, pool.length);
  });

  test('level metadata is sane', () {
    expect(PuzzleLevel.easy.pairCount, 3);
    expect(PuzzleLevel.hard.distractors, 2);
    expect(PuzzleLevel.easy.distractors, 0);
    expect(PuzzleLevel.medium.label, 'Medium');
  });
}
