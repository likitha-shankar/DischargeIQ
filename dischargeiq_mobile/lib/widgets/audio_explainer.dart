/// widgets/audio_explainer.dart
///
/// "Listen or watch" card (Sprint 4, Task 4.1) - streams the per-diagnosis
/// NotebookLM explainers: audio (podcast) from GET /media/{document_type}
/// and video from GET /media/{document_type}/video. Availability of each is
/// probed with a HEAD request; whatever exists gets a control, and when
/// NEITHER exists the widget renders NOTHING - fallback rule 6.5: media
/// never blocks or clutters the text experience.
///
/// Mirrors the Streamlit block: general media for the condition, with a
/// caption pointing back at the patient-specific written summary.
library;

import 'package:audioplayers/audioplayers.dart';
import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';

class AudioExplainerCard extends StatefulWidget {
  const AudioExplainerCard({super.key, required this.documentType});

  /// Router classification from PipelineResponse.document_type.
  final String documentType;

  @override
  State<AudioExplainerCard> createState() => _AudioExplainerCardState();
}

class _AudioExplainerCardState extends State<AudioExplainerCard> {
  final _player = AudioPlayer();
  VideoPlayerController? _video;
  bool _audioAvailable = false;
  bool _videoAvailable = false;
  bool _showVideo = false;
  bool _playing = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  String get _audioUrl => '${ApiConfig.baseUrl}/media/${widget.documentType}';
  String get _videoUrl => '$_audioUrl/video';

  @override
  void initState() {
    super.initState();
    _probe();
    _player.onPlayerStateChanged.listen((s) {
      if (mounted) setState(() => _playing = s == PlayerState.playing);
    });
    _player.onPositionChanged.listen((p) {
      if (mounted) setState(() => _position = p);
    });
    _player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _duration = d);
    });
  }

  Future<void> _probe() async {
    // "unknown" documents have no matching explainer by definition.
    if (widget.documentType.isEmpty || widget.documentType == 'unknown') return;
    Future<bool> exists(String url) async {
      try {
        final resp = await http.head(Uri.parse(url)).timeout(const Duration(seconds: 6));
        return resp.statusCode == 200;
      } catch (_) {
        // Unreachable server degrades exactly like 404: no player, text only.
        return false;
      }
    }

    final audio = await exists(_audioUrl);
    final video = await exists(_videoUrl);
    if (mounted) {
      setState(() {
        _audioAvailable = audio;
        _videoAvailable = video;
      });
    }
  }

  Future<void> _toggleAudio() async {
    // One medium at a time - starting the podcast pauses the video.
    _video?.pause();
    if (_playing) {
      await _player.pause();
    } else {
      await _player.play(UrlSource(_audioUrl));
    }
  }

  Future<void> _toggleVideo() async {
    await _player.pause();
    if (_video == null) {
      final controller = VideoPlayerController.networkUrl(Uri.parse(_videoUrl));
      await controller.initialize();
      if (!mounted) {
        controller.dispose();
        return;
      }
      setState(() => _video = controller);
    }
    setState(() => _showVideo = true);
    _video!.value.isPlaying ? _video!.pause() : _video!.play();
  }

  @override
  void dispose() {
    _player.dispose();
    _video?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_audioAvailable && !_videoAvailable) return const SizedBox.shrink();
    final progress = _duration.inMilliseconds > 0
        ? (_position.inMilliseconds / _duration.inMilliseconds).clamp(0.0, 1.0)
        : 0.0;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: kTealPale,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kTealMid, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Big tap targets on purpose - older patients, rule of thumb 48dp.
              if (_audioAvailable) ...[
                IconButton.filled(
                  style: IconButton.styleFrom(backgroundColor: kTealMid),
                  iconSize: 28,
                  onPressed: _toggleAudio,
                  icon: Icon(_playing ? Icons.pause_rounded : Icons.headphones_rounded,
                      color: Colors.white),
                ),
                const SizedBox(width: 8),
              ],
              if (_videoAvailable) ...[
                IconButton.filled(
                  style: IconButton.styleFrom(backgroundColor: kTealMid),
                  iconSize: 28,
                  onPressed: _toggleVideo,
                  icon: const Icon(Icons.ondemand_video_rounded, color: Colors.white),
                ),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: Text(
                  _audioAvailable && _videoAvailable
                      ? 'Listen or watch: a guide to your condition'
                      : (_audioAvailable
                          ? 'Prefer to listen? Audio guide to your condition'
                          : 'Prefer to watch? Video guide to your condition'),
                  style: const TextStyle(
                      fontWeight: FontWeight.w700, color: kTextPrimaryLight),
                ),
              ),
            ],
          ),
          if (_audioAvailable && _duration > Duration.zero) ...[
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 6,
                backgroundColor: Colors.white,
                valueColor: const AlwaysStoppedAnimation(kTealMid),
              ),
            ),
          ],
          if (_showVideo && _video != null && _video!.value.isInitialized) ...[
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: AspectRatio(
                aspectRatio: _video!.value.aspectRatio,
                child: GestureDetector(
                  onTap: () => setState(() =>
                      _video!.value.isPlaying ? _video!.pause() : _video!.play()),
                  child: VideoPlayer(_video!),
                ),
              ),
            ),
          ],
          const SizedBox(height: 6),
          const Text(
            'General guide for your condition - the summary below is specific '
            'to YOUR discharge document.',
            style: TextStyle(
                fontSize: 12, color: kTextPrimaryLight, height: 1.3),
          ),
        ],
      ),
    );
  }
}
