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

import 'package:provider/provider.dart';

import 'package:dischargeiq_mobile/services/case_audio_player.dart';
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
  // The player lives above the tabs (CaseAudioPlayer) so playback survives a
  // tab change. This card only drives it and reflects its state.
  VideoPlayerController? _video;
  bool _audioAvailable = false;
  bool _videoAvailable = false;
  bool _showVideo = false;

  String get _audioUrl => '${ApiConfig.baseUrl}/media/${widget.documentType}';
  String get _videoUrl => '$_audioUrl/video';

  @override
  void initState() {
    super.initState();
    _probe();
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
    await context.read<CaseAudioPlayer>().toggle(
          _audioUrl,
          label: _friendlyLabel,
        );
  }

  /// Minutes and seconds, e.g. "1:07".
  String _clock(Duration d) =>
      '${d.inMinutes}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';

  /// "Heart failure explainer" from a document_type of "heart_failure".
  String get _friendlyLabel {
    final words = widget.documentType.replaceAll('_', ' ').trim();
    if (words.isEmpty) return 'Audio explainer';
    return '${words[0].toUpperCase()}${words.substring(1)} explainer';
  }

  Future<void> _toggleVideo() async {
    await context.read<CaseAudioPlayer>().pause();
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
    // Only the video belongs to this card. Disposing the shared audio player
    // here is what used to kill playback on every tab change.
    _video?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_audioAvailable && !_videoAvailable) return const SizedBox.shrink();
    final audio = context.watch<CaseAudioPlayer>();
    final isThisTrack = audio.isCurrent(_audioUrl);
    final playing = isThisTrack && audio.isPlaying;
    final progress = isThisTrack ? audio.progress : 0.0;
    final position = isThisTrack ? audio.position : Duration.zero;
    final duration = isThisTrack ? audio.duration : Duration.zero;
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
                  // A play triangle, not headphones. Headphones say "audio
                  // exists here"; they do not say "tap this to start it", and
                  // the control read as decoration until it was playing.
                  icon: Icon(
                      playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
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
          if (_audioAvailable && duration > Duration.zero) ...[
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
            const SizedBox(height: 4),
            // How long this takes, which is the question before "should I
            // start it" - a patient just home from hospital is deciding
            // whether they have the energy for five minutes of audio.
            Text(
              '${_clock(position)} of ${_clock(duration)}',
              style: const TextStyle(fontSize: 11, color: kTextSecondaryLight),
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
