/// widgets/quiz_widgets.dart
///
/// Reusable visual pieces for the teach-back quiz flow (Sprint 3):
/// question card with tappable options, step progress bar, animated score
/// ring, per-domain result chips, and the comprehension-lift banner.
/// Pure presentation - all state lives in QuizScreen.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/models/quiz.dart';
import 'package:flutter/material.dart';

const Map<String, IconData> kDomainIcons = {
  'diagnosis': Icons.monitor_heart_outlined,
  'medications': Icons.medication_outlined,
  'follow_up': Icons.event_available_outlined,
  'activity': Icons.directions_walk_outlined,
  'red_flags': Icons.warning_amber_outlined,
};

/// Step progress: "Question 2 of 5" with a filled linear track.
class QuizProgressBar extends StatelessWidget {
  const QuizProgressBar({
    super.key,
    required this.current,
    required this.total,
    required this.label,
  });

  final int current;
  final int total;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: Theme.of(context)
                .textTheme
                .labelLarge
                ?.copyWith(color: kTealMid, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: current / total),
            duration: const Duration(milliseconds: 350),
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

/// One question with 4 tappable options.
///
/// [revealCorrect] is false during the pre (baseline) phase - protocol §3a:
/// no feedback before the intervention, or the baseline teaches. In post
/// phase, after selection the correct option turns green, a wrong pick turns
/// red, and the explanation appears.
class QuestionCard extends StatelessWidget {
  const QuestionCard({
    super.key,
    required this.question,
    required this.selectedIndex,
    required this.revealCorrect,
    required this.onSelect,
  });

  final QuizQuestion question;
  final int? selectedIndex;
  final bool revealCorrect;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final answered = selectedIndex != null;
    final showFeedback = revealCorrect && answered;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(kDomainIcons[question.domain] ?? Icons.quiz_outlined,
                color: kTealMid, size: 22),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                kDomainLabels[question.domain] ?? question.domain,
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(color: kTealMid, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(question.question,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w600, height: 1.35)),
        const SizedBox(height: 16),
        for (var i = 0; i < question.options.length; i++) ...[
          _OptionTile(
            text: question.options[i],
            state: _optionState(i, showFeedback),
            // Lock the answer once feedback is shown - no answer-shopping.
            onTap: showFeedback ? null : () => onSelect(i),
          ),
          const SizedBox(height: 10),
        ],
        if (showFeedback) ...[
          const SizedBox(height: 4),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: dark ? kCardDark : kTealPale,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(question.explanation,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.4)),
          ),
        ],
      ],
    );
  }

  _OptionState _optionState(int index, bool showFeedback) {
    if (!showFeedback) {
      return selectedIndex == index ? _OptionState.selected : _OptionState.idle;
    }
    if (index == question.correctIndex) return _OptionState.correct;
    if (index == selectedIndex) return _OptionState.wrong;
    return _OptionState.idle;
  }
}

enum _OptionState { idle, selected, correct, wrong }

class _OptionTile extends StatelessWidget {
  const _OptionTile({required this.text, required this.state, this.onTap});

  final String text;
  final _OptionState state;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final (Color border, Color fill, IconData? icon) = switch (state) {
      _OptionState.selected => (kTealMid, dark ? kCardDark : kTealPale, null),
      _OptionState.correct => (kTier3, kTier3Bg, Icons.check_circle),
      _OptionState.wrong => (kTier1, kTier1Bg, Icons.cancel),
      _OptionState.idle => (
          dark ? kBorderDark : kBorderLight,
          dark ? kSurfaceDark : kCardLight,
          null
        ),
    };
    // Feedback tiles use fixed light backgrounds → fixed dark text for contrast.
    final feedbackText = state == _OptionState.correct || state == _OptionState.wrong;

    return Material(
      color: fill,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          decoration: BoxDecoration(
            border: Border.all(color: border, width: 1.5),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  text,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        height: 1.3,
                        color: feedbackText ? kTextPrimaryLight : null,
                      ),
                ),
              ),
              if (icon != null)
                Icon(icon,
                    size: 20,
                    color: state == _OptionState.correct ? kTier3 : kTier1),
            ],
          ),
        ),
      ),
    );
  }
}

/// Animated ring showing percent correct.
class ScoreRing extends StatelessWidget {
  const ScoreRing({super.key, required this.percent, this.size = 128});

  final double percent;
  final double size;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: percent / 100),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutCubic,
      builder: (context, value, _) => SizedBox(
        width: size,
        height: size,
        child: Stack(
          fit: StackFit.expand,
          alignment: Alignment.center,
          children: [
            CircularProgressIndicator(
              value: value,
              strokeWidth: 10,
              backgroundColor: kTealPale,
              valueColor: AlwaysStoppedAnimation(
                percent >= 80
                    ? kTier3
                    : percent >= 50
                        ? kTealMid
                        : kTier2,
              ),
            ),
            Center(
              child: Text(
                '${(value * 100).round()}%',
                style: Theme.of(context)
                    .textTheme
                    .headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Per-domain result chips - green when fully correct, amber otherwise.
class DomainChips extends StatelessWidget {
  const DomainChips({super.key, required this.result});

  final QuizScoreResult result;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final e in result.domainScores.entries)
          Chip(
            avatar: Icon(
              kDomainIcons[e.key] ?? Icons.quiz_outlined,
              size: 16,
              color: e.value['correct'] == e.value['total'] ? kTier3 : kTier2,
            ),
            label: Text(
              '${kDomainLabels[e.key] ?? e.key}  '
              '${e.value['correct']}/${e.value['total']}',
              style: const TextStyle(fontSize: 12.5),
            ),
            side: BorderSide(
              color: e.value['correct'] == e.value['total'] ? kTier3 : kTier2,
            ),
            backgroundColor:
                e.value['correct'] == e.value['total'] ? kTier3Bg : kTier2Bg,
            labelStyle: const TextStyle(color: kTextPrimaryLight),
          ),
      ],
    );
  }
}

/// "Your understanding went up X points" banner with a gentle pop-in.
class LiftBanner extends StatelessWidget {
  const LiftBanner({super.key, required this.prePercent, required this.postPercent});

  final double prePercent;
  final double postPercent;

  @override
  Widget build(BuildContext context) {
    final lift = postPercent - prePercent;
    final improved = lift > 0;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.85, end: 1),
      duration: const Duration(milliseconds: 500),
      curve: Curves.elasticOut,
      builder: (context, scale, child) =>
          Transform.scale(scale: scale, child: child),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: improved ? kTier3Bg : kTier2Bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: improved ? kTier3 : kTier2, width: 1.5),
        ),
        child: Column(
          children: [
            Icon(improved ? Icons.trending_up : Icons.flag_outlined,
                color: improved ? kTier3 : kTier2, size: 30),
            const SizedBox(height: 6),
            Text(
              improved
                  ? 'Your understanding went up ${lift.round()} points!'
                  : 'Let\'s review the tricky parts together.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: kTextPrimaryLight),
            ),
            const SizedBox(height: 4),
            Text(
              'Before: ${prePercent.round()}%   →   After: ${postPercent.round()}%',
              style: const TextStyle(fontSize: 13.5, color: kTextPrimaryLight),
            ),
          ],
        ),
      ),
    );
  }
}
