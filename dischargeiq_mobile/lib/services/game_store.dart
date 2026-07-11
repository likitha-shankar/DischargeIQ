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
  static const _kKey = 'section_stars';

  /// Set of earned star keys; corrupt or missing data yields an empty set -
  /// losing stars must never break the results screen.
  static Future<Set<String>> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return (prefs.getStringList(_kKey) ?? const []).toSet();
    } catch (_) {
      return {};
    }
  }

  /// Award one star. Atomic load-modify-save so concurrent awards from
  /// different screens cannot lose each other. Returns true only when the
  /// star is NEW - callers use that to show feedback exactly once, ever
  /// (calm-celebration rule: a star can only be earned once).
  static Future<bool> award(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final earned = (prefs.getStringList(_kKey) ?? const []).toSet();
      if (earned.contains(key)) return false;
      earned.add(key);
      await prefs.setStringList(_kKey, earned.toList()..sort());
      return true;
    } catch (_) {
      return false; // best-effort engagement state, never blocks the UI
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
