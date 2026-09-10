/// The "How it works" screen, held to the same bar as the agents it explains.
///
/// The version this replaced measured Flesch-Kincaid 6.9. Every agent output
/// is gated at 6.0 by hard rule 4, and the one screen whose entire job is
/// explaining the product to a patient was exempt because nothing was
/// checking it. That is the gap these tests close.
///
/// The content assertions matter as much as the readability one: a help
/// screen that omits "this can be wrong" or "your notes stay on the phone"
/// is not merely thin, it withholds the two things a patient most needs.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dischargeiq_mobile/screens/how_it_works_screen.dart';

Future<void> _pump(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1200, 6000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(const MaterialApp(home: HowItWorksScreen()));
  await tester.pumpAndSettle();
}

/// Every visible string on the screen, joined.
String _visibleText(WidgetTester tester) => tester
    .widgetList<Text>(find.byType(Text))
    .map((t) => t.data ?? '')
    .join(' ');

void main() {
  group('the promises a patient needs are actually made', () {
    testWidgets('it says the app can be wrong', (tester) async {
      await _pump(tester);
      expect(_visibleText(tester), contains('can be wrong'));
    });

    testWidgets('it says notes stay on the phone', (tester) async {
      await _pump(tester);
      expect(_visibleText(tester).toLowerCase(), contains('stay on this phone'));
    });

    testWidgets('it says the app never changes a medicine', (tester) async {
      // Hard rule 2, stated to the patient rather than only enforced in code.
      await _pump(tester);
      expect(_visibleText(tester).toLowerCase(),
          contains('never tell you to stop or change a medicine'));
    });

    testWidgets('it says the document is the only source', (tester) async {
      await _pump(tester);
      expect(_visibleText(tester).toLowerCase(), contains('only source'));
    });

    testWidgets('it points at a control that really exists', (tester) async {
      // "See where this comes from" is the exact SourceQuote chip label. An
      // instruction naming something the reader cannot find is worse than no
      // instruction.
      await _pump(tester);
      expect(_visibleText(tester), contains('See where this comes from'));
    });
  });

  group('it does not describe the system to itself', () {
    testWidgets('no internal agent names leak to the patient', (tester) async {
      await _pump(tester);
      final text = _visibleText(tester).toLowerCase();
      for (final jargon in ['agent 1', 'agent 6', 'extraction:', 'pipeline',
                            'simulates a confused patient', 'llm']) {
        expect(text, isNot(contains(jargon)), reason: 'leaked: $jargon');
      }
    });
  });

  group('readability', () {
    testWidgets('sentences stay short', (tester) async {
      // A proxy for the Flesch-Kincaid gate, which needs textstat and so
      // lives on the Python side. Measured there at 1.8 for this copy; this
      // catches the drift that would push it back up.
      await _pump(tester);
      final long = <String>[];
      for (final sentence in _visibleText(tester).split(RegExp(r'[.!?]'))) {
        final words = sentence.trim().split(RegExp(r'\s+'))
            .where((w) => w.isNotEmpty).length;
        if (words > 20) long.add(sentence.trim());
      }
      expect(long, isEmpty, reason: 'sentences over 20 words: $long');
    });
  });
}
