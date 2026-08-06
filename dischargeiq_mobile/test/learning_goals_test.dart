/// test/learning_goals_test.dart
///
/// Tests the patient-chosen learning goals and the understanding rubric:
/// storage round-trips, goal-first ordering, rubric movement, and the way
/// goals reshape the quests and the coach.
///
/// The behaviour worth pinning is that a chosen goal actually changes what
/// the app asks next - a goals feature that stores a preference and then
/// ignores it would pass a naive test and fail the patient.
library;

import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/journey_coach.dart';
import 'package:dischargeiq_mobile/services/learning_goals.dart';
import 'package:dischargeiq_mobile/services/quests.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Progress for one goal, with only the fields a given test cares about.
GoalProgress _progress(
  String goalId, {
  bool read = false,
  bool mastered = false,
  int? pre,
  int? post,
}) =>
    GoalProgress(
      goal: goalById(goalId)!,
      sectionRead: read,
      domainMastered: mastered,
      preLevel: pre,
      postLevel: post,
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('goal catalogue', () {
    test('every goal maps onto a real star key and quiz domain', () {
      // The whole feature rests on this: a goal must be able to drive both
      // the reading journey and the mastery that proves it landed.
      for (final goal in kLearningGoals) {
        expect(kSectionStarKeys, contains(goal.starKey),
            reason: '${goal.id} has no reading section');
        expect(kSectionStarLabels.containsKey(goal.starKey), isTrue);
      }
    });

    test('goal ids are unique and resolvable', () {
      final ids = kLearningGoals.map((g) => g.id).toSet();
      expect(ids, hasLength(kLearningGoals.length));
      for (final id in ids) {
        expect(goalById(id), isNotNull);
      }
      expect(goalById('not_a_goal'), isNull);
    });
  });

  group('storage', () {
    test('goals round-trip in catalogue order, not tap order', () async {
      // Tapped bottom-up; stored order must still be the display order so the
      // chips do not shuffle between visits.
      await LearningGoalStore.save('doc1', ['appointments', 'medications']);
      expect(await LearningGoalStore.load('doc1'),
          ['medications', 'appointments']);
    });

    test('goals are per document', () async {
      await LearningGoalStore.save('doc1', ['medications']);
      expect(await LearningGoalStore.load('doc2'), isEmpty);
    });

    test('an unknown stored goal is dropped, not rendered blank', () async {
      // Simulates a goal removed in a later build.
      SharedPreferences.setMockInitialValues({
        'learning_goals.doc1': ['medications', 'retired_topic'],
      });
      expect(await LearningGoalStore.load('doc1'), ['medications']);
    });

    test('choosing nothing is remembered as an answer', () async {
      expect(await LearningGoalStore.wasAsked('doc1'), isFalse);
      await LearningGoalStore.save('doc1', const []);
      // Must not re-open the picker on every visit just because the patient
      // said "show me everything".
      expect(await LearningGoalStore.wasAsked('doc1'), isTrue);
      expect(await LearningGoalStore.load('doc1'), isEmpty);
    });

    test('ratings store per phase and clamp to the rubric', () async {
      await LearningGoalStore.rate('doc1', 'medications', 'pre', 1);
      await LearningGoalStore.rate('doc1', 'medications', 'post', 99);
      expect(await LearningGoalStore.rating('doc1', 'medications', 'pre'), 1);
      expect(await LearningGoalStore.rating('doc1', 'medications', 'post'),
          kMaxUnderstanding);
    });

    test('deleting clears goals and ratings', () async {
      await LearningGoalStore.save('doc1', ['medications']);
      await LearningGoalStore.rate('doc1', 'medications', 'pre', 2);
      await LearningGoalStore.clear('doc1');
      expect(await LearningGoalStore.load('doc1'), isEmpty);
      expect(await LearningGoalStore.rating('doc1', 'medications', 'pre'),
          isNull);
      // Asked-flag clears too, so a genuinely new document asks again.
      expect(await LearningGoalStore.wasAsked('doc1'), isFalse);
    });
  });

  group('goal-first ordering', () {
    test('chosen topics come first, nothing is dropped', () {
      final ordered = goalFirstOrder(kSectionStarKeys, ['warning_signs']);
      expect(ordered.first, 'warning_signs');
      expect(ordered.toSet(), kSectionStarKeys.toSet());
      expect(ordered, hasLength(kSectionStarKeys.length));
    });

    test('no goals keeps the canonical order', () {
      expect(goalFirstOrder(kSectionStarKeys, const []), kSectionStarKeys);
    });
  });

  group('rubric movement', () {
    test('lift is null until both ratings exist', () {
      expect(_progress('medications', pre: 1).lift, isNull);
      expect(_progress('medications', post: 3).lift, isNull);
      expect(_progress('medications', pre: 1, post: 3).lift, 2);
    });

    test('a drop is reported, not hidden', () {
      // A patient who realises they understood less than they thought is a
      // real result. Clamping it to zero would erase the most useful signal
      // this rubric can produce.
      expect(_progress('medications', pre: 3, post: 1).lift, -2);
    });

    test('a goal is met at the teach-back bar, without needing the quiz', () {
      expect(_progress('medications', read: true, post: 1).met, isFalse);
      expect(_progress('medications', read: true, post: 2).met, isTrue);
      // Reading is required - a high self-rating alone is not evidence.
      expect(_progress('medications', post: 3).met, isFalse);
      // Mastery is a bonus, never a gate.
      expect(_progress('medications', read: true, post: 2, mastered: false).met,
          isTrue);
    });
  });

  group('next step', () {
    test('unread goals outrank read-but-unrated ones', () {
      final next = nextGoalStep([
        _progress('medications', read: true, pre: 1),
        _progress('warning_signs'),
      ]);
      expect(next!.goal.id, 'warning_signs');
    });

    test('null once every goal is met', () {
      expect(
        nextGoalStep([_progress('medications', read: true, post: 3)]),
        isNull,
      );
    });
  });

  group('quests follow the goals', () {
    test('a goal quest is added and comes first', () {
      final quests = buildQuests(
        stars: const {},
        stats: GameStats(),
        goals: const ['medications'],
        progress: [_progress('medications')],
      );
      expect(quests.first.id, 'goals');
      expect(quests.first.title, 'Your goal');
      expect(quests.first.subtitle, contains('My medications'));
    });

    test('no goal quest when no goals are set', () {
      final quests =
          buildQuests(stars: const {}, stats: GameStats());
      expect(quests.map((q) => q.id), isNot(contains('goals')));
      expect(quests, hasLength(3));
    });

    test('"Understand it" names a chosen topic first', () {
      // Without goals this would name "What happened", the first section.
      final quests = buildQuests(
        stars: const {},
        stats: GameStats(),
        goals: const ['warning_signs'],
        progress: [_progress('warning_signs')],
      );
      final understand = quests.firstWhere((q) => q.id == 'understand');
      expect(understand.subtitle, contains('Warning signs'));
    });

    test('a read goal switches the ask from reading to re-rating', () {
      final quests = buildQuests(
        stars: const {'medications'},
        stats: GameStats(),
        goals: const ['medications'],
        progress: [_progress('medications', read: true, pre: 1)],
      );
      expect(quests.first.subtitle, contains('rate how well'));
    });
  });

  group('coach follows the goals', () {
    test('it points at a chosen topic before an earlier unchosen one', () {
      final suggestion = suggestNextStep(
        todayMood: 'okay',
        stats: GameStats(),
        stars: const {},
        goals: const ['recovery'],
      );
      expect(suggestion!.text, contains('Recovery'));
    });

    test('a rough day still asks for nothing, goals or not', () {
      // The mood rule outranks the goals rule: a goal must never become a
      // reason to push someone who said they feel rough.
      final suggestion = suggestNextStep(
        todayMood: 'rough',
        stats: GameStats(),
        stars: const {},
        goals: const ['medications'],
      );
      expect(suggestion!.kind, CoachKind.rest);
    });
  });
}
