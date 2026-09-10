/// Every medication on a document reaches the screen.
///
/// The Medications tab used to collapse after five entries behind a "Show
/// all" toggle, on CDC plain-language guidance about how many items a reader
/// with limited health literacy can process at once. That guidance is about
/// absorbing comparable items in a single pass, not about a reference list a
/// patient scrolls and returns to, and the collapse bought a cosmetic
/// improvement with a safety cost: 30% of the corpus carries more than five
/// medications (worst case 23), so roughly a third of patients could close
/// the app never knowing the later ones existed.
///
/// Nothing failed when that shipped. The tab rendered, the data was correct,
/// the list was simply shorter than the prescription. That is why this test
/// asserts on the LAST medication rather than on a count: a cap of any size
/// hides the tail, and the tail is where the newly-prescribed drugs sit.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/results_screen.dart';
import 'package:dischargeiq_mobile/services/case_audio_player.dart';

/// A result carrying [count] distinctly-named medications.
///
/// Names are deliberately not real drugs: the assertion is about list
/// plumbing, and a fake name cannot collide with prose elsewhere on the tab
/// and pass by accident.
Map<String, dynamic> _resultWith(int count) => {
      'pipeline_status': 'complete',
      'extraction': {
        'primary_diagnosis': 'Heart failure',
        'medications': [
          for (var i = 1; i <= count; i++)
            {'name': 'Medicine$i', 'dose': '$i mg', 'frequency': 'daily'},
        ],
        'follow_up_appointments': [],
        'red_flag_symptoms': [],
      },
      'diagnosis_explanation': 'Your heart was not pumping well.',
      'medication_rationale': '',
      'recovery_trajectory': '',
      'escalation_guide': '',
    };

Future<void> _openMedicationsTab(WidgetTester tester, int medCount) async {
  final discharge = DischargeProvider()..setResult(_resultWith(medCount));
  await tester.pumpWidget(MultiProvider(
    providers: [
      ChangeNotifierProvider<DischargeProvider>.value(value: discharge),
      ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
      ChangeNotifierProvider<CaseAudioPlayer>(create: (_) => CaseAudioPlayer()),
    ],
    child: const MaterialApp(home: ResultsScreen()),
  ));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Medications').first);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a long medication list shows its last entry without a tap',
      (tester) async {
    // Taller than a phone so the list is not merely off-screen; scrolling is
    // a separate concern from hiding, and this test is about hiding.
    tester.view.physicalSize = const Size(1200, 6000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await _openMedicationsTab(tester, 12);

    expect(find.text('Medicine1'), findsOneWidget);
    expect(find.text('Medicine12'), findsOneWidget,
        reason: 'the twelfth medicine is a real prescription, not overflow');
  });

  testWidgets('no control offers to reveal hidden medicines', (tester) async {
    tester.view.physicalSize = const Size(1200, 6000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await _openMedicationsTab(tester, 12);

    // Guards the regression directly: any reinstated cap has to advertise
    // itself with a control like this one.
    expect(find.textContaining('Show all'), findsNothing);
    expect(find.textContaining('Show fewer'), findsNothing);
  });
}
