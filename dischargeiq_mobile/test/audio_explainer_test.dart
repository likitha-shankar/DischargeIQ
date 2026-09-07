/// Widget tests for the audio explainer card - the tap path itself.
///
/// These exist because the per-case explainer shipped broken once already, in
/// the least visible way possible: the backend was healthy, enabled and
/// reachable, and the client simply never called it. Nothing failed. There
/// was no error to see. The button just played the wrong thing.
///
/// So the assertions here are about WHICH audio a tap requests, and about the
/// card refusing to promise audio it cannot deliver. A release build on a
/// real phone strips Dart logging, so this is the only place the tap path
/// gets observed at all.
///
/// Note the split: presence is asserted on the LABEL, taps go to the button's
/// Key. Both rows render a play triangle, so finding a tap target by icon
/// would be ambiguous in exactly the place precision matters.

library;

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dischargeiq_mobile/services/case_audio_player.dart';
import 'package:dischargeiq_mobile/widgets/audio_explainer.dart';

/// Minimal valid WAV: 44-byte RIFF header, no samples. Enough for the card,
/// which only ever hands the bytes to the player.
Uint8List _wav() {
  final b = BytesBuilder()
    ..add('RIFF'.codeUnits)
    ..add([36, 0, 0, 0])
    ..add('WAVEfmt '.codeUnits)
    ..add([16, 0, 0, 0, 1, 0, 1, 0])
    ..add([0x40, 0x1F, 0, 0, 0x80, 0x3E, 0, 0, 2, 0, 16, 0])
    ..add('data'.codeUnits)
    ..add([0, 0, 0, 0]);
  return b.toBytes();
}

const _payload = {
  'extraction': {'primary_diagnosis': 'Heart failure'},
  'diagnosis_explanation': 'Your heart was not pumping well.',
};

/// Pump the card with stubbed IO. [hasGeneric] drives the HEAD probe for the
/// per-condition recording; [fetcher] stands in for the generation call.
Future<void> _pump(
  WidgetTester tester, {
  String documentType = 'heart_failure',
  String sessionId = 'sess-1',
  Map<String, dynamic> payload = _payload,
  bool hasGeneric = true,
  Future<Uint8List?> Function(String, Map<String, dynamic>)? fetcher,
}) async {
  await tester.pumpWidget(
    ChangeNotifierProvider<CaseAudioPlayer>(
      create: (_) => CaseAudioPlayer(),
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: AudioExplainerCard(
              documentType: documentType,
              sessionId: sessionId,
              pipelinePayload: payload,
              probeMedia: (_) async => hasGeneric,
              caseAudioFetcher:
                  fetcher ?? (_, __) async => _wav(),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  group('the card offers the patient their own summary', () {
    testWidgets('the per-case row is present when a session and payload exist',
        (tester) async {
      await _pump(tester);
      expect(find.text('Listen to YOUR summary'), findsOneWidget);
    });

    testWidgets('tapping it requests audio for THIS session and payload',
        (tester) async {
      // The regression that shipped: the tap fetched a per-condition file and
      // the patient's own document was never involved.
      String? sawSession;
      Map<String, dynamic>? sawPayload;
      await _pump(tester, fetcher: (sid, payload) async {
        sawSession = sid;
        sawPayload = payload;
        return _wav();
      });
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pump();
      expect(sawSession, 'sess-1');
      expect(sawPayload?['extraction'], isNotNull);
    });

    testWidgets('a second tap does not regenerate - the bytes are cached',
        (tester) async {
      // The endpoint's stated contract: generation is a script LLM call plus
      // TTS, so repeated presses of play must not re-post.
      var calls = 0;
      await _pump(tester, fetcher: (_, __) async {
        calls++;
        return _wav();
      });
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pumpAndSettle();
      expect(calls, 1);
    });
  });

  group('the card does not promise audio it cannot deliver', () {
    testWidgets('a failed generation stops offering the row', (tester) async {
      await _pump(tester, hasGeneric: false, fetcher: (_, __) async => null);
      expect(find.text('Listen to YOUR summary'), findsOneWidget);
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pumpAndSettle();
      expect(
        find.text('Listen to YOUR summary'),
        findsNothing,
        reason: 'a button that will not work should stop being offered',
      );
    });

    testWidgets('no session id means no per-case row', (tester) async {
      await _pump(tester, sessionId: '');
      expect(find.text('Listen to YOUR summary'), findsNothing);
    });

    testWidgets('an empty payload means no per-case row', (tester) async {
      await _pump(tester, payload: const {});
      expect(find.text('Listen to YOUR summary'), findsNothing);
    });

    testWidgets('with no media of any kind the card renders nothing',
        (tester) async {
      // Fallback rule 6.5: media never blocks or clutters the text
      // experience. An empty bordered box promising audio is clutter.
      await _pump(tester,
          sessionId: '', hasGeneric: false, documentType: 'unknown');
      expect(find.byType(Card), findsNothing);
      expect(find.textContaining('Listen'), findsNothing);
    });
  });

  group('an unclassified document still gets its own summary', () {
    testWidgets('documentType "unknown" keeps the per-case row', (tester) async {
      // The card used to be hidden entirely for unknown documents, which also
      // hid the per-case explainer - but a patient's own summary does not
      // need the router to recognise their condition.
      await _pump(tester, documentType: 'unknown', hasGeneric: false);
      expect(find.text('Listen to YOUR summary'), findsOneWidget);
    });

    testWidgets('the general-guide caption is absent when there is no guide',
        (tester) async {
      await _pump(tester, documentType: 'unknown', hasGeneric: false);
      expect(
        find.textContaining('General guide for your condition'),
        findsNothing,
        reason: 'nothing to distinguish the per-case audio FROM',
      );
    });

    testWidgets('the caption returns when a per-condition guide exists',
        (tester) async {
      await _pump(tester, hasGeneric: true);
      expect(find.textContaining('General guide for your condition'),
          findsOneWidget);
    });
  });

  group('generation is visibly in progress', () {
    testWidgets('a spinner shows while generating and clears after',
        (tester) async {
      final gate = Completer<Uint8List?>();
      await _pump(tester, fetcher: (_, __) => gate.future);
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.textContaining('Making your audio'), findsOneWidget);
      gate.complete(_wav());
      await tester.pumpAndSettle();
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('a second tap while generating cannot start a second call',
        (tester) async {
      // Generation is billable. A double tap must not double-charge.
      var calls = 0;
      final gate = Completer<Uint8List?>();
      await _pump(tester, fetcher: (_, __) {
        calls++;
        return gate.future;
      });
      await tester.tap(find.byKey(const Key('caseAudioPlay')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('caseAudioPlay')), warnIfMissed: false);
      await tester.pump();
      expect(calls, 1);
      gate.complete(_wav());
      await tester.pumpAndSettle();
    });
  });
}
