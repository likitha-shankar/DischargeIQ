/// services/puzzle.dart
///
/// Medical matching puzzle (gamification wave 4): a no-fail matching game
/// built ENTIRELY from the patient's own extracted discharge data - match a
/// medication to its schedule, an appointment to its date, the diagnosis to
/// its plain-language meaning. Every correct match opens a short teaching
/// popup, so a right answer IS a micro-lesson (the app's whole thesis, as a
/// game).
///
/// Pure Dart - no Flutter - so the pair building, level logic, and teach-text
/// composition are unit-testable without a device.
///
/// Safety rules, in code not prose (same posture as the rest of the app):
///   - Medication schedule and dose come VERBATIM from the document.
///   - The diagnosis "meaning" REUSES Agent 2's grounded explanation text; the
///     puzzle never generates a fresh definition.
///   - Nothing is fabricated: a field that is not present simply yields no
///     pair rather than a guessed one.
///   - Pure engagement: this never feeds the comprehension-lift metric.
library;

/// Difficulty the patient picks by mood; changeable any time.
enum PuzzleLevel { easy, medium, hard }

extension PuzzleLevelInfo on PuzzleLevel {
  String get label => switch (this) {
        PuzzleLevel.easy => 'Easy',
        PuzzleLevel.medium => 'Medium',
        PuzzleLevel.hard => 'Hard',
      };

  String get blurb => switch (this) {
        PuzzleLevel.easy => 'A few pairs, gentle hints',
        PuzzleLevel.medium => 'More pairs, mixed together',
        PuzzleLevel.hard => 'Everything, with a couple of tricky extras',
      };

  /// Target number of matching pairs shown.
  int get pairCount => switch (this) {
        PuzzleLevel.easy => 3,
        PuzzleLevel.medium => 5,
        PuzzleLevel.hard => 8,
      };

  /// Extra unmatched "distractor" prompts on the right column (hard only).
  int get distractors => this == PuzzleLevel.hard ? 2 : 0;
}

/// Which discharge domain a pair teaches - drives the popup icon and copy.
enum PuzzleKind { medication, appointment, diagnosis }

/// One matchable pair: [left] is the thing the patient recognizes (a drug
/// name, a visit, their condition); [right] is what it matches to (schedule,
/// date, meaning); [teach] is the popup shown on a correct match.
class PuzzlePair {
  const PuzzlePair({
    required this.kind,
    required this.left,
    required this.right,
    required this.teach,
  });

  final PuzzleKind kind;
  final String left;
  final String right;
  final String teach;
}

/// Build the pool of grounded pairs from the extraction + Agent 2 text.
/// Order: medications first (richest, most pairs), then appointments, then
/// the single diagnosis pair. Callers trim to the level's pairCount.
List<PuzzlePair> buildPuzzlePairs(
  Map<String, dynamic> extraction, {
  String diagnosisExplanation = '',
}) {
  final pairs = <PuzzlePair>[];

  // Medications: name <-> "dose · frequency" (both verbatim). Skip a med with
  // no schedule text at all - nothing to match it to.
  final meds = extraction['medications'];
  if (meds is List) {
    for (final m in meds.whereType<Map>()) {
      final name = '${m['name'] ?? ''}'.trim();
      if (name.isEmpty) continue;
      final dose = '${m['dose'] ?? ''}'.trim();
      final freq = '${m['frequency'] ?? ''}'.trim();
      final schedule = [dose, freq].where((s) => s.isNotEmpty).join(' · ');
      if (schedule.isEmpty) continue;
      pairs.add(PuzzlePair(
        kind: PuzzleKind.medication,
        left: name,
        right: schedule,
        teach: 'You take $name as $schedule, exactly as written on your '
            'discharge papers. Always follow your pharmacy label if it differs.',
      ));
    }
  }

  // Appointments: specialty/provider <-> date. Reason (if any) enriches the
  // teach popup but is never invented.
  final appts = extraction['follow_up_appointments'];
  if (appts is List) {
    for (final a in appts.whereType<Map>()) {
      final who = '${a['specialty'] ?? a['provider'] ?? ''}'.trim();
      final date = '${a['date'] ?? ''}'.trim();
      if (who.isEmpty || date.isEmpty) continue;
      final reason = '${a['reason'] ?? ''}'.trim();
      pairs.add(PuzzlePair(
        kind: PuzzleKind.appointment,
        left: who,
        right: date,
        teach: 'Your $who visit is on $date'
            '${reason.isNotEmpty ? ', for $reason' : ''}. '
            'Adding it to your calendar helps you remember.',
      ));
    }
  }

  // Diagnosis: the condition <-> its plain-language meaning, taken from the
  // FIRST sentence of Agent 2's grounded explanation (never generated here).
  final dx = '${extraction['primary_diagnosis'] ?? ''}'.trim();
  final meaning = _firstSentence(diagnosisExplanation);
  if (dx.isNotEmpty && dx != 'Extraction failed' && meaning.isNotEmpty) {
    pairs.add(PuzzlePair(
      kind: PuzzleKind.diagnosis,
      left: dx,
      right: 'In plain words',
      teach: meaning,
    ));
  }

  return pairs;
}

/// Select the pairs for a level: take up to pairCount, preferring a mix of
/// kinds so a round is not all-medications when other kinds exist.
List<PuzzlePair> pairsForLevel(List<PuzzlePair> pool, PuzzleLevel level) {
  if (pool.length <= level.pairCount) return List.of(pool);
  // Round-robin across kinds so variety survives the trim.
  final byKind = <PuzzleKind, List<PuzzlePair>>{};
  for (final p in pool) {
    byKind.putIfAbsent(p.kind, () => []).add(p);
  }
  final picked = <PuzzlePair>[];
  final queues = byKind.values.toList();
  var i = 0;
  while (picked.length < level.pairCount && queues.any((q) => q.isNotEmpty)) {
    final q = queues[i % queues.length];
    if (q.isNotEmpty) picked.add(q.removeAt(0));
    i++;
  }
  return picked;
}

/// First sentence of a block of text, trimmed. Empty when there is none.
String _firstSentence(String text) {
  final t = text.replaceAll(RegExp(r'[*#_`]'), '').trim();
  if (t.isEmpty) return '';
  final end = t.indexOf(RegExp(r'[.!?]\s'));
  return (end < 0 ? t : t.substring(0, end + 1)).trim();
}
