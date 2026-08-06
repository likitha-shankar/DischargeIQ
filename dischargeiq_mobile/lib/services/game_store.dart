/// services/game_store.dart
///
/// On-device persistence for the quiz game layer (Sprint 3, game v3):
/// XP, level, personal bests, mastered domains, and a short quiz history.
/// Backed by SharedPreferences (same store as theme_mode) under one JSON
/// key so a future reset is a single-key delete. No server round-trips -
/// this is engagement state, not clinical data, so it never leaves the phone.
library;

import 'dart:convert' show jsonDecode, jsonEncode;

import 'package:shared_preferences/shared_preferences.dart';

/// XP awarded per rule. Accuracy-based only - no speed bonuses, which
/// pressure older or unwell patients (same principle as the streak chip).
const int kXpPerCorrect = 10;
const int kXpQuizFinished = 25;
const int kXpAllMastered = 50;

/// Cumulative XP required to reach each level (index = level - 1).
/// Beyond the last entry the patient stays at max level.
const List<int> kLevelThresholds = [0, 100, 250, 450, 700, 1000, 1400, 1900];

/// One completed pre/post quiz run, kept for the history list.
class QuizRunRecord {
  const QuizRunRecord({
    required this.dateIso,
    required this.prePercent,
    required this.postPercent,
  });

  final String dateIso;
  final double prePercent;
  final double postPercent;

  double get lift => postPercent - prePercent;

  factory QuizRunRecord.fromJson(Map<String, dynamic> json) => QuizRunRecord(
        dateIso: '${json['date'] ?? ''}',
        prePercent: (json['pre'] as num?)?.toDouble() ?? 0,
        postPercent: (json['post'] as num?)?.toDouble() ?? 0,
      );

  Map<String, dynamic> toJson() =>
      {'date': dateIso, 'pre': prePercent, 'post': postPercent};
}

/// The whole persisted game state. Mutable by design - QuizBody updates it
/// in place after each round, then calls [GameStore.save].
class GameStats {
  GameStats({
    this.xp = 0,
    this.quizzesCompleted = 0,
    this.bestPostPercent = 0,
    this.bestLift = 0,
    Set<String>? masteredDomains,
    List<QuizRunRecord>? history,
  })  : masteredDomains = masteredDomains ?? {},
        history = history ?? [];

  int xp;
  int quizzesCompleted;
  double bestPostPercent;
  double bestLift;

  /// Domains ever answered fully correct in a post/mastery round. A badge,
  /// once earned, is never taken away - non-punitive by design.
  final Set<String> masteredDomains;

  /// Newest-first, capped at [_kHistoryCap] entries.
  final List<QuizRunRecord> history;

  static const _kHistoryCap = 20;

  /// Current level, 1-based. Level N is reached at kLevelThresholds[N-1] XP.
  int get level {
    var lvl = 1;
    for (var i = 0; i < kLevelThresholds.length; i++) {
      if (xp >= kLevelThresholds[i]) lvl = i + 1;
    }
    return lvl;
  }

  /// XP progress toward the next level as 0..1; 1.0 at max level.
  double get levelProgress {
    if (level >= kLevelThresholds.length) return 1;
    final floor = kLevelThresholds[level - 1];
    final ceil = kLevelThresholds[level];
    return (xp - floor) / (ceil - floor);
  }

  /// XP still needed for the next level; 0 at max level.
  int get xpToNextLevel => level >= kLevelThresholds.length
      ? 0
      : kLevelThresholds[level] - xp;

  /// Record one finished full run (pre+post), updating bests and history.
  void recordRun({required double prePercent, required double postPercent}) {
    quizzesCompleted++;
    if (postPercent > bestPostPercent) bestPostPercent = postPercent;
    final lift = postPercent - prePercent;
    if (lift > bestLift) bestLift = lift;
    history.insert(
      0,
      QuizRunRecord(
        dateIso: DateTime.now().toIso8601String(),
        prePercent: prePercent,
        postPercent: postPercent,
      ),
    );
    if (history.length > _kHistoryCap) history.removeRange(_kHistoryCap, history.length);
  }

  factory GameStats.fromJson(Map<String, dynamic> json) => GameStats(
        xp: (json['xp'] as num?)?.toInt() ?? 0,
        quizzesCompleted: (json['quizzes'] as num?)?.toInt() ?? 0,
        bestPostPercent: (json['best_post'] as num?)?.toDouble() ?? 0,
        bestLift: (json['best_lift'] as num?)?.toDouble() ?? 0,
        masteredDomains: {
          for (final d in (json['mastered'] as List? ?? [])) '$d'
        },
        history: [
          for (final r in (json['history'] as List? ?? []))
            QuizRunRecord.fromJson(r as Map<String, dynamic>)
        ],
      );

  Map<String, dynamic> toJson() => {
        'xp': xp,
        'quizzes': quizzesCompleted,
        'best_post': bestPostPercent,
        'best_lift': bestLift,
        'mastered': [...masteredDomains],
        'history': [for (final r in history) r.toJson()],
      };
}

/// Discharge-process step stars (Task 2.2, per the July review: gamify the
/// PROCESS of working through the instructions, not just the quiz).
/// Key order matches the first five results tabs.
const List<String> kSectionStarKeys = [
  'what_happened',
  'medications',
  'appointments',
  'warning_signs',
  'recovery',
];

/// Action star (Task 2.2, second half): earned once when the patient adds a
/// follow-up appointment to their calendar from the Appointments tab. Kept
/// out of [kSectionStarKeys] because that list maps 1:1 onto tab indices.
const String kCalendarStarKey = 'calendar_added';

/// Every earnable discharge-process star, in display order. Star counts and
/// the star row render from this list; tab-award logic uses only
/// [kSectionStarKeys].
const List<String> kAllStarKeys = [...kSectionStarKeys, kCalendarStarKey];

const Map<String, String> kSectionStarLabels = {
  'what_happened': 'What happened',
  'medications': 'Medications',
  'appointments': 'Appointments',
  'warning_signs': 'Warning signs',
  'recovery': 'Recovery',
  kCalendarStarKey: 'Appointment saved',
};

/// Stars live under their OWN SharedPreferences key, not inside [GameStats]:
/// QuizBody holds a GameStats instance in memory across a whole quiz run and
/// saves it at round ends, which would silently clobber stars awarded from
/// the results tabs in between. A separate key removes the race entirely.
class SectionStarStore {
  /// Pre-Jul-2026 global key. Stars are per-document now; [migrateLegacy]
  /// hands this old global set to the patient's oldest saved document once.
  static const _kLegacyKey = 'section_stars';

  static String _key(String docId) => 'section_stars.$docId';

  /// One-time migration: if a global (legacy) star set exists, assign it to
  /// [docId] - callers pass the OLDEST saved document, the only one that can
  /// have existed when the stars were earned - then drop the legacy key.
  /// No-op when there is nothing to migrate or the target already has stars.
  static Future<void> migrateLegacy(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final legacy = prefs.getStringList(_kLegacyKey);
      if (legacy == null) return;
      if ((prefs.getStringList(_key(docId)) ?? const []).isEmpty) {
        await prefs.setStringList(_key(docId), legacy);
      }
      await prefs.remove(_kLegacyKey);
    } catch (_) {
      // Best-effort engagement state, never blocks the UI.
    }
  }

  /// Earned star keys for one document; corrupt or missing data yields an
  /// empty set - losing stars must never break the results screen.
  static Future<Set<String>> load(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return (prefs.getStringList(_key(docId)) ?? const []).toSet();
    } catch (_) {
      return {};
    }
  }

  /// Award one star on one document. Atomic load-modify-save so concurrent
  /// awards from different screens cannot lose each other. Returns true only
  /// when the star is NEW - callers use that to show feedback exactly once
  /// per document (calm-celebration rule).
  static Future<bool> award(String docId, String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final earned = (prefs.getStringList(_key(docId)) ?? const []).toSet();
      if (earned.contains(key)) return false;
      earned.add(key);
      await prefs.setStringList(_key(docId), earned.toList()..sort());
      return true;
    } catch (_) {
      return false; // best-effort engagement state, never blocks the UI
    }
  }
}

/// Daily gentle check-in (gamification wave 3): once per day the journey
/// card asks "How are you feeling?". No streaks, no loss state - a missed
/// day simply never comes up. Entries: "YYYY-MM-DD|mood", newest last, capped.
class CheckinStore {
  static const _kKey = 'daily_checkins';
  static const _kCap = 90;

  static String _today() {
    final now = DateTime.now();
    return '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}';
  }

  /// All stored entries as (date, mood) pairs.
  static Future<List<(String, String)>> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return [
        for (final e in prefs.getStringList(_kKey) ?? const [])
          if (e.contains('|')) (e.split('|')[0], e.split('|')[1])
      ];
    } catch (_) {
      return const [];
    }
  }

  /// True when today's check-in is already recorded.
  static Future<bool> doneToday() async {
    final today = _today();
    return (await load()).any((e) => e.$1 == today);
  }

  /// Record today's mood ('good' | 'okay' | 'rough'). One per day - a
  /// second tap the same day is ignored. Returns total check-in count.
  static Future<int> record(String mood) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final entries = (prefs.getStringList(_kKey) ?? const []).toList();
      final today = _today();
      if (!entries.any((e) => e.startsWith('$today|'))) {
        entries.add('$today|$mood');
        if (entries.length > _kCap) {
          entries.removeRange(0, entries.length - _kCap);
        }
        await prefs.setStringList(_kKey, entries);
      }
      return entries.length;
    } catch (_) {
      return 0; // best-effort engagement state, never blocks the UI
    }
  }
}

/// Loads and saves [GameStats] as one JSON string in SharedPreferences.
class GameStore {
  static const _kKey = 'quiz_game_stats';

  /// Load persisted stats; corrupt or missing data yields fresh stats
  /// rather than an exception - losing XP must never break the quiz.
  static Future<GameStats> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_kKey);
      if (raw == null || raw.isEmpty) return GameStats();
      return GameStats.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return GameStats();
    }
  }

  /// Persist stats. Failures are swallowed for the same reason as [load].
  static Future<void> save(GameStats stats) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kKey, jsonEncode(stats.toJson()));
    } catch (_) {
      // ponytail: engagement state is best-effort; clinical flow never blocks on it.
    }
  }
}

/// Per-document quiz bests.
///
/// XP, levels and mastery stay GLOBAL - long-horizon progression across every
/// document is the point of them. Bests are different: "Personal best: 50%"
/// shown against a brand-new document reads as this document's history, and
/// it is not. Scoping bests to the document keeps the number honest.
class DocQuizBests {
  DocQuizBests({this.bestPostPercent = 0, this.bestLift = 0, this.runs = 0});

  double bestPostPercent;
  double bestLift;
  int runs;

  static String _key(String docId) => 'doc_quiz_bests_$docId';

  static Future<DocQuizBests> load(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(docId));
      if (raw == null || raw.isEmpty) return DocQuizBests();
      final j = jsonDecode(raw) as Map<String, dynamic>;
      return DocQuizBests(
        bestPostPercent: (j['best_post'] as num?)?.toDouble() ?? 0,
        bestLift: (j['best_lift'] as num?)?.toDouble() ?? 0,
        runs: (j['runs'] as num?)?.toInt() ?? 0,
      );
    } catch (_) {
      return DocQuizBests();
    }
  }

  static Future<void> save(String docId, DocQuizBests b) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
          _key(docId),
          jsonEncode({
            'best_post': b.bestPostPercent,
            'best_lift': b.bestLift,
            'runs': b.runs,
          }));
    } catch (_) {
      // Best-effort, same rule as GameStore: engagement state never blocks.
    }
  }
}

/// Consecutive rough days ending at the most recent check-in. Pure function
/// (testable): entries are (YYYY-MM-DD, mood), any order. A gap day breaks
/// the run - we only escalate on a genuinely unbroken rough stretch (B3).
int consecutiveRoughDays(List<(String, String)> entries) {
  final byDate = {for (final e in entries) e.$1: e.$2};
  final dates = byDate.keys.toList()..sort();
  if (dates.isEmpty) return 0;
  var run = 0;
  var cursor = DateTime.parse(dates.last);
  while (true) {
    final key = '${cursor.year.toString().padLeft(4, '0')}-'
        '${cursor.month.toString().padLeft(2, '0')}-'
        '${cursor.day.toString().padLeft(2, '0')}';
    if (byDate[key] == 'rough') {
      run++;
      cursor = cursor.subtract(const Duration(days: 1));
    } else {
      break;
    }
  }
  return run;
}

/// Personal-best moves per puzzle level (gamification wave 4). Fewer moves is
/// better; the only comparison is against the patient's own past - never other
/// patients (same no-leaderboard rule as the rest of the game layer).
class PuzzleScoreStore {
  static const _kKey = 'puzzle_best_moves';

  static Future<Map<String, int>> _all() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_kKey);
      if (raw == null || raw.isEmpty) return {};
      return {
        for (final e in (jsonDecode(raw) as Map).entries)
          '${e.key}': (e.value as num).toInt()
      };
    } catch (_) {
      return {};
    }
  }

  /// Best (fewest) moves recorded for [level], or null if never finished.
  static Future<int?> best(String level) async => (await _all())[level];

  /// Record a finished round. Returns true only when it beats the old best
  /// (or is the first finish) - callers use it for the "new best" callout.
  static Future<bool> record(String level, int moves) async {
    try {
      final all = await _all();
      final prev = all[level];
      if (prev != null && moves >= prev) return false;
      all[level] = moves;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kKey, jsonEncode(all));
      return true;
    } catch (_) {
      return false;
    }
  }
}

/// State of the "bonus that unlocks tomorrow" return hook: finishing a quiz
/// or puzzle banks today's effort (historically "plants a seed" - the pref
/// keys keep the seed names for continuity); it pays off the NEXT day the
/// journey card is visited. Appointment mechanic with no punishment: an
/// unvisited bonus simply waits - it never expires.
enum SeedState { none, planted, bloomed }

class SeedStore {
  static const _kDateKey = 'seed_planted_date';
  static const _kBloomsKey = 'seed_blooms_count';

  static String _dateKeyOf(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';

  /// Plant a seed today (finishing a quiz or puzzle calls this). Planting
  /// again the same day is a no-op; planting over an unbloomed older seed
  /// refreshes the date so it still blooms tomorrow, never retroactively.
  static Future<void> plant({DateTime? now}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kDateKey, _dateKeyOf(now ?? DateTime.now()));
    } catch (_) {
      // Best-effort engagement state.
    }
  }

  /// Current state: [SeedState.planted] the day it was planted,
  /// [SeedState.bloomed] any later day, [SeedState.none] otherwise.
  static Future<SeedState> state({DateTime? now}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final planted = prefs.getString(_kDateKey);
      if (planted == null || planted.isEmpty) return SeedState.none;
      return planted == _dateKeyOf(now ?? DateTime.now())
          ? SeedState.planted
          : SeedState.bloomed;
    } catch (_) {
      return SeedState.none;
    }
  }

  /// Acknowledge a bloom: clears the seed and adds one to the lifetime bloom
  /// count. Returns the new total.
  static Future<int> acknowledgeBloom() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final total = (prefs.getInt(_kBloomsKey) ?? 0) + 1;
      await prefs.setInt(_kBloomsKey, total);
      await prefs.remove(_kDateKey);
      return total;
    } catch (_) {
      return 0;
    }
  }

  /// Lifetime bloom count (shown as "N flowers grown from your effort").
  static Future<int> blooms() async {
    try {
      return (await SharedPreferences.getInstance()).getInt(_kBloomsKey) ?? 0;
    } catch (_) {
      return 0;
    }
  }
}
