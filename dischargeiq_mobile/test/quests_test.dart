/// test/quests_test.dart
///
/// Unit checks for the "First week home" quest math (services/quests.dart).
/// Pure Dart - quests are computed from GameStats + star sets, no platform
/// channels. Verifies progress counting, next-step subtitles, and the
/// no-guilt rule (progress only counts up, empty state is 0/N not failure).
library;

import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/quests.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fresh patient: all quests at zero, first steps named', () {
    final quests = buildQuests(stars: {}, stats: GameStats());
    expect(quests.length, 3);
    expect(quests.every((q) => q.done == 0 && !q.complete), isTrue);
    expect(quests[0].subtitle, contains('Next: read'));
    expect(quests[1].subtitle, contains('calendar'));
    expect(quests[2].subtitle, contains('beat your first quiz'));
  });

  test('understand-it counts reading stars only, not the calendar star', () {
    final quests = buildQuests(
      stars: {'what_happened', 'medications', kCalendarStarKey},
      stats: GameStats(),
    );
    expect(quests[0].done, 2);
    expect(quests[0].total, 5);
    // Calendar star belongs to Act on it.
    expect(quests[1].done, 1);
  });

  test('act-on-it completes with calendar star + a finished quiz', () {
    final stats = GameStats()..quizzesCompleted = 1;
    final quests = buildQuests(stars: {kCalendarStarKey}, stats: stats);
    expect(quests[1].complete, isTrue);
    expect(quests[1].subtitle, contains('done'));
  });

  test('own-it needs an improvement AND all five domains mastered', () {
    final stats = GameStats(
      masteredDomains: {'diagnosis', 'medications', 'follow_up', 'activity'},
    )..bestLift = 20;
    var quests = buildQuests(stars: {}, stats: stats);
    expect(quests[2].done, 1);
    expect(quests[2].subtitle, contains('4 of 5'));

    stats.masteredDomains.add('red_flags');
    quests = buildQuests(stars: {}, stats: stats);
    expect(quests[2].complete, isTrue);
  });

  test('all quests complete on the full journey', () {
    final stats = GameStats(
      masteredDomains: {'diagnosis', 'medications', 'follow_up', 'activity', 'red_flags'},
    )
      ..quizzesCompleted = 2
      ..bestLift = 40;
    final quests = buildQuests(
      stars: kAllStarKeys.toSet(),
      stats: stats,
    );
    expect(quests.every((q) => q.complete), isTrue);
  });
}
