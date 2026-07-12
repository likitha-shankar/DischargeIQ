/// widgets/game_widgets.dart
///
/// Game-layer visuals for the teach-back quiz (Sprint 3, game v3):
/// XP/level bar, XP-gained chip, per-domain mastery badges, and the
/// welcome-back card. Pure presentation - state lives in QuizBody and
/// persists via services/game_store.dart.
///
/// Same game-design rules as quiz_widgets.dart: accuracy-based, no timers,
/// non-punitive (badges are earned, never lost).
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/models/quiz.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/widgets/quiz_widgets.dart' show kDomainIcons;
import 'package:flutter/material.dart';

/// Level + XP progress toward the next level.
class XpLevelBar extends StatelessWidget {
  const XpLevelBar({super.key, required this.stats});

  final GameStats stats;

  @override
  Widget build(BuildContext context) {
    final maxed = stats.xpToNextLevel == 0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.military_tech_outlined, size: 18, color: kTealMid),
            const SizedBox(width: 6),
            Text('Level ${stats.level}',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(fontWeight: FontWeight.w800, color: kTealMid)),
            const Spacer(),
            Text(
              maxed ? '${stats.xp} XP - top level!' : '${stats.xpToNextLevel} XP to level ${stats.level + 1}',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: Theme.of(context).textTheme.bodySmall?.color),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: stats.levelProgress.clamp(0.0, 1.0)),
            duration: const Duration(milliseconds: 700),
            curve: Curves.easeOutCubic,
            builder: (_, value, __) => LinearProgressIndicator(
              value: value,
              minHeight: 8,
              backgroundColor: kTealPale,
              valueColor: const AlwaysStoppedAnimation(kTealMid),
            ),
          ),
        ),
      ],
    );
  }
}

/// "+45 XP" chip that pops in on the results screen.
class XpGainChip extends StatelessWidget {
  const XpGainChip({super.key, required this.gained});

  final int gained;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.6, end: 1),
      duration: const Duration(milliseconds: 450),
      curve: Curves.elasticOut,
      builder: (context, scale, child) =>
          Transform.scale(scale: scale, child: child),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: kTealPale,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: kTealMid, width: 1.2),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.bolt_rounded, size: 18, color: kTealMid),
            const SizedBox(width: 4),
            Text('+$gained XP',
                style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: kTextPrimaryLight)),
          ],
        ),
      ),
    );
  }
}

/// Mastery level for one domain, derived from the round score plus any
/// badge already earned in a previous quiz (earned badges never downgrade).
enum MasteryLevel { learning, good, mastered }

MasteryLevel masteryLevelFor(
    Map<String, int> bucket, String domain, Set<String> everMastered) {
  if (everMastered.contains(domain) || bucket['correct'] == bucket['total']) {
    return MasteryLevel.mastered;
  }
  return bucket['correct']! * 2 >= bucket['total']!
      ? MasteryLevel.good
      : MasteryLevel.learning;
}

/// Per-domain mastery badges: replaces the flat green/amber chips with a
/// three-step ladder (learning → good → mastered) so progress is visible
/// even before a domain is fully correct.
class MasteryBadges extends StatelessWidget {
  const MasteryBadges({
    super.key,
    required this.result,
    required this.everMastered,
  });

  final QuizScoreResult result;

  /// Domains mastered in ANY previous quiz (from GameStats).
  final Set<String> everMastered;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final e in result.domainScores.entries)
          _badge(context, e.key, e.value),
      ],
    );
  }

  Widget _badge(BuildContext context, String domain, Map<String, int> bucket) {
    final level = masteryLevelFor(bucket, domain, everMastered);
    final (Color color, Color bg, String label) = switch (level) {
      MasteryLevel.mastered => (kTier3, kTier3Bg, 'Mastered'),
      MasteryLevel.good => (kTealMid, kTealPale, 'Almost there'),
      MasteryLevel.learning => (kTier2, kTier2Bg, 'Keep learning'),
    };
    return Chip(
      avatar: Icon(
        level == MasteryLevel.mastered
            ? Icons.workspace_premium_rounded
            : kDomainIcons[domain] ?? Icons.quiz_outlined,
        size: 16,
        color: color,
      ),
      label: Text(
        '${kDomainLabels[domain] ?? domain} - $label '
        '${bucket['correct']}/${bucket['total']}',
        style: const TextStyle(fontSize: 12.5),
      ),
      side: BorderSide(color: color),
      backgroundColor: bg,
      labelStyle: const TextStyle(color: kTextPrimaryLight),
    );
  }
}

/// Intro-screen card for returning patients: level, best score, best lift.
/// Hidden on the very first quiz (no stats yet) - nothing to brag about.
class WelcomeBackCard extends StatelessWidget {
  const WelcomeBackCard({super.key, required this.stats});

  final GameStats stats;

  @override
  Widget build(BuildContext context) {
    if (stats.quizzesCompleted == 0) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: kTealPale,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kTealMid, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.emoji_events_outlined, size: 18, color: kTealMid),
            const SizedBox(width: 6),
            Text('Welcome back - Level ${stats.level}',
                style: const TextStyle(
                    fontWeight: FontWeight.w800, color: kTextPrimaryLight)),
          ]),
          const SizedBox(height: 6),
          Text(
            'Personal best: ${stats.bestPostPercent.round()}%'
            '${stats.bestLift > 0 ? '   ·   Biggest jump: +${stats.bestLift.round()} pts' : ''}'
            '   ·   Quizzes done: ${stats.quizzesCompleted}',
            style: const TextStyle(
                fontSize: 13, color: kTextPrimaryLight, height: 1.35),
          ),
        ],
      ),
    );
  }
}

/// Discharge-process star row (Task 2.2): one star per results section read,
/// plus the add-to-calendar action star. Pure presentation; earned keys come
/// from SectionStarStore. Shown on the quiz intro so the patient sees their
/// progress before testing themselves.
class SectionStarsRow extends StatelessWidget {
  const SectionStarsRow({super.key, required this.earned});

  /// Earned star keys (subset of kAllStarKeys).
  final Set<String> earned;

  @override
  Widget build(BuildContext context) {
    // Theme-aware: this row sits directly on the screen background (no card),
    // so hardcoded light-mode colors were unreadable in dark mode.
    final dark = Theme.of(context).brightness == Brightness.dark;
    final primary = dark ? kTextPrimaryDark : kTextPrimaryLight;
    final faint = dark ? Colors.white38 : Colors.black45;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Discharge stars  ·  ${earned.length} of ${kAllStarKeys.length}',
          style: TextStyle(
              fontSize: 13, fontWeight: FontWeight.w600, color: primary),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 10,
          runSpacing: 6,
          children: [
            for (final key in kAllStarKeys)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    earned.contains(key) ? Icons.star_rounded : Icons.star_outline_rounded,
                    size: 18,
                    color: earned.contains(key)
                        ? const Color(0xFFF5B300)
                        : (dark ? Colors.white24 : Colors.black26),
                  ),
                  const SizedBox(width: 3),
                  Text(
                    kSectionStarLabels[key] ?? key,
                    style: TextStyle(
                      fontSize: 12,
                      color: earned.contains(key) ? primary : faint,
                    ),
                  ),
                ],
              ),
          ],
        ),
      ],
    );
  }
}
