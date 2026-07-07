/// widgets/audio_explainer.dart
///
/// "Prefer to listen?" card (Sprint 4, Task 4.1) - streams the per-diagnosis
/// audio explainer from GET /media/{document_type}. Availability is probed
/// with a HEAD request first; on 404 (audio not generated yet) or any network
/// error the widget renders NOTHING - fallback rule 6.5: media never blocks
/// or clutters the text experience.
///
/// Mirrors the Streamlit player: general audio for the condition, with a
/// caption pointing back at the patient-specific written summary.
library;

import 'package:audioplayers/audioplayers.dart';
import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class AudioExplainerCard extends StatefulWidget {
  const AudioExplainerCard({super.key, required this.documentType});

  /// Router classification from PipelineResponse.document_type.
  final String documentType;

  @override
  State<AudioExplainerCard> createState() => _AudioExplainerCardState();
}

class _AudioExplainerCardState extends State<AudioExplainerCard> {
  final _player = AudioPlayer();
  bool _available = false;
  bool _playing = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  String get _url => '${ApiConfig.baseUrl}/media/${widget.documentType}';

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
    try {
      final resp = await http.head(Uri.parse(_url)).timeout(const Duration(seconds: 6));
      if (mounted && resp.statusCode == 200) setState(() => _available = true);
    } catch (_) {
      // Unreachable server degrades exactly like 404: no player, text only.
    }
  }

  Future<void> _toggle() async {
    if (_playing) {
      await _player.pause();
    } else {
      await _player.play(UrlSource(_url));
    }
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_available) return const SizedBox.shrink();
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
              // Big tap target on purpose - older patients, rule of thumb 48dp.
              IconButton.filled(
                style: IconButton.styleFrom(backgroundColor: kTealMid),
                iconSize: 28,
                onPressed: _toggle,
                icon: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                    color: Colors.white),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Prefer to listen? Audio guide to your condition',
                  style: TextStyle(
                      fontWeight: FontWeight.w700, color: kTextPrimaryLight),
                ),
              ),
            ],
          ),
          if (_duration > Duration.zero) ...[
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
