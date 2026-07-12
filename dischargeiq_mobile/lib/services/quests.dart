/// services/quests.dart
///
/// "First week home" quests (gamification wave 2): three named quests that
/// GROUP the existing reward mechanics into a visible journey - nothing new
/// is tracked, every step below is already persisted by SectionStarStore or
/// GameStats. Pure Dart (no Flutter) so quest math is unit-testable.
///
/// Design rules inherited from docs/GAMIFICATION_STRATEGY.md: progress only
/// ever counts up, no time pressure, no guilt state - an unfinished quest
/// renders as "in progress", never as "failed".
library;

import 'package:dischargeiq_mobile/models/quiz.dart' show kDomainLabels;
import 'package:dischargeiq_mobile/services/game_store.dart';

/// One quest: a titled group of concrete discharge-process steps.
class Quest {
  const Quest({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.done,
    required this.total,
  });

  final String id;
  final String title;

  /// Short line naming the NEXT step when in progress, or a completion line.
  final String subtitle;
  final int done;
  final int total;

  bool get complete => done >= total;
  double get progress => total == 0 ? 0 : done / total;
}

/// Build the three quests from persisted reward state.
///
/// Args:
///   stars: Earned star keys from SectionStarStore.load().
///   stats: Persisted GameStats from GameStore.load().
List<Quest> buildQuests({required Set<String> stars, required GameStats stats}) {
  // Quest 1 - Understand it: read all five sections.
  final read = kSectionStarKeys.where(stars.contains).length;
  final unread = kSectionStarKeys.where((k) => !stars.contains(k)).toList();
  final q1 = Quest(
    id: 'understand',
    title: 'Understand it',
    subtitle: read == kSectionStarKeys.length
        ? 'All five sections read'
        : 'Next: read ${kSectionStarLabels[unread.first]}',
    done: read,
    total: kSectionStarKeys.length,
  );

  // Quest 2 - Act on it: save an appointment + take the baseline quiz.
  final savedAppt = stars.contains(kCalendarStarKey);
  final tookBaseline = stats.quizzesCompleted > 0 || stats.history.isNotEmpty;
  final q2 = Quest(
    id: 'act',
    title: 'Act on it',
    subtitle: savedAppt && tookBaseline
        ? 'Appointment saved and first quiz done'
        : (!savedAppt
            ? 'Next: add an appointment to your calendar'
            : 'Next: take the "Test yourself" quiz'),
    done: (savedAppt ? 1 : 0) + (tookBaseline ? 1 : 0),
    total: 2,
  );

  // Quest 3 - Own it: improve on the post-quiz + master every topic.
  final improved = stats.bestLift > 0 ||
      stats.history.any((r) => r.postPercent > r.prePercent);
  final masteredCount =
      kDomainLabels.keys.where(stats.masteredDomains.contains).length;
  final allMastered = masteredCount >= kDomainLabels.length;
  final q3 = Quest(
    id: 'own',
    title: 'Own it',
    subtitle: improved && allMastered
        ? 'Every topic mastered - you own this'
        : (!improved
            ? 'Next: beat your first quiz score'
            : 'Next: master all ${kDomainLabels.length} topics '
                '($masteredCount of ${kDomainLabels.length})'),
    done: (improved ? 1 : 0) + (allMastered ? 1 : 0),
    total: 2,
  );

  return [q1, q2, q3];
}
