/// services/journey_coach.dart
///
/// Mood-adaptive suggestion for the Recovery Journey card. Takes what the
/// app already knows - today's mood check-in, earned stars, quiz mastery -
/// and offers ONE gentle next step sized to how the patient feels.
/// Evidence basis: affect-adaptive design (adapting content to the player's
/// emotional state) sustains engagement; here the affect signal is the
/// self-reported daily mood, no sensors.
///
/// Design rules (docs/GAMIFICATION_STRATEGY.md): the suggestion is an
/// invitation, never a task. Rough days get LESS asked of them, never more.
/// Pure Dart - no Flutter - so the routing logic is unit-testable.
library;

import 'package:dischargeiq_mobile/models/quiz.dart' show kDomainLabels;
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/learning_goals.dart';

/// What kind of step the coach is pointing at - drives the icon only; the
/// card renders the suggestion as plain guidance, not a button.
enum CoachKind { rest, read, puzzle, quiz, celebrate }

/// One suggestion: a short invitation line and its icon kind.
class CoachSuggestion {
  const CoachSuggestion({required this.kind, required this.text});

  final CoachKind kind;
  final String text;
}

/// Pick one gentle next step from today's mood and current progress.
///
/// Returns null when there is nothing worth saying (no check-in yet - the
/// check-in prompt is already on screen - or an unrecognized mood value).
///
/// Args:
///   todayMood: 'good' | 'okay' | 'rough' | null (not checked in yet).
///   stats:     Current [GameStats] (mastery, quizzes completed).
///   stars:     Earned star keys from [SectionStarStore].
///   goals:     Chosen goal ids from [LearningGoalStore]. When set, the
///              section the coach names is one the patient asked for - the
///              suggestion should never send them somewhere they did not
///              choose while a chosen topic is still unread.
CoachSuggestion? suggestNextStep({
  required String? todayMood,
  required GameStats stats,
  required Set<String> stars,
  List<String> goals = const [],
}) {
  if (todayMood == null) return null;

  final unreadSections =
      goalFirstOrder(kSectionStarKeys, goals).where((k) => !stars.contains(k));
  final unmastered = kDomainLabels.length - stats.masteredDomains.length;
  final everythingDone = unreadSections.isEmpty && unmastered <= 0;

  switch (todayMood) {
    case 'rough':
      // Ask less, not more. Never point a rough day at the quiz.
      return const CoachSuggestion(
        kind: CoachKind.rest,
        text: 'No pressure today. If you feel up to it later, the matching '
            'game takes two gentle minutes - or just rest. Your progress '
            'keeps.',
      );
    case 'okay':
      if (unreadSections.isNotEmpty) {
        final label = kSectionStarLabels[unreadSections.first] ?? 'a section';
        return CoachSuggestion(
          kind: CoachKind.read,
          text: 'One small step is plenty: the "$label" section is a short '
              'read, and it checks off a milestone.',
        );
      }
      return const CoachSuggestion(
        kind: CoachKind.puzzle,
        text: 'A relaxed round of the matching game counts as looking after '
            'yourself today.',
      );
    case 'good':
      if (everythingDone) {
        return const CoachSuggestion(
          kind: CoachKind.celebrate,
          text: 'Every milestone is checked off - you know this plan well. '
              'A replay of anything is purely for fun.',
        );
      }
      if (unmastered > 0 && stats.quizzesCompleted > 0) {
        return const CoachSuggestion(
          kind: CoachKind.quiz,
          text: 'Feeling steady? A "Test yourself" round could master '
              'another topic and raise a flag on your ridge.',
        );
      }
      if (unreadSections.isNotEmpty) {
        final label = kSectionStarLabels[unreadSections.first] ?? 'a section';
        return CoachSuggestion(
          kind: CoachKind.read,
          text: 'A good day to read the "$label" section - it checks off a '
              'milestone.',
        );
      }
      return const CoachSuggestion(
        kind: CoachKind.quiz,
        text: 'Feeling steady? The "Test yourself" quiz shows you how much '
            'you already know.',
      );
    default:
      return null;
  }
}
