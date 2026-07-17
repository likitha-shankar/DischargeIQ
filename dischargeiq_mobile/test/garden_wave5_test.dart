/// test/garden_wave5_test.dart
///
/// Unit checks for gamification wave 5: the mood-adaptive coach
/// (services/garden_coach.dart) and the seed-blooms-tomorrow return hook
/// (SeedStore in services/game_store.dart). SeedStore uses SharedPreferences,
/// mocked with setMockInitialValues; the coach is pure Dart.
library;

import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/garden_coach.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('garden coach', () {
    test('no check-in yet means no suggestion', () {
      expect(
        suggestNextStep(todayMood: null, stats: GameStats(), stars: {}),
        isNull,
      );
    });

    test('rough day never points at the quiz', () {
      final s = suggestNextStep(
          todayMood: 'rough', stats: GameStats(), stars: {});
      expect(s, isNotNull);
      expect(s!.kind, CoachKind.rest);
      expect(s.text.contains('Test yourself'), isFalse);
    });

    test('okay day suggests the first unread section by name', () {
      final s = suggestNextStep(
        todayMood: 'okay',
        stats: GameStats(),
        stars: {'what_happened'},
      );
      expect(s!.kind, CoachKind.read);
      expect(s.text, contains(kSectionStarLabels['medications']!));
    });

    test('good day with a quiz behind them stretches toward mastery', () {
      final stats = GameStats()..quizzesCompleted = 1;
      final s = suggestNextStep(
        todayMood: 'good',
        stats: stats,
        stars: kSectionStarKeys.toSet(),
      );
      expect(s!.kind, CoachKind.quiz);
    });

    test('everything done on a good day celebrates without asking more', () {
      final stats = GameStats()
        ..quizzesCompleted = 3
        ..masteredDomains.addAll(
            ['medications', 'appointments', 'warning_signs', 'recovery', 'diagnosis']);
      final s = suggestNextStep(
        todayMood: 'good',
        stats: stats,
        stars: kSectionStarKeys.toSet(),
      );
      expect(s!.kind, CoachKind.celebrate);
    });

    test('unknown mood value yields nothing rather than a wrong nudge', () {
      expect(
        suggestNextStep(todayMood: 'meh', stats: GameStats(), stars: {}),
        isNull,
      );
    });
  });

  group('seed store', () {
    test('plant today reads planted today and bloomed tomorrow', () async {
      SharedPreferences.setMockInitialValues({});
      final today = DateTime(2026, 7, 15, 14);
      await SeedStore.plant(now: today);
      expect(await SeedStore.state(now: today), SeedState.planted);
      expect(
        await SeedStore.state(now: today.add(const Duration(days: 1))),
        SeedState.bloomed,
      );
    });

    test('no seed means none, and bloom acknowledgment counts and clears',
        () async {
      SharedPreferences.setMockInitialValues({});
      expect(await SeedStore.state(), SeedState.none);

      final planted = DateTime(2026, 7, 15);
      final tomorrow = DateTime(2026, 7, 16);
      await SeedStore.plant(now: planted);
      expect(await SeedStore.state(now: tomorrow), SeedState.bloomed);
      expect(await SeedStore.acknowledgeBloom(), 1);
      // Cleared after acknowledgment; lifetime count persists.
      expect(await SeedStore.state(now: tomorrow), SeedState.none);
      expect(await SeedStore.blooms(), 1);
    });

    test('replanting the same day is idempotent, never retroactive', () async {
      SharedPreferences.setMockInitialValues({});
      final day = DateTime(2026, 7, 15);
      await SeedStore.plant(now: day);
      await SeedStore.plant(now: day);
      expect(await SeedStore.state(now: day), SeedState.planted);
    });
  });

  group('companion store', () {
    test('unnamed by default, trims and caps the saved name', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await CompanionStore.name(), '');
      await CompanionStore.setName('  Maple  ');
      expect(await CompanionStore.name(), 'Maple');
      await CompanionStore.setName('x' * 40);
      expect((await CompanionStore.name()).length, 20);
    });

    test('kind defaults to butterfly and rejects unknown values', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await CompanionStore.kind(), 'butterfly');
      await CompanionStore.setKind('turtle');
      expect(await CompanionStore.kind(), 'turtle');
      await CompanionStore.setKind('dragon'); // not a garden resident
      expect(await CompanionStore.kind(), 'turtle');
    });
  });
}
