/// services/read_aloud.dart
///
/// Read-aloud (accessibility, Task 3.5): on-device text-to-speech for the
/// results sections, for patients who struggle with reading. Wraps
/// flutter_tts as a single shared engine with a deliberately SLOW rate -
/// discharge instructions read to an older patient must never race.
/// Speech happens entirely on the phone; no text leaves the device.
library;

import 'package:flutter_tts/flutter_tts.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ReadAloud {
  static final FlutterTts _tts = FlutterTts();
  static bool _configured = false;
  static bool _speaking = false;

  /// Preference key: whether the speaker button is shown on results.
  static const prefKey = 'read_aloud_enabled';

  static bool get isSpeaking => _speaking;

  /// Called when speech finishes or is cancelled - the UI resets its icon.
  static void Function()? onDone;

  static Future<void> _configure() async {
    if (_configured) return;
    // 0.42 is noticeably slower than the platform default - calm, followable
    // pacing for medical instructions (same principle as no quiz timers).
    await _tts.setSpeechRate(0.42);
    await _tts.setPitch(1.0);
    _tts.setCompletionHandler(() {
      _speaking = false;
      onDone?.call();
    });
    _tts.setCancelHandler(() {
      _speaking = false;
      onDone?.call();
    });
    _configured = true;
  }

  /// Speak one section. Any current speech is stopped first.
  static Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    await _configure();
    await _tts.stop();
    _speaking = true;
    await _tts.speak(_cleanForSpeech(text));
  }

  static Future<void> stop() async {
    _speaking = false;
    await _tts.stop();
  }

  /// Whether the speaker button should be shown (Settings toggle, default on).
  static Future<bool> enabled() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(prefKey) ?? true;
    } catch (_) {
      return true;
    }
  }

  static Future<void> setEnabled(bool value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(prefKey, value);
    } catch (_) {}
  }

  /// Strip markdown/formatting noise so the voice reads words, not symbols.
  static String _cleanForSpeech(String text) {
    return text
        .replaceAll(RegExp(r'[#*_`>|]'), '')
        .replaceAll(RegExp(r'^\s*[-•]\s*', multiLine: true), '')
        .replaceAll(RegExp(r'\n{2,}'), '. ')
        .replaceAll(RegExp(r'\s{2,}'), ' ')
        .trim();
  }
}
