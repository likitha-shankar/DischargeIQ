/// test/game_store_test.dart
///
/// Unit checks for the quiz game layer's pure logic (services/game_store.dart):
/// level thresholds, XP progress, run recording / personal bests, history cap,
/// and JSON round-tripping. No SharedPreferences involved - GameStats is plain
/// Dart, so these run with `flutter test` and no platform channels.
library;

import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('level rises with XP and progress stays in 0..1', () {
    final stats = GameStats();
    expect(stats.level, 1);
    stats.xp = 99;
    expect(stats.level, 1);
    stats.xp = 100;
    expect(stats.level, 2);
    expect(stats.xpToNextLevel, 150);
    stats.xp = 5000; // beyond the last threshold
    expect(stats.level, kLevelThresholds.length);
    expect(stats.levelProgress, 1);
    expect(stats.xpToNextLevel, 0);
  });

  test('recordRun updates bests, count, and newest-first history', () {
    final stats = GameStats();
    stats.recordRun(prePercent: 40, postPercent: 80);
    stats.recordRun(prePercent: 60, postPercent: 70);
    expect(stats.quizzesCompleted, 2);
    expect(stats.bestPostPercent, 80);
    expect(stats.bestLift, 40);
    expect(stats.history.first.postPercent, 70); // newest first
  });

  test('history is capped at 20 runs', () {
    final stats = GameStats();
    for (var i = 0; i < 25; i++) {
      stats.recordRun(prePercent: 0, postPercent: i.toDouble());
    }
    expect(stats.history.length, 20);
    expect(stats.history.first.postPercent, 24); // newest kept
  });

  test('JSON round-trip preserves everything', () {
    final stats = GameStats(xp: 260, quizzesCompleted: 3, bestPostPercent: 90,
        bestLift: 55, masteredDomains: {'medications', 'red_flags'});
    stats.recordRun(prePercent: 20, postPercent: 100);
    final copy = GameStats.fromJson(stats.toJson());
    expect(copy.xp, stats.xp);
    expect(copy.level, 3);
    expect(copy.masteredDomains, stats.masteredDomains);
    expect(copy.history.length, stats.history.length);
    expect(copy.bestPostPercent, 100); // recordRun raised it before the copy
  });

  test('missing or null fields degrade to defaults', () {
    // Wholly corrupt JSON (wrong types) is caught by GameStore.load's
    // try/catch; fromJson itself only guarantees null/missing tolerance.
    final stats = GameStats.fromJson({'history': null, 'mastered': null});
    expect(stats.xp, 0);
    expect(stats.level, 1);
    expect(stats.history, isEmpty);
    expect(stats.masteredDomains, isEmpty);
  });

  // ── Section stars (Task 2.2) ─────────────────────────────────────────────
  // SectionStarStore touches SharedPreferences; setMockInitialValues gives it
  // an in-memory backend so these still run without platform channels.

  test('section star awarded once, persists, and count is stable', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    SharedPreferences.setMockInitialValues({});

    expect(await SectionStarStore.load(), isEmpty);
    expect(await SectionStarStore.award('medications'), isTrue);
    expect(await SectionStarStore.award('medications'), isFalse); // once, ever
    expect(await SectionStarStore.award('recovery'), isTrue);
    expect(await SectionStarStore.load(), {'medications', 'recovery'});
  });

  test('star keys and labels agree with each other', () {
    expect(kAllStarKeys.toSet(), kSectionStarLabels.keys.toSet());
    expect(kSectionStarKeys.length, 5); // tab-mapped reading stars only
    expect(kAllStarKeys.length, 6); // + the add-to-calendar action star
  });

  test('daily check-in records once per day and counts days', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    SharedPreferences.setMockInitialValues({});
    expect(await CheckinStore.doneToday(), isFalse);
    expect(await CheckinStore.record('good'), 1);
    expect(await CheckinStore.doneToday(), isTrue);
    // Second answer the same day is ignored - no double counting.
    expect(await CheckinStore.record('rough'), 1);
    final entries = await CheckinStore.load();
    expect(entries.length, 1);
    expect(entries.first.$2, 'good');
  });
}
