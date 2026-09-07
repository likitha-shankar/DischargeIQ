// Integration probe: does the per-case explainer ACTUALLY play on the phone?
//
// The widget tests prove the tap requests the right audio and that the bytes
// reach the player. They cannot prove the last inch: that iOS decodes a real
// multi-megabyte WAV and runs its audio clock. Those tests run against a fake
// canvas with no audio hardware behind it.
//
// This runs on the device, against the LIVE backend, through the real
// audioplayers plugin. The assertions are chosen so they can only pass if the
// OS is genuinely playing:
//
//   duration > 0        - iOS parsed the WAV header and decoded it
//   isPlaying == true   - the platform reported a playing state back
//   position advances   - the audio clock is running, not just a flag set
//
// Run (the iPhone MUST be on a USB cable):
//   flutter test integration_test/case_audio_probe_test.dart \
//     -d 00008120-001A3D281A78C01E \
//     --dart-define=API_KEY=$DISCHARGEIQ_API_KEY
//
// Two dead ends already ruled out, so nobody re-walks them:
//
//   Wireless device. "Cannot start app on wirelessly tethered iOS device."
//   Integration tests need the VM service port, which wireless tethering does
//   not carry. The tool suggests --publish-port; `flutter test` has no such
//   flag. A cable is the fix, not a flag.
//
//   macOS as a stand-in. Builds and runs, but audioplayers' setSourceBytes
//   does not stream from memory - it WRITES THE BYTES TO A CACHE FILE and
//   plays that. Under the macOS sandbox the container's Caches directory is
//   absent and it throws PathNotFoundException, so the run says nothing about
//   iOS. Worth knowing regardless: playBytes depends on a writable cache
//   directory existing, which is the one way this path can fail on a phone
//   while every unit test still passes.

import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:dischargeiq_mobile/services/case_audio_player.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

/// A payload with enough substance for the script model to narrate.
const _payload = {
  'pipeline_status': 'complete',
  'extraction': {
    'primary_diagnosis': 'Acute Decompensated Heart Failure',
    'medications': [
      {'name': 'Furosemide', 'dose': '40 mg', 'frequency': 'once daily', 'status': 'new'},
      {'name': 'Carvedilol', 'dose': '6.25 mg', 'frequency': 'twice daily', 'status': 'new'},
    ],
    'follow_up_appointments': [
      {'provider': 'Dr. Chen', 'specialty': 'Cardiology', 'date': '2026-09-20'},
    ],
    'red_flag_symptoms': ['Weight gain of 3 pounds in one day'],
  },
  'diagnosis_explanation': 'Your heart was not pumping blood as well as it should.',
  'medication_rationale': 'Furosemide removes extra fluid from your body.',
  'recovery_trajectory': 'Week 1-2: rest and weigh yourself every morning.',
  'escalation_guide': 'Call 911 if you cannot breathe.',
};

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('real device: per-case audio generates and actually plays',
      (t) async {
    // 1. The real network call the button makes.
    final bytes = await ApiService()
        .caseAudio(sessionId: 'device-probe-1', pipelinePayload: _payload);

    expect(bytes, isNotNull,
        reason: 'GENERATION FAILED on device - check the API key is compiled '
            'into this build and CASE_AUDIO_ENABLED is on server-side');
    expect(bytes!.length, greaterThan(100000),
        reason: 'audio suspiciously small: ${bytes.length} bytes');

    // A WAV, not an error page the client mistook for audio.
    expect(String.fromCharCodes(bytes.take(4)), 'RIFF',
        reason: 'response was not a WAV');

    // 2. Hand it to the real player on real audio hardware.
    final player = CaseAudioPlayer();
    await player.playBytes('case:device-probe-1', bytes, label: 'Your summary');

    // iOS needs a moment to parse the header and start the clock.
    await Future<void>.delayed(const Duration(seconds: 2));

    expect(player.duration.inMilliseconds, greaterThan(0),
        reason: 'DECODE FAILED - iOS never reported a duration');
    expect(player.isPlaying, isTrue,
        reason: 'the platform did not report a playing state');

    // 3. The audio clock is genuinely running. A flag can be set wrongly; a
    //    position that advances on its own cannot.
    final first = player.position;
    await Future<void>.delayed(const Duration(seconds: 2));
    final second = player.position;
    expect(second, greaterThan(first),
        reason: 'position did not advance - audio is not actually playing '
            '($first -> $second)');

    // 4. Pause holds position rather than resetting it.
    await player.pause();
    await Future<void>.delayed(const Duration(milliseconds: 600));
    expect(player.isPlaying, isFalse);
    final held = player.position;
    await Future<void>.delayed(const Duration(seconds: 1));
    expect(player.position, held,
        reason: 'position moved while paused');

    // 5. Resuming continues from where it stopped - the behaviour a patient
    //    who paused to read something depends on.
    await player.toggleBytes('case:device-probe-1', bytes);
    await Future<void>.delayed(const Duration(seconds: 1));
    expect(player.isPlaying, isTrue, reason: 'resume did not restart playback');
    expect(player.position, greaterThanOrEqualTo(held),
        reason: 'resume restarted from the beginning instead of continuing');

    await player.stop();
    expect(player.hasTrack, isFalse);

    // ignore: avoid_print
    print('PROBE OK: ${bytes.length} bytes, '
        'duration ${player.duration.inSeconds}s, clock advanced');
  }, timeout: const Timeout(Duration(minutes: 4)));

  testWidgets('real device: seeking inside the track works', (t) async {
    final bytes = await ApiService()
        .caseAudio(sessionId: 'device-probe-1', pipelinePayload: _payload);
    expect(bytes, isNotNull);

    final player = CaseAudioPlayer();
    await player.playBytes('case:seek', bytes!);
    await Future<void>.delayed(const Duration(seconds: 2));
    expect(player.duration.inMilliseconds, greaterThan(0));

    // The skip control a patient uses when they missed a drug name.
    await player.seek(const Duration(seconds: 10));
    await Future<void>.delayed(const Duration(milliseconds: 900));
    expect(player.position.inSeconds, greaterThanOrEqualTo(8),
        reason: 'seek did not move the playhead');

    await player.stop();
  }, timeout: const Timeout(Duration(minutes: 4)));
}
