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
