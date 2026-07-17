/// Widget tests for PatientText (results_screen.dart) - the single renderer
/// for all agent narrative text. Raw markdown symbols must never reach the
/// patient: headings render styled without '#', stray '**' markers are
/// stripped, bullets keep their text.
library;

import 'package:dischargeiq_mobile/screens/results_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, String text) => tester.pumpWidget(
      MaterialApp(home: Scaffold(body: PatientText(text: text))),
    );

void main() {
  testWidgets('markdown headings render without # symbols', (tester) async {
    await _pump(tester,
        '# Your Hospital Stay\n## Why This Happened\nBody line here.');
    expect(find.text('Your Hospital Stay'), findsOneWidget);
    expect(find.text('Why This Happened'), findsOneWidget);
    expect(find.textContaining('#'), findsNothing);
  });

  testWidgets('stray-asterisk heading lines lose their markers',
      (tester) async {
    await _pump(tester, '*When to expect improvement:**\nHealing takes time.');
    expect(find.text('When to expect improvement'), findsOneWidget);
    expect(find.textContaining('*'), findsNothing);
  });

  testWidgets('unbalanced ** inside a line is stripped, not shown',
      (tester) async {
    await _pump(tester, 'Call your doctor **right away if dizzy.');
    expect(
        find.textContaining('Call your doctor right away'), findsOneWidget);
    expect(find.textContaining('**'), findsNothing);
  });

  testWidgets('bullets and balanced bold still render', (tester) async {
    await _pump(tester, '- **Rest** at home for 3 days.');
    expect(find.textContaining('at home for 3 days'), findsOneWidget);
  });
}
