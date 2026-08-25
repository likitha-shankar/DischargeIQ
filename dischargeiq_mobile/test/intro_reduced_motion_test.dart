/// Tests that the landing intro honours the OS reduced-motion setting.
///
/// The intro is a nine second branding animation carrying no information.
/// Users who enable Reduce Motion (iOS Settings > Accessibility > Motion, or
/// Android "Remove animations") often do so because motion causes nausea or
/// vertigo, and this app's readers are unwell before they open it. Suppressing
/// the intro for them costs nothing, because there is nothing in it to miss.
///
/// The August 2026 accessibility pass covered contrast, text scaling and
/// screen-reader headings but missed motion entirely, which is why this test
/// exists rather than relying on the fix staying put.

import 'package:dischargeiq_mobile/screens/intro_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Wrap the intro in a MediaQuery with an explicit disableAnimations value.
Widget _harness({required bool disableAnimations, required VoidCallback onDone}) {
  return MediaQuery(
    data: MediaQueryData(disableAnimations: disableAnimations),
    child: MaterialApp(home: IntroScreen(onDone: onDone)),
  );
}

void main() {
  testWidgets('reduced motion finishes immediately without animating',
      (tester) async {
    var doneCalls = 0;
    await tester.pumpWidget(
      _harness(disableAnimations: true, onDone: () => doneCalls++),
    );

    // One frame is enough: the post-frame callback should have advanced past
    // the intro rather than starting a nine second timeline.
    await tester.pump();
    expect(doneCalls, 1);

    // Nothing from the animated tree should ever have been built. "Skip" is
    // part of the cinematic, so its absence proves the still frame rendered.
    expect(find.text('Skip'), findsNothing);
  });

  testWidgets('reduced motion leaves no pending timers', (tester) async {
    // A leaked periodic timer (the caret blink) would fail the test binding
    // here, which is the point: the caret must never start under reduce motion.
    await tester.pumpWidget(
      _harness(disableAnimations: true, onDone: () {}),
    );
    await tester.pump();
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('normal motion still plays the full intro', (tester) async {
    var doneCalls = 0;
    await tester.pumpWidget(
      _harness(disableAnimations: false, onDone: () => doneCalls++),
    );
    await tester.pump();

    // The intro must NOT have completed after one frame.
    expect(doneCalls, 0);

    // Advance past the full 9.1s timeline and confirm it completes exactly
    // once. This also guards the fix against silently disabling the intro for
    // everybody, which would be the easy way to "pass" the test above.
    await tester.pump(const Duration(milliseconds: 9200));
    expect(doneCalls, 1);

    // Settle remaining exit animations so the binding ends clean.
    await tester.pumpAndSettle();
  });
}
