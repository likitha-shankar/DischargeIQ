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

import 'dart:typed_data';

import 'package:provider/provider.dart';

import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:dischargeiq_mobile/services/case_audio_player.dart';
import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';

class AudioExplainerCard extends StatefulWidget {
  const AudioExplainerCard({
    super.key,
    required this.documentType,
    this.sessionId = '',
    this.pipelinePayload = const {},
    this.caseAudioFetcher,
    this.probeMedia,
  });

  /// Override for the per-case generation call. Production leaves this null
  /// and the card uses [ApiService.caseAudio]; tests supply a stub so the tap
  /// path can be driven without a network or a device.
  final Future<Uint8List?> Function(String sessionId, Map<String, dynamic> payload)?
      caseAudioFetcher;

  /// Override for the HEAD probe that decides whether a per-condition file
  /// exists. Same purpose as [caseAudioFetcher].
  final Future<bool> Function(String url)? probeMedia;

  /// Router classification from PipelineResponse.document_type.
  final String documentType;

  /// Backend session id for the per-case explainer. Empty disables it.
  final String sessionId;

  /// The pipeline result to narrate. Empty disables the per-case explainer.
  final Map<String, dynamic> pipelinePayload;

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

  /// Generated per-case WAV, held for the life of the screen.
  ///
  /// This is the cache the server relies on: /media/case costs a script LLM
  /// call plus TTS, and the endpoint's contract is that a second press of
  /// play must NOT re-post. Holding the bytes here is what honours that.
  Uint8List? _caseBytes;
  bool _caseLoading = false;

  /// Set once a generation attempt has failed, so the button stops offering
  /// something that will not arrive. Feature-off (404) lands here too.
  bool _caseFailed = false;

  bool get _caseAvailable =>
      widget.sessionId.isNotEmpty && widget.pipelinePayload.isNotEmpty;

  /// Synthetic track id for the shared player - the per-case audio has no URL.
  String get _caseKey => 'case:${widget.sessionId}';

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
    final probe = widget.probeMedia ??
        (String url) async {
          try {
            final resp =
                await http.head(Uri.parse(url)).timeout(const Duration(seconds: 6));
            return resp.statusCode == 200;
          } catch (_) {
            // Unreachable server degrades exactly like 404: no player, text only.
            return false;
          }
        };
    Future<bool> exists(String url) => probe(url);

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

  /// Play the patient's OWN summary, generating it on the first press.
  ///
  /// Generation is several seconds of script LLM plus TTS, so the button
  /// shows a spinner rather than appearing dead. A failure is not surfaced as
  /// an error dialog: this is an optional extra on top of text that is
  /// already on screen, so it degrades to a quiet unavailable state.
  Future<void> _toggleCaseAudio() async {
    _video?.pause();
    final player = context.read<CaseAudioPlayer>();
    final cached = _caseBytes;
    if (cached != null) {
      await player.toggleBytes(_caseKey, cached, label: 'Your summary');
      return;
    }
    if (_caseLoading) return;
    setState(() => _caseLoading = true);
    final fetch = widget.caseAudioFetcher ??
        (String sid, Map<String, dynamic> payload) =>
            ApiService().caseAudio(sessionId: sid, pipelinePayload: payload);
    final bytes = await fetch(widget.sessionId, widget.pipelinePayload);
    if (!mounted) return;
    setState(() {
      _caseLoading = false;
      _caseBytes = bytes;
      _caseFailed = bytes == null;
    });
    if (bytes == null) return;
    await player.playBytes(_caseKey, bytes, label: 'Your summary');
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
    // Rule 6.5: with no media of any kind, the card renders nothing rather
    // than an empty box promising audio that does not exist.
    final offerCase = _caseAvailable && !_caseFailed;
    if (!_audioAvailable && !_videoAvailable && !offerCase) {
      return const SizedBox.shrink();
    }
    final audio = context.watch<CaseAudioPlayer>();
    final isThisTrack = audio.isCurrent(_audioUrl);
    final isCaseTrack = audio.isCurrent(_caseKey);
    final playing = isThisTrack && audio.isPlaying;
    final casePlaying = isCaseTrack && audio.isPlaying;
    // The scrubber follows whichever of the two tracks is loaded, so it does
    // not sit frozen at 0:00 while the per-case explainer is playing.
    final onAir = isThisTrack || isCaseTrack;
    final progress = onAir ? audio.progress : 0.0;
    final position = onAir ? audio.position : Duration.zero;
    final duration = onAir ? audio.duration : Duration.zero;
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
          // The patient's OWN summary comes first. The per-condition podcast
          // below it is the same recording for everyone with this diagnosis;
          // this one names their drugs and their follow-ups, so it is the
          // one worth reaching for.
          if (offerCase) ...[
            Row(
              children: [
                IconButton.filled(
                  // Named so tests can drive the per-case control specifically:
                  // both rows show a play triangle, and finding by icon would
                  // be ambiguous exactly where precision matters.
                  key: const Key('caseAudioPlay'),
                  style: IconButton.styleFrom(backgroundColor: kTeal),
                  iconSize: 28,
                  // Disabled while generating, so a second tap cannot fire a
                  // second (billable) generation of the same audio.
                  onPressed: _caseLoading ? null : _toggleCaseAudio,
                  icon: _caseLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              strokeWidth: 2.4, color: Colors.white),
                        )
                      : Icon(
                          casePlaying
                              ? Icons.pause_rounded
                              : Icons.play_arrow_rounded,
                          color: Colors.white),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Listen to YOUR summary',
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: kTextPrimaryLight),
                      ),
                      Text(
                        _caseLoading
                            ? 'Making your audio - about 10 seconds'
                            : 'Your document, read aloud',
                        style: const TextStyle(
                            fontSize: 12, color: kTextSecondaryLight),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (_audioAvailable || _videoAvailable) ...[
              const SizedBox(height: 10),
              const Divider(height: 1, color: kTealMid),
              const SizedBox(height: 10),
            ],
          ],
          // Skipped entirely when only the per-case explainer exists, so the
          // card does not draw an empty control row with a caption under it.
          if (_audioAvailable || _videoAvailable)
            Row(
            children: [
              // Big tap targets on purpose - older patients, rule of thumb 48dp.
              if (_audioAvailable) ...[
                // Rewind sits BEFORE play: someone who missed a drug name
                // reaches for "back" first, and it should be where their
                // thumb already is.
                IconButton(
                  tooltip: 'Back 15 seconds',
                  iconSize: 26,
                  onPressed: isThisTrack
                      ? () => audio.skip(const Duration(seconds: -15))
                      : null,
                  icon: const Icon(Icons.replay_10_rounded, color: kTeal),
                ),
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
                IconButton(
                  tooltip: 'Forward 15 seconds',
                  iconSize: 26,
                  onPressed: isThisTrack
                      ? () => audio.skip(const Duration(seconds: 15))
                      : null,
                  icon: const Icon(Icons.forward_10_rounded, color: kTeal),
                ),
                const SizedBox(width: 4),
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
          if (onAir && duration > Duration.zero) ...[
            const SizedBox(height: 8),
            // Draggable, not just an indicator. The skip buttons above are
            // the primary control - a thin slider is hard for older hands -
            // but someone who wants the last third of the explainer should
            // be able to go straight there.
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                trackHeight: 6,
                activeTrackColor: kTealMid,
                inactiveTrackColor: Colors.white,
                thumbColor: kTeal,
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 16),
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
              ),
              child: Slider(
                value: progress,
                onChanged: isThisTrack && duration > Duration.zero
                    ? (v) => audio.seek(duration * v)
                    : null,
                semanticFormatterCallback: (v) =>
                    'Position ${_clock(duration * v)} of ${_clock(duration)}',
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
          // Only meaningful when a per-condition recording is on offer. With
          // just the per-case explainer there is no "general guide" to
          // distinguish it from, and the sentence would contradict itself.
          if (_audioAvailable || _videoAvailable)
            const Text(
              'General guide for your condition - the summary below is '
              'specific to YOUR discharge document.',
              style: TextStyle(
                  fontSize: 12, color: kTextPrimaryLight, height: 1.3),
            ),
        ],
      ),
    );
  }
}
