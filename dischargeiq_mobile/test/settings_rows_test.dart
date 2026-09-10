/// What Settings offers, and what it must not.
///
/// "Watch the intro again" was raised as pointless on 25 Aug 2026, queued in
/// docs/ISSUES_AND_IDEAS.md, held back until after the 26 Aug demo, and then
/// forgotten for two weeks - the deferral outlived its reason and nothing was
/// watching. This test is what stops that recurring.
///
/// The substantive objection: nobody replays a nine-second logo animation,
/// and the row sat directly beneath "Guided tour", which is the thing a lost
/// patient actually wants. Two adjacent rows that look like siblings, one
/// useful and one not.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';

Future<void> _pump(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1200, 5000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MultiProvider(
    providers: [
      ChangeNotifierProvider<DischargeProvider>(create: (_) => DischargeProvider()),
      ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
    ],
    child: const MaterialApp(home: SettingsScreen()),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the intro replay row is gone', (tester) async {
    await _pump(tester);
    expect(find.text('Watch the intro again'), findsNothing);
    expect(find.text('The short welcome animation'), findsNothing);
  });

  testWidgets('the guided tour survives', (tester) async {
    // The row the intro replay was competing with. Removing the wrong one of
    // the two would be a quiet downgrade: the tour is the only in-app help a
    // patient who is lost can reach.
    await _pump(tester);
    expect(find.text('Guided tour'), findsOneWidget);
  });

  testWidgets('the rows that carry obligations are still present',
      (tester) async {
    await _pump(tester);
    // Licences and the disclaimer are not preferences; they are things the
    // product has to show. A settings tidy-up must never take them with it.
    expect(find.text('Open source licences'), findsOneWidget);
    expect(find.text('Disclaimer'), findsOneWidget);
  });
}
