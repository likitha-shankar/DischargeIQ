/// services/voice_input.dart
///
/// Microphone dictation for the chat, wrapping the platform speech
/// recognizer (Apple on iOS, Google on Android).
///
/// Exists so the chat sheet never touches the plugin directly: permission
/// refusal, an unavailable recognizer, and a silent room all have to degrade
/// into "keep typing" rather than an error the patient has to solve.
///
/// Privacy: recognition is handled by the platform. This app records nothing,
/// stores nothing, and sends no audio anywhere - only the resulting text goes
/// to the chat endpoint, exactly as if it had been typed.
library;

import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_to_text.dart';

class VoiceInput {
  VoiceInput._();

  static final SpeechToText _speech = SpeechToText();
  static bool _available = false;
  static bool _initialised = false;

  /// True while the microphone is open.
  static bool get isListening => _speech.isListening;

  /// Prepare the recognizer once, prompting for permission on first use.
  ///
  /// Returns false when speech is unavailable for any reason - no permission,
  /// no recognizer, offline-only device. Callers hide the microphone rather
  /// than showing a button that cannot work.
  static Future<bool> prepare() async {
    if (_initialised) return _available;
    try {
      _available = await _speech.initialize(
        // Both callbacks are best-effort diagnostics. Errors surface to the
        // patient as the mic simply stopping, never as a dialog.
        onError: (e) => debugPrint('speech error: ${e.errorMsg}'),
        onStatus: (s) => debugPrint('speech status: $s'),
      );
    } catch (e) {
      debugPrint('speech init failed: $e');
      _available = false;
    }
    _initialised = true;
    return _available;
  }

  /// Listen until the patient stops talking, reporting text as it firms up.
  ///
  /// Args:
  ///   onResult: Called with the transcript so far. [isFinal] is true on the
  ///             last call, which is when the caller should send.
  ///
  /// Returns false when listening could not start.
  static Future<bool> listen({
    required void Function(String text, bool isFinal) onResult,
  }) async {
    if (!await prepare()) return false;
    try {
      await _speech.listen(
        onResult: (r) => onResult(r.recognizedWords, r.finalResult),
        listenOptions: SpeechListenOptions(
          // Dictation, not command-and-control: a patient describing a symptom
          // pauses mid-sentence and must not be cut off at the first gap.
          listenMode: ListenMode.dictation,
          partialResults: true,
          cancelOnError: true,
          // Generous windows for someone unwell, who may speak slowly.
          listenFor: const Duration(seconds: 30),
          pauseFor: const Duration(seconds: 4),
        ),
      );
      return true;
    } catch (e) {
      debugPrint('speech listen failed: $e');
      return false;
    }
  }

  /// Stop listening and keep whatever was heard.
  static Future<void> stop() async {
    try {
      await _speech.stop();
    } catch (_) {
      // Stopping a recognizer that already stopped is not an error worth
      // surfacing to a patient.
    }
  }

  /// Stop listening and discard the transcript.
  static Future<void> cancel() async {
    try {
      await _speech.cancel();
    } catch (_) {
      // Same reasoning as stop().
    }
  }
}
