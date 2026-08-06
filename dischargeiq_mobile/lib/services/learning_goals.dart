/// services/learning_goals.dart
///
/// Patient-chosen learning goals and the understanding rubric behind them
/// (clinical review, Aug 2026: define a rubric, ask the patient what they
/// want to learn, then gamify THAT rather than a fixed reading order).
///
/// Two ideas live here:
///   1. A goal is one of the five discharge topics the patient says matters
///      most to them. Goals reorder the journey - quests, the coach, and the
///      reading order all point at chosen topics first.
///   2. The rubric is a four-level teach-back ladder the patient rates
///      themselves against, before and after. The movement between those two
///      ratings is the outcome this feature is measured by.
///
/// Pure Dart apart from SharedPreferences, so the rubric and ordering logic
/// stay unit-testable. Every value here is engagement data, never clinical
/// data, and never leaves the device - see docs/GAMIFICATION_STRATEGY.md.
library;

import 'package:shared_preferences/shared_preferences.dart';

/// One learning goal: a discharge topic the patient can choose to focus on.
///
/// The app already tracks the same five topics under two different
/// vocabularies - reading stars ([starKey]) and quiz domains ([quizDomain]).
/// A goal binds them so that choosing a topic drives both the reading journey
/// and the quiz mastery that proves it landed.
class LearningGoal {
  const LearningGoal({
    required this.id,
    required this.label,
    required this.prompt,
    required this.starKey,
    required this.quizDomain,
  });

  /// Stable storage id. Never renamed - it is a SharedPreferences value.
  final String id;

  /// Short name, used in chips and quest lines.
  final String label;

  /// The patient's own words for what they want out of this topic. Shown in
  /// the picker, because "Medications" is a category and "What each of my
  /// pills is for" is a reason to tap it.
  final String prompt;

  /// Matching reading star in [kSectionStarKeys].
  final String starKey;

  /// Matching quiz domain in [kDomainLabels].
  final String quizDomain;
}

/// The five goals, in the order the picker shows them. Ordered by how often
/// patients are confused by each topic rather than by document order, so the
/// two most-missed topics are not buried at the bottom of the sheet.
const List<LearningGoal> kLearningGoals = [
  LearningGoal(
    id: 'medications',
    label: 'My medications',
    prompt: 'What each pill is for, and when to take it',
    starKey: 'medications',
    quizDomain: 'medications',
  ),
  LearningGoal(
    id: 'warning_signs',
    label: 'Warning signs',
    prompt: 'Which symptoms mean I should call someone',
    starKey: 'warning_signs',
    quizDomain: 'red_flags',
  ),
  LearningGoal(
    id: 'what_happened',
    label: 'What happened',
    prompt: 'What my diagnosis actually means',
    starKey: 'what_happened',
    quizDomain: 'diagnosis',
  ),
  LearningGoal(
    id: 'recovery',
    label: 'Getting better',
    prompt: 'What I can and cannot do while I recover',
    starKey: 'recovery',
    quizDomain: 'activity',
  ),
  LearningGoal(
    id: 'appointments',
    label: 'Follow-up visits',
    prompt: 'Who I see next, and when',
    starKey: 'appointments',
    quizDomain: 'follow_up',
  ),
];

/// Look up a goal by id; null for unknown ids so stored data from an older
/// build can never crash the journey.
LearningGoal? goalById(String id) {
  for (final g in kLearningGoals) {
    if (g.id == id) return g;
  }
  return null;
}

/// The understanding rubric: a four-level teach-back ladder.
///
/// Deliberately the patient's own judgement, not a score the app computes.
/// The wording climbs toward "I could explain this to someone else", which is
/// what teach-back actually asks of a patient, so the top of the ladder is
/// the same bar a nurse would use at the bedside.
class UnderstandingLevel {
  const UnderstandingLevel({
    required this.value,
    required this.label,
    required this.blurb,
  });

  /// 0-3. Stored as an int; order is the whole meaning.
  final int value;

  /// Short label for the chip or slider stop.
  final String label;

  /// The sentence the patient reads when choosing this level.
  final String blurb;
}

const List<UnderstandingLevel> kUnderstandingLevels = [
  UnderstandingLevel(
    value: 0,
    label: 'Not yet',
    blurb: 'I have not really understood this part.',
  ),
  UnderstandingLevel(
    value: 1,
    label: 'The gist',
    blurb: 'I get the general idea, but not the details.',
  ),
  UnderstandingLevel(
    value: 2,
    label: 'I could explain it',
    blurb: 'I could explain this to someone at home.',
  ),
  UnderstandingLevel(
    value: 3,
    label: 'I could teach it',
    blurb: 'I could teach this, and act on it without checking.',
  ),
];

/// Highest rung of the rubric, used for progress maths.
const int kMaxUnderstanding = 3;

/// Whether a rating counts as "understood" for quest completion. Level 2 -
/// could explain it to someone at home - is the teach-back bar; level 3 is
/// aspirational and must not be required to finish a quest.
const int kUnderstoodThreshold = 2;

/// Per-document learning goals and self-ratings.
///
/// Everything is scoped by document id for the same reason stars are: a
/// patient with two discharge summaries has different goals for each, and
/// showing one document's goals over another's was the exact class of bug
/// that made per-document stars necessary.
class LearningGoalStore {
  static String _goalsKey(String docId) => 'learning_goals.$docId';

  static String _ratingKey(String docId, String goalId, String phase) =>
      'learning_level.$docId.$goalId.$phase';

  /// Marks that the patient has been shown the picker for this document, so
  /// it is never asked twice - including when they chose nothing, which is a
  /// valid answer and must be remembered as one.
  static String _askedKey(String docId) => 'learning_goals_asked.$docId';

  /// Chosen goal ids for one document, in [kLearningGoals] order.
  ///
  /// Returns an empty list when nothing was chosen or storage is unreadable -
  /// no goals simply means the journey keeps its default order.
  static Future<List<String>> load(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = (prefs.getStringList(_goalsKey(docId)) ?? const []).toSet();
      // Filter through the canonical list so a goal removed in a later build
      // disappears quietly instead of rendering as a blank chip.
      return [
        for (final g in kLearningGoals)
          if (stored.contains(g.id)) g.id,
      ];
    } catch (_) {
      return const [];
    }
  }

  /// Replace the goal set for one document. Passing an empty list is a real
  /// choice ("show me everything"), not a reset.
  static Future<bool> save(String docId, List<String> goalIds) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_goalsKey(docId), goalIds);
      await prefs.setBool(_askedKey(docId), true);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// True once the picker has been shown for this document, whatever the
  /// patient chose. Callers use it to ask exactly once.
  static Future<bool> wasAsked(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_askedKey(docId)) ?? false;
    } catch (_) {
      // Fail toward not nagging: an unreadable flag must not re-open the
      // sheet on every visit.
      return true;
    }
  }

  /// One self-rating. [phase] is 'pre' (at goal-setting) or 'post' (after
  /// working through the topic). Null when never rated.
  static Future<int?> rating(String docId, String goalId, String phase) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getInt(_ratingKey(docId, goalId, phase));
    } catch (_) {
      return null;
    }
  }

  /// Store one self-rating, clamped to the rubric's range.
  static Future<bool> rate(
    String docId,
    String goalId,
    String phase,
    int level,
  ) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(
        _ratingKey(docId, goalId, phase),
        level.clamp(0, kMaxUnderstanding),
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Every rating for one document, keyed by goal id, for a whole phase.
  /// Used by the journey card so one read covers all goals.
  static Future<Map<String, int>> ratings(String docId, String phase) async {
    final out = <String, int>{};
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final goal in kLearningGoals) {
        final v = prefs.getInt(_ratingKey(docId, goal.id, phase));
        if (v != null) out[goal.id] = v;
      }
    } catch (_) {
      // Partial results are fine - a missing rating renders as "not rated".
    }
    return out;
  }

  /// Wipe one document's goals and ratings. Called when a document is
  /// deleted, so a reused id can never inherit a stranger's goals.
  static Future<void> clear(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_goalsKey(docId));
      await prefs.remove(_askedKey(docId));
      for (final goal in kLearningGoals) {
        for (final phase in const ['pre', 'post']) {
          await prefs.remove(_ratingKey(docId, goal.id, phase));
        }
      }
    } catch (_) {
      // Best-effort cleanup; orphaned engagement keys are harmless.
    }
  }
}

/// Reading order with the patient's goals first.
///
/// The journey and coach walk sections in this order, so someone who said
/// "I care about my medications" is pointed at medications before the app
/// suggests reading about follow-up visits. Non-goal sections keep their
/// original order behind the goals - nothing is hidden, only reordered.
///
/// Args:
///   allKeys: Canonical star keys, normally kSectionStarKeys.
///   goalIds: Chosen goal ids; empty means keep the canonical order.
///
/// Returns:
///   The same keys, goal-matching ones first.
List<String> goalFirstOrder(List<String> allKeys, List<String> goalIds) {
  if (goalIds.isEmpty) return List.of(allKeys);
  final goalStarKeys = <String>{
    for (final id in goalIds)
      if (goalById(id) != null) goalById(id)!.starKey,
  };
  return [
    ...allKeys.where(goalStarKeys.contains),
    ...allKeys.where((k) => !goalStarKeys.contains(k)),
  ];
}

/// Progress on one goal: what the patient has done, and how far their own
/// rating has moved. Both halves matter - reading the section is evidence of
/// effort, the rating change is the outcome the rubric actually measures.
class GoalProgress {
  const GoalProgress({
    required this.goal,
    required this.sectionRead,
    required this.domainMastered,
    required this.preLevel,
    required this.postLevel,
  });

  final LearningGoal goal;

  /// Reading star earned for this goal's section.
  final bool sectionRead;

  /// Quiz mastery reached on this goal's domain.
  final bool domainMastered;

  /// Self-rating when the goal was set, and after. Null when not yet rated.
  final int? preLevel;
  final int? postLevel;

  /// Rubric movement, or null until both ratings exist. Can be negative -
  /// a patient who realises they understood less than they thought is a real
  /// and useful result, so it is never clamped to zero.
  int? get lift =>
      (preLevel == null || postLevel == null) ? null : postLevel! - preLevel!;

  /// The goal is met when the patient has read the section AND rates
  /// themselves at the teach-back bar. Mastery is a bonus, not a gate: the
  /// quiz is optional and a goal must be reachable without it.
  bool get met =>
      sectionRead && (postLevel ?? preLevel ?? 0) >= kUnderstoodThreshold;
}

/// Build progress for every chosen goal.
///
/// Args:
///   goalIds:  Chosen goal ids from [LearningGoalStore.load].
///   stars:    Earned star keys from SectionStarStore.
///   mastered: Mastered quiz domains from GameStats.masteredDomains.
///   pre/post: Rating maps from [LearningGoalStore.ratings].
List<GoalProgress> buildGoalProgress({
  required List<String> goalIds,
  required Set<String> stars,
  required Set<String> mastered,
  required Map<String, int> pre,
  required Map<String, int> post,
}) {
  final out = <GoalProgress>[];
  for (final id in goalIds) {
    final goal = goalById(id);
    if (goal == null) continue; // stored id from an older build
    out.add(GoalProgress(
      goal: goal,
      sectionRead: stars.contains(goal.starKey),
      domainMastered: mastered.contains(goal.quizDomain),
      preLevel: pre[id],
      postLevel: post[id],
    ));
  }
  return out;
}

/// The next goal worth pointing the patient at, or null when every goal is
/// met. Unread sections come first, then goals that are read but still rated
/// below the teach-back bar - reading is a smaller ask than re-rating.
GoalProgress? nextGoalStep(List<GoalProgress> progress) {
  for (final p in progress) {
    if (!p.sectionRead) return p;
  }
  for (final p in progress) {
    if (!p.met) return p;
  }
  return null;
}
