/// widgets/quiz_widgets.dart
///
/// Reusable visual pieces for the teach-back quiz flow (Sprint 3):
/// question card with tappable options, step progress bar, animated score
/// ring, the comprehension-lift banner, the answer-streak chip, and the
/// milestone confetti overlay. Game-layer widgets (XP bar, mastery badges)
/// live in game_widgets.dart. Pure presentation - all state lives in QuizScreen.
///
/// Game-design notes (from patient-education gamification research):
/// celebrations are GATED to milestones (improved score, perfect score) so
/// they stay rare and meaningful; feedback is instant and non-punitive; no
/// timers or speed scoring, which pressure older or unwell patients.
library;

import 'dart:math' show Random, pi, sin;

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
          if (selectedIndex == question.correctIndex) ...[
            const SizedBox(height: 4),
            Row(children: [
              const Icon(Icons.star_rounded, size: 18, color: kTier3),
              const SizedBox(width: 6),
              Text(
                // Deterministic per question so rebuilds don't reshuffle praise.
                _kPraise[question.question.hashCode.abs() % _kPraise.length],
                style: const TextStyle(
                    fontWeight: FontWeight.w700, color: kTier3, fontSize: 14),
              ),
            ]),
            const SizedBox(height: 8),
          ] else
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

// Short, 5th-grade-level praise lines for correct post-quiz answers.
const _kPraise = [
  'You got it!',
  'Nice work!',
  "That's right!",
  'Great memory!',
  'Well done!',
];

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

/// "N in a row!" chip shown during the post quiz for 2+ consecutive correct
/// answers. Pops in with a gentle scale; accuracy-based, never speed-based.
class StreakChip extends StatelessWidget {
  const StreakChip({super.key, required this.streak});

  final int streak;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      // A new streak value re-triggers the pop via the key.
      key: ValueKey(streak),
      tween: Tween(begin: 0.6, end: 1),
      duration: const Duration(milliseconds: 450),
      curve: Curves.elasticOut,
      builder: (context, scale, child) =>
          Transform.scale(scale: scale, child: child),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: kTier3Bg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: kTier3, width: 1.2),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.local_fire_department_rounded,
                size: 18, color: kTier3),
            const SizedBox(width: 5),
            Text(
              '$streak in a row!',
              style: const TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                  color: kTextPrimaryLight),
            ),
          ],
        ),
      ),
    );
  }
}

/// One falling confetti piece: spawn column, sway, spin, color, size, delay.
class _ConfettiPiece {
  _ConfettiPiece(Random rng)
      : x = rng.nextDouble(),
        delay = rng.nextDouble() * 0.35,
        sway = 0.02 + rng.nextDouble() * 0.05,
        swaySpeed = 2 + rng.nextDouble() * 3,
        size = 5 + rng.nextDouble() * 5,
        spin = (rng.nextDouble() - 0.5) * 8,
        color = _palette[rng.nextInt(_palette.length)];

  static const _palette = [kTealMid, kTealLight, kTier3, kTier2, kMedNew];

  final double x, delay, sway, swaySpeed, size, spin;
  final Color color;
}

class _ConfettiPainter extends CustomPainter {
  _ConfettiPainter(this.pieces, this.t);

  final List<_ConfettiPiece> pieces;
  final double t; // 0..1 animation progress

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();
    for (final p in pieces) {
      final local = ((t - p.delay) / (1 - p.delay)).clamp(0.0, 1.0);
      if (local == 0) continue;
      // Ease-in fall from above the top edge to below the bottom edge.
      final y = (local * local * 0.7 + local * 0.5) * (size.height + 40) - 20;
      final x =
          (p.x + sin(local * p.swaySpeed * pi) * p.sway) * size.width;
      // Fade out over the last quarter of the fall.
      paint.color = p.color.withValues(alpha: (1 - local) < 0.25 ? (1 - local) * 4 : 1);
      canvas.save();
      canvas.translate(x, y);
      canvas.rotate(local * p.spin);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromCenter(
                center: Offset.zero, width: p.size, height: p.size * 0.6),
            const Radius.circular(2)),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter old) => old.t != t;
}

/// One-shot confetti overlay for milestone celebrations. Plays once on mount
/// and fades itself out; wrap in Positioned.fill inside a Stack.
class ConfettiBurst extends StatefulWidget {
  const ConfettiBurst({super.key, this.pieces = 60});

  final int pieces;

  @override
  State<ConfettiBurst> createState() => _ConfettiBurstState();
}

class _ConfettiBurstState extends State<ConfettiBurst>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 2400))
    ..forward();
  late final List<_ConfettiPiece> _pieces =
      List.generate(widget.pieces, (_) => _ConfettiPiece(Random()));

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (_, __) => _controller.isCompleted
            ? const SizedBox.shrink()
            : CustomPaint(
                painter: _ConfettiPainter(_pieces, _controller.value),
                size: Size.infinite,
              ),
      ),
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
