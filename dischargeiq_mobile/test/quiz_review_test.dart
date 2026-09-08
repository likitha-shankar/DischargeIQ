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
import 'package:flutter/material.dart';
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

  group('the results sheet', _sheetTests);
}

/// Widget-level behaviour of the results sheet itself.
///
/// The sheet is what a patient sees the moment a round ends, so these cover
/// the two things that were wrong before: the round ended by changing the
/// subject to learning cards without ever saying how they did, and the sheet
/// showed "You chose" only on wrong answers - which reads as if the right
/// ones were never recorded.
void _sheetTests() {
  QuizQuestion q(String text, {int correct = 0}) => QuizQuestion(
        question: text,
        options: const ['Option A', 'Option B', 'Option C'],
        correctIndex: correct,
        domain: 'medications',
        explanation: 'Because of the reason.',
      );

  Future<void> pump(WidgetTester t, List<QuizReviewItem> items,
          {void Function(QuizReviewItem)? onLearn}) =>
      t.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: QuizReviewList(items: items, onLearn: onLearn),
          ),
        ),
      ));

  testWidgets('a right answer still shows what the patient chose',
      (t) async {
    await pump(t, buildReviewItems([q('Which pill is for your heart?')], [0]));
    // Correct rows start collapsed, so open it first.
    await t.tap(find.textContaining('Which pill'));
    await t.pumpAndSettle();
    expect(find.textContaining('You chose: Option A'), findsOneWidget);
    expect(find.textContaining('Correct answer: Option A'), findsOneWidget);
  });

  testWidgets('a wrong answer shows both the choice and the right answer',
      (t) async {
    await pump(t, buildReviewItems([q('Which pill is for your heart?')], [2]));
    // Missed rows are expanded already - that is the point of the sheet.
    expect(find.textContaining('You chose: Option C'), findsOneWidget);
    expect(find.textContaining('Correct answer: Option A'), findsOneWidget);
  });

  testWidgets('questions are numbered so they can be referred to', (t) async {
    await pump(
        t, buildReviewItems([q('First one'), q('Second one')], [0, 1]));
    expect(find.textContaining('1. First one'), findsOneWidget);
    expect(find.textContaining('2. Second one'), findsOneWidget);
  });

  testWidgets('the learning card button appears and reports its question',
      (t) async {
    QuizReviewItem? tapped;
    await pump(t, buildReviewItems([q('Which pill?')], [2]),
        onLearn: (item) => tapped = item);
    await t.tap(find.text('Read the learning card'));
    await t.pumpAndSettle();
    expect(tapped, isNotNull);
    expect(tapped!.question.domain, 'medications');
  });

  testWidgets('no learning-card hook means no button', (t) async {
    await pump(t, buildReviewItems([q('Which pill?')], [2]));
    expect(find.text('Read the learning card'), findsNothing);
  });

  testWidgets('a skipped question says so rather than claiming a choice',
      (t) async {
    await pump(t, buildReviewItems([q('Which pill?')], [null]));
    expect(find.textContaining('You skipped this one'), findsOneWidget);
    expect(find.textContaining('You chose:'), findsNothing);
  });
}
