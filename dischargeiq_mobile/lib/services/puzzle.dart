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
        PuzzleLevel.easy => 'Icons help you group, hints on tap',
        PuzzleLevel.medium => 'No icon clues - read every card',
        PuzzleLevel.hard => 'No hints, and cards move when you miss',
      };

  /// Target number of matching pairs shown.
  int get pairCount => switch (this) {
        PuzzleLevel.easy => 3,
        PuzzleLevel.medium => 5,
        PuzzleLevel.hard => 8,
      };

  /// Extra unmatched "distractor" prompts on the right column (hard only).
  int get distractors => this == PuzzleLevel.hard ? 2 : 0;

  // The three rules below make the levels genuinely different even when a
  // sparse document caps every level at the same two or three pairs -
  // pairCount alone collapsed the levels into one for real-world summaries.

  /// Easy shows each prompt's domain icon, a visual grouping aid.
  bool get showKindIcons => this == PuzzleLevel.easy;

  /// Hard removes the hint button entirely.
  bool get hintAllowed => this != PuzzleLevel.hard;

  /// XP for solving a board at this level. Scaling with difficulty is what
  /// makes picking Hard worth something; a flat reward made Easy the only
  /// rational choice.
  int get xpReward => switch (this) {
        PuzzleLevel.easy => 10,
        PuzzleLevel.medium => 20,
        PuzzleLevel.hard => 35,
      };

  /// Hard reshuffles the unmatched tiles after every miss - a memory
  /// challenge, not a punishment: matched pairs stay matched.
  bool get reshuffleOnMiss => this == PuzzleLevel.hard;
}

/// Which discharge domain a pair teaches - drives the popup icon and copy.
enum PuzzleKind { medication, appointment, diagnosis, warning }

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
  String escalationGuide = '',
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

  // Warning signs: one symptom per escalation tier, verbatim from Agent 5's
  // guide. One per tier keeps every right-hand side distinct - two symptoms
  // that both match "Call 911" would make the game ambiguous. This is what
  // lets REAL documents play: many have no structured doses or appointment
  // dates (only ~62% of the MTSamples corpus carries medications and ~69%
  // follow-up), so without these a genuine summary often could not reach the
  // two pairs the board needs.
  pairs.addAll(_tierPairs(escalationGuide));

  return pairs;
}

/// One (symptom <-> tier action) pair per tier found in the escalation guide.
///
/// Parses the fixed tier headers Agent 5 is contractually required to emit,
/// takes the FIRST bullet under each, and strips any explanation after ":" so
/// the card shows the symptom alone. Nothing is generated here - both sides
/// are verbatim slices of grounded agent output.
List<PuzzlePair> _tierPairs(String guide) {
  if (guide.isEmpty) return const [];
  const tiers = [
    ('CALL 911 IMMEDIATELY', 'Call 911'),
    ('GO TO THE ER TODAY', 'Go to the ER today'),
    ('CALL YOUR DOCTOR', 'Call your doctor'),
  ];
  final upper = guide.toUpperCase();
  final result = <PuzzlePair>[];
  for (var t = 0; t < tiers.length; t++) {
    final start = upper.indexOf(tiers[t].$1);
    if (start < 0) continue;
    final end = t + 1 < tiers.length
        ? (upper.indexOf(tiers[t + 1].$1, start + 1) < 0
            ? guide.length
            : upper.indexOf(tiers[t + 1].$1, start + 1))
        : guide.length;
    final section = guide.substring(start, end);
    final bullet = section
        .split('\n')
        .map((l) => l.trim())
        .firstWhere(
          (l) => l.startsWith('-') || l.startsWith('•') || l.startsWith('*'),
          orElse: () => '',
        );
    if (bullet.isEmpty) continue;
    var symptom = bullet.replaceFirst(RegExp(r'^[-•*]\s*'), '');
    final colon = symptom.indexOf(':');
    if (colon > 0) symptom = symptom.substring(0, colon);
    symptom = symptom.trim();
    if (symptom.isEmpty || symptom.length > 60) continue;
    result.add(PuzzlePair(
      kind: PuzzleKind.warning,
      left: symptom,
      right: tiers[t].$2,
      teach: 'Your discharge guide says: $bullet. Knowing which symptoms '
          'need which response keeps you safe at home.',
    ));
  }
  return result;
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
