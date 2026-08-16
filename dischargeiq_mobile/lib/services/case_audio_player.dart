/// services/case_audio_player.dart
///
/// One audio player for the whole results screen, so an explainer keeps
/// playing while the patient reads other tabs.
///
/// It used to live inside AudioExplainerCard, which sits in the TabBarView.
/// Flutter unmounts an off-screen tab, so switching away disposed the player:
/// the audio stopped mid-sentence, the position was lost, and there was no
/// control anywhere else to pause or resume it. Someone listening while
/// looking up their medications lost the explainer by doing the obvious
/// thing.
///
/// Holding the player above the tabs fixes all three: playback continues, the
/// position survives, and a bar pinned under the tab strip can pause it from
/// any tab.
library;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

class CaseAudioPlayer extends ChangeNotifier {
  CaseAudioPlayer() {
    _player.onPlayerStateChanged.listen((state) {
      _playing = state == PlayerState.playing;
      // A finished track is not "paused at the end" - clear it so the bar
      // disappears rather than sitting there offering to resume nothing.
      if (state == PlayerState.completed) {
        _position = Duration.zero;
        _url = null;
      }
      notifyListeners();
    });
    _player.onPositionChanged.listen((p) {
      _position = p;
      notifyListeners();
    });
    _player.onDurationChanged.listen((d) {
      _duration = d;
      notifyListeners();
    });
  }

  final AudioPlayer _player = AudioPlayer();

  String? _url;
  String _label = '';
  bool _playing = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  /// URL of the track loaded, or null when nothing is queued.
  String? get url => _url;

  /// Human-readable name for the bar ("Heart failure explainer").
  String get label => _label;

  bool get isPlaying => _playing;
  Duration get position => _position;
  Duration get duration => _duration;

  /// True when a track is loaded, whether or not it is currently playing.
  /// The bar shows in both states so a paused explainer can be resumed.
  bool get hasTrack => _url != null;

  /// Fraction played, 0.0 when the duration is not known yet.
  double get progress => _duration.inMilliseconds > 0
      ? (_position.inMilliseconds / _duration.inMilliseconds).clamp(0.0, 1.0)
      : 0.0;

  /// Whether [url] is the track currently loaded.
  bool isCurrent(String url) => _url == url;

  /// Start [url], or resume it when it is already the loaded track.
  ///
  /// Resuming rather than restarting matters: a patient who paused to read
  /// something should not be sent back to the beginning of the explainer.
  Future<void> play(String url, {String label = ''}) async {
    if (_url == url) {
      await _player.resume();
      return;
    }
    _url = url;
    _label = label;
    _position = Duration.zero;
    _duration = Duration.zero;
    notifyListeners();
    await _player.play(UrlSource(url));
  }

  Future<void> pause() async => _player.pause();

  /// Jump to a position, clamped inside the track.
  ///
  /// Seeking past the end would complete the track and clear the bar, which
  /// is not what someone dragging near the end is asking for.
  Future<void> seek(Duration to) async {
    if (_url == null) return;
    var target = to;
    if (target < Duration.zero) target = Duration.zero;
    if (_duration > Duration.zero && target > _duration) {
      target = _duration - const Duration(milliseconds: 200);
    }
    _position = target;
    notifyListeners();
    await _player.seek(target);
  }

  /// Move [delta] from where we are - negative rewinds.
  ///
  /// Fifteen seconds because this is spoken explanation, not music: it is
  /// roughly one sentence back, which is what someone who missed a drug name
  /// actually wants.
  Future<void> skip(Duration delta) => seek(_position + delta);

  /// Stop and forget the track, so the bar disappears.
  Future<void> stop() async {
    await _player.stop();
    _url = null;
    _label = '';
    _position = Duration.zero;
    _duration = Duration.zero;
    notifyListeners();
  }

  Future<void> toggle(String url, {String label = ''}) async {
    if (_url == url && _playing) {
      await pause();
    } else {
      await play(url, label: label);
    }
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }
}
