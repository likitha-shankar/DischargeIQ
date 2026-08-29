// Tests for the per-question quiz review (LOF action item, 26 Aug 2026).
//
// The logic under test is small but the failure modes are not cosmetic. This
// screen tells a patient which discharge instruction they misunderstood, so
// mislabelling an answer teaches them the wrong thing with the app's
// authority behind it.
//
// Two cases matter most and neither is the happy path:
//   - a SKIPPED question must not read as a wrong answer, because "you chose"
//     followed by an option they never picked is simply false;
//   - a mastery round re-asks only the missed questions, so the answers list
//     is legitimately shorter than the question list and must not throw or
//     silently mark the remainder wrong.

import 'package:dischargeiq_mobile/models/quiz.dart';
import 'package:dischargeiq_mobile/widgets/quiz_review.dart';
import 'package:flutter_test/flutter_test.dart';

QuizQuestion _q(String text, {int correct = 0, String explanation = 'because'}) =>
    QuizQuestion(
      question: text,
      options: const ['option A', 'option B', 'option C'],
      correctIndex: correct,
      domain: 'medications',
      explanation: explanation,
    );

void main() {
  group('buildReviewItems', () {
    test('marks a correct answer correct', () {
      final items = buildReviewItems([_q('Q1', correct: 1)], [1]);
      expect(items.single.isCorrect, isTrue);
      expect(items.single.wasAnswered, isTrue);
      expect(items.single.chosenIndex, 1);
    });

    test('marks a wrong answer incorrect and keeps what was chosen', () {
      final items = buildReviewItems([_q('Q1', correct: 1)], [2]);
      expect(items.single.isCorrect, isFalse);
      expect(items.single.wasAnswered, isTrue);
      // The chosen index has to survive, or the review cannot say "you chose".
      expect(items.single.chosenIndex, 2);
    });

    test('a skipped question is unanswered, not wrong-with-an-answer', () {
      // Telling a patient "you chose option A" when they chose nothing is a
      // false statement, and the UI branches on wasAnswered to avoid it.
      final items = buildReviewItems([_q('Q1', correct: 0)], [null]);
      expect(items.single.wasAnswered, isFalse);
      expect(items.single.isCorrect, isFalse);
    });

    test('a -1 sentinel answer counts as skipped', () {
      // The scoring path converts nulls to -1 before sending to the server;
      // both shapes reach this function depending on the caller.
      final items = buildReviewItems([_q('Q1', correct: 0)], [-1]);
      expect(items.single.wasAnswered, isFalse);
      expect(items.single.isCorrect, isFalse);
    });

    test('a correct index of 0 is not treated as unanswered', () {
      // Guards the obvious falsy-zero bug: option A is a real answer.
      final items = buildReviewItems([_q('Q1', correct: 0)], [0]);
      expect(items.single.wasAnswered, isTrue);
      expect(items.single.isCorrect, isTrue);
    });

    test('a short answers list does not throw and reports the rest skipped', () {
      // A mastery round re-asks only the missed questions.
      final questions = [_q('Q1'), _q('Q2'), _q('Q3')];
      final items = buildReviewItems(questions, [0]);
      expect(items, hasLength(3));
      expect(items[0].wasAnswered, isTrue);
      expect(items[1].wasAnswered, isFalse);
      expect(items[2].wasAnswered, isFalse);
    });

    test('no questions yields no items', () {
      expect(buildReviewItems([], []), isEmpty);
    });

    test('preserves order so the review matches the quiz', () {
      final questions = [_q('First'), _q('Second'), _q('Third')];
      final items = buildReviewItems(questions, [0, 1, 2]);
      expect([for (final i in items) i.question.question],
          ['First', 'Second', 'Third']);
    });
  });
}
