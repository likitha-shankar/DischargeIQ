/// The licence summary must summarise without shortening the record.
///
/// The risk in this screen is not a layout bug. It is that a page whose job
/// is legal attribution gets "tidied" into one that no longer discharges the
/// obligation - MIT, BSD-3-Clause and Apache-2.0 each require the notice to
/// travel with the distribution, so the complete list has to stay reachable.
///
/// These tests pin the two halves of that: the summary is short, and the way
/// through to everything else is still there.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dischargeiq_mobile/screens/licences_screen.dart';

Future<void> _pump(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(const MaterialApp(home: LicencesScreen()));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the summary names both halves of the product', (tester) async {
    await _pump(tester);
    // A licence page that lists only the mobile packages looks complete while
    // omitting the service that does the analysis.
    expect(find.text('IN THE APP'), findsOneWidget);
    expect(find.text('IN THE ANALYSIS SERVICE'), findsOneWidget);
    expect(find.text('Flutter'), findsOneWidget);
    expect(find.text('FastAPI'), findsOneWidget);
    expect(find.text('pdfplumber'), findsOneWidget);
  });

  testWidgets('the complete list is still one tap away', (tester) async {
    await _pump(tester);
    expect(find.text('View all licences'), findsOneWidget);

    await tester.tap(find.text('View all licences'));
    await tester.pumpAndSettle();
    // Flutter's generated page, which carries every package and its text.
    expect(find.byType(LicensePage), findsOneWidget);
  });

  testWidgets('the summary says it is a summary', (tester) async {
    await _pump(tester);
    // Without this line the short list reads as the whole list, which is
    // the misleading version of this page rather than the concise one.
    expect(find.textContaining('full list'), findsOneWidget);
  });

  testWidgets('the project states its own licence', (tester) async {
    await _pump(tester);
    expect(find.textContaining('Apache License 2.0'), findsOneWidget);
  });
}
