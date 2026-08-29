/// widgets/quiz_review.dart
///
/// Per-question review shown on the quiz results screen: what was asked, what
/// the patient chose, the right answer when they missed it, and why.
///
/// LOF review action item, 26 Aug 2026 (John Trzesniak): the mental model of
/// users taking quizzes should include detailed feedback per question after
/// completion, to improve learning.
///
/// The results screen already showed a score, an XP chip, a comprehension-lift
/// banner and mastery badges by topic. All of that tells a patient HOW MUCH
/// they got right. None of it tells them WHICH thing they misunderstood, and
/// that is the only part with any teaching value.
///
/// Deliberately kept out of the quiz flow itself. Feedback during the baseline
/// round would teach mid-measurement and destroy the pre/post comparison; the
/// whole design depends on the first round being silent.
library;

import 'package:dischargeiq_mobile/models/quiz.dart';
import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

/// One question, the patient's answer, and whether it was right.
class QuizReviewItem {
  const QuizReviewItem({
    required this.question,
    required this.chosenIndex,
    required this.wasAnswered,
  });

  final QuizQuestion question;

  /// Index the patient picked, or -1 when they skipped it.
  final int chosenIndex;

  /// False when the question was never answered, which reads differently from
  /// getting it wrong and is shown differently.
  final bool wasAnswered;

  bool get isCorrect => wasAnswered && chosenIndex == question.correctIndex;
}

/// Build the review list from the questions and the recorded answers.
///
/// A mastery round only re-asks the missed questions, so answers can be
/// shorter than the question list; anything without a recorded answer is
/// reported as unanswered rather than silently counted wrong.
List<QuizReviewItem> buildReviewItems(
  List<QuizQuestion> questions,
  List<int?> answers,
) {
  return [
    for (var i = 0; i < questions.length; i++)
      QuizReviewItem(
        question: questions[i],
        chosenIndex: i < answers.length ? (answers[i] ?? -1) : -1,
        wasAnswered: i < answers.length && answers[i] != null && answers[i]! >= 0,
      ),
  ];
}

/// Expandable per-question breakdown.
///
/// Missed questions are expanded by default and correct ones are collapsed.
/// A patient who scored well should not have to scroll past six green ticks to
/// reach the one thing they got wrong, and a patient who scored badly should
/// not have to tap six times to find out why.
class QuizReviewList extends StatelessWidget {
  const QuizReviewList({super.key, required this.items});

  final List<QuizReviewItem> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    final missed = items.where((i) => !i.isCorrect).length;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Question by question',
          style: Theme.of(context)
              .textTheme
              .titleSmall
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(
          missed == 0
              ? 'You got every question right. The answers are here if you want to read them again.'
              : missed == 1
                  ? 'One to look at again. It is open below.'
                  : '$missed to look at again. They are open below.',
          style: TextStyle(
            fontSize: 13,
            height: 1.35,
            color: dark ? kTextSecondaryDark : kTextSecondaryLight,
          ),
        ),
        const SizedBox(height: 10),
        for (var i = 0; i < items.length; i++)
          _ReviewTile(index: i, item: items[i], dark: dark),
      ],
    );
  }
}

class _ReviewTile extends StatelessWidget {
  const _ReviewTile({
    required this.index,
    required this.item,
    required this.dark,
  });

  final int index;
  final QuizReviewItem item;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final correct = item.isCorrect;
    // Never red. A patient who misunderstood their discharge instructions is
    // not being marked down - the point is to close the gap, not to score
    // them. Amber reads as "look here", red reads as failure.
    final accent = correct ? kTier3 : kMedChanged;
    final q = item.question;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: dark ? kCardDark : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accent.withValues(alpha: 0.35)),
      ),
      child: Theme(
        // Remove the default divider lines so the card reads as one block.
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: !correct,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: Icon(
            correct ? Icons.check_circle_outline : Icons.lightbulb_outline,
            color: accent,
          ),
          title: Text(
            q.question,
            style: TextStyle(
              fontSize: 14,
              height: 1.35,
              fontWeight: FontWeight.w600,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          subtitle: Text(
            correct ? 'You got this right' : 'Worth another look',
            style: TextStyle(fontSize: 12.5, color: accent),
          ),
          children: [
            if (!item.wasAnswered)
              _line(context, 'You skipped this one.', italic: true)
            else if (!correct)
              _line(
                context,
                'You chose: ${_optionAt(q, item.chosenIndex)}',
              ),
            // The right answer is always shown, including when they got it
            // right: re-reading the correct statement is the cheapest possible
            // reinforcement, and hiding it would make a perfect score
            // unreviewable.
            const SizedBox(height: 6),
            _line(
              context,
              'Correct answer: ${_optionAt(q, q.correctIndex)}',
              bold: true,
            ),
            if (q.explanation.trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: dark ? 0.12 : 0.08),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  q.explanation,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Option text by index, tolerant of an out-of-range index rather than
  /// throwing inside a results screen the patient has already earned.
  static String _optionAt(QuizQuestion q, int i) =>
      (i >= 0 && i < q.options.length) ? q.options[i] : 'not recorded';

  Widget _line(BuildContext context, String text,
      {bool bold = false, bool italic = false}) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        text,
        style: TextStyle(
          fontSize: 13.5,
          height: 1.35,
          fontWeight: bold ? FontWeight.w600 : FontWeight.w400,
          fontStyle: italic ? FontStyle.italic : FontStyle.normal,
          color: dark ? kTextPrimaryDark : kTextPrimaryLight,
        ),
      ),
    );
  }
}
