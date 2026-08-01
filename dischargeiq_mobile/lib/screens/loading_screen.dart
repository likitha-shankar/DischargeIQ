import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

const _kStatusMessages = [
  'Reading your discharge document...',
  'Understanding your diagnosis...',
  'Analyzing your medications...',
  'Building your recovery plan...',
  'Checking warning signs...',
  'Running discharge quality check...',
  'Almost ready...',
];

const _kPillLabels = [
  'Extraction',
  'Diagnosis',
  'Medications',
  'Recovery',
  'Warnings',
  'Quality check',
];

/// Full-screen loading with hospital→home animation while `/analyze` runs.
///
/// Three input modes: a picked PDF (pdfBytes), camera-scanned text (ocrText,
/// Sprint 2 OCR path), or photo files for the opt-in enhanced cloud read
/// (imagePaths - the only mode where photos leave the phone). Exactly one
/// must be provided.
class LoadingScreen extends StatefulWidget {
  const LoadingScreen({
    super.key,
    this.pdfBytes,
    this.ocrText,
    this.imagePaths,
    required this.fileName,
  }) : assert(pdfBytes != null || ocrText != null || imagePaths != null);

  final Uint8List? pdfBytes;
  final String? ocrText;
  final List<String>? imagePaths;
  final String fileName;

  @override
  State<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends State<LoadingScreen> with TickerProviderStateMixin {
  late final AnimationController _walk;
  late final AnimationController _legs;
  int _msgIndex = 0;
  Timer? _msgTimer;
  Timer? _progressTimer;

  // Client-minted session id lets us poll GET /progress/{id} DURING the run
  // for real per-agent updates. The backend accepts it (unused-UUID check).
  late final String _sessionId = _uuidV4();

  // Real progress, when the poller has it. Null until the first live update
  // arrives; the fake 4s message cycler covers the gap.
  String? _liveMessage;
  int _liveAgent = 0;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  @override
  void initState() {
    super.initState();
    _walk = AnimationController(vsync: this, duration: const Duration(seconds: 5))..repeat();
    _legs = AnimationController(vsync: this, duration: const Duration(milliseconds: 400))..repeat(reverse: true);

    _msgTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      if (!mounted || _liveMessage != null) return; // live updates take over
      setState(() {
        _msgIndex = (_msgIndex + 1) % _kStatusMessages.length;
      });
    });

    // Live progress poll (Streamlit polls the same endpoint). Errors are
    // ignored: worst case the screen falls back to the message cycler.
    _progressTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      try {
        final p = await ApiService().getProgress(_sessionId);
        if (!mounted || '${p['status']}' != 'running') return;
        final message = '${p['message'] ?? ''}';
        if (message.isEmpty) return;
        setState(() {
          _liveMessage = message;
          _liveAgent = (p['current_agent'] as num?)?.toInt() ?? 0;
        });
      } catch (_) {
        // Keep the fake cycler; never surface polling noise to the patient.
      }
    });

    Future<void>.delayed(Duration.zero, _runAnalyze);
  }

  /// Minimal RFC-4122 v4 UUID (no dependency needed for one id).
  static String _uuidV4() {
    final rng = math.Random.secure();
    final b = List<int>.generate(16, (_) => rng.nextInt(256));
    b[6] = (b[6] & 0x0f) | 0x40; // version 4
    b[8] = (b[8] & 0x3f) | 0x80; // variant 10
    final hex = [for (final x in b) x.toRadixString(16).padLeft(2, '0')].join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<void> _runAnalyze() async {
    try {
      final Map<String, dynamic> data;
      if (widget.imagePaths != null) {
        data = await ApiService()
            .analyzeImages(widget.imagePaths!, sessionId: _sessionId);
      } else if (widget.ocrText != null) {
        data = await ApiService()
            .analyzeText(widget.ocrText!, sessionId: _sessionId);
      } else {
        data = await ApiService()
            .analyze(widget.pdfBytes!, widget.fileName, sessionId: _sessionId);
      }
      if (!mounted) return;
      // On-device library (D-6): keep this analysis on the phone so closing
      // the app no longer loses it. Saved BEFORE setResult so the returned
      // document id can scope per-document stars from the first tab view.
      // Local file write, milliseconds - not worth a fire-and-forget race.
      // Dead runs (quota-exhausted partials) are not worth reopening.
      String? docId;
      if (!isUnusableRun(data)) {
        // File under whoever is active. This is what keeps new uploads out
        // of the Unassigned bucket: the home screen already showed whose
        // documents these are, so the question never has to be asked after
        // the fact. Null (no people set up yet) stays unassigned, which is
        // correct rather than a guess.
        docId = await DocumentStore.save(
          result: data,
          fileName: widget.fileName,
          pdfBytes: widget.pdfBytes,
          personId: (await PersonStore.active())?.id,
        );
      }
      if (!mounted) return;
      context.read<DischargeProvider>().setResult(
            data,
            pdfBytes: widget.pdfBytes,
            fileName: widget.fileName,
            docId: docId,
          );
      Navigator.of(context).pop();
    } catch (err) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not analyze this document. $err')),
      );
    }
  }

  @override
  void dispose() {
    _msgTimer?.cancel();
    _progressTimer?.cancel();
    _walk.dispose();
    _legs.dispose();
    super.dispose();
  }

  int get _activePill {
    // Real agent number wins (1-based from the backend); fake cycler covers
    // the gap before the first live update arrives.
    if (_liveAgent > 0) return (_liveAgent - 1).clamp(0, _kPillLabels.length - 1);
    if (_msgIndex < _kPillLabels.length) return _msgIndex;
    return _kPillLabels.length - 1;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _dark ? kBgDark : kBgLight,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const SizedBox(height: 24),
              Text(
                'Analyzing your document...',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                  color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Our AI agents are reading your discharge summary',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 11,
                  color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                ),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: 280,
                height: 110,
                child: ClipRect(
                  child: Stack(
                    clipBehavior: Clip.hardEdge,
                    children: [
                      // Solid scene background prevents any parent/browser artifact bleed-through.
                      Positioned.fill(
                        child: Container(color: _dark ? kBgDark : kBgLight),
                      ),
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        child: Container(
                          height: 2,
                          color: kTealGlow.withValues(alpha: 0.5),
                        ),
                      ),
                      Positioned(
                        left: 72,
                        right: 46,
                        bottom: 10,
                        height: 2,
                        child: CustomPaint(
                          painter: _DashedLinePainter(color: kTealGlow.withValues(alpha: 0.4)),
                        ),
                      ),
                      const _Hospital(),
                      _HomeIcon(dark: _dark),
                      AnimatedBuilder(
                        animation: Listenable.merge([_walk, _legs]),
                        builder: (context, _) {
                          final t = _walk.value;
                          final x = 74.0 + (230 - 74) * t;
                          final opacity = t < 0.65
                              ? 1.0
                              : t < 0.85
                                  ? 1.0 - (t - 0.65) / 0.2 * 0.5
                                  : 0.0;
                          return Positioned(
                            left: x,
                            bottom: 2,
                            child: Opacity(
                              opacity: opacity.clamp(0.0, 1.0),
                              child: _WalkingPerson(legTurns: _legs.value),
                            ),
                          );
                        },
                      ),
                      AnimatedBuilder(
                        animation: _walk,
                        builder: (context, _) {
                          final t = _walk.value;
                          final x = 76.0 + (228 - 76) * t;
                          final bob = -12.0 - 2.0 * math.sin(t * math.pi * 2);
                          final rot = -0.105 + 0.175 * math.sin(t * math.pi * 2);
                          double op;
                          if (t < 0.12) {
                            op = t / 0.12;
                          } else if (t < 0.8) {
                            op = 1.0;
                          } else {
                            op = 1.0 - (t - 0.8) / 0.2;
                          }
                          return Positioned(
                            left: x,
                            bottom: 22 + bob,
                            child: Opacity(
                              opacity: op.clamp(0.0, 1.0),
                              child: Transform.rotate(
                                angle: rot,
                                child: _DocChip(dark: _dark),
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                transitionBuilder: (child, anim) => FadeTransition(opacity: anim, child: child),
                child: Text(
                  _liveMessage ?? _kStatusMessages[_msgIndex],
                  key: ValueKey<int>(_msgIndex),
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: _dark ? kTealGlow : kTeal,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: SizedBox(
                  height: 4,
                  child: LinearProgressIndicator(
                    backgroundColor: _dark ? kTealMid.withValues(alpha: 0.2) : kTealPale,
                    color: _dark ? kTealGlow : kTeal,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                alignment: WrapAlignment.center,
                spacing: 6,
                runSpacing: 6,
                children: List.generate(_kPillLabels.length, (i) {
                  final on = i == _activePill;
                  return AnimatedOpacity(
                    duration: const Duration(milliseconds: 300),
                    opacity: _dark && !on ? 0.4 : 1.0,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      curve: Curves.easeInOut,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: on ? (_dark ? kTealMid : kTeal) : (_dark ? Colors.transparent : Colors.white),
                        border: on
                            ? null
                            : Border.all(
                                color: _dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow,
                              ),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        _kPillLabels[i],
                        style: TextStyle(
                          fontSize: 9,
                          color: on ? Colors.white : (_dark ? kTealGlow : kTeal),
                        ),
                      ),
                    ),
                  );
                }),
              ),
              // Scan sessions only: escape hatch for "I forgot a page".
              // Popping abandons this analysis (the in-flight result is
              // discarded via the !mounted guard) and returns to the scan
              // screen with every already-captured page intact.
              if (widget.ocrText != null || widget.imagePaths != null) ...[
                const SizedBox(height: 20),
                TextButton.icon(
                  // 'add_pages' tells the scan screen underneath to stay put
                  // instead of popping itself back to the landing.
                  onPressed: () => Navigator.of(context).maybePop('add_pages'),
                  icon: Icon(Icons.add_a_photo_outlined,
                      size: 16, color: _dark ? kTealGlow : kTeal),
                  label: Text(
                    'Forgot a page? Go back and add it',
                    style: TextStyle(
                        fontSize: 12.5, color: _dark ? kTealGlow : kTeal),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _DashedLinePainter extends CustomPainter {
  _DashedLinePainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const dash = 5.0;
    const gap = 4.0;
    double x = 0;
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5;
    while (x < size.width) {
      canvas.drawLine(Offset(x, 0), Offset(math.min(x + dash, size.width), 0), paint);
      x += dash + gap;
    }
  }

  @override
  bool shouldRepaint(covariant _DashedLinePainter oldDelegate) => oldDelegate.color != color;
}

class _Hospital extends StatelessWidget {
  const _Hospital();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Positioned(
      left: 6,
      bottom: 2,
      child: SizedBox(
        width: 64,
        height: 76,
        child: Column(
          children: [
            SizedBox(
              height: 18,
              width: 64,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Positioned.fill(
                    child: Container(
                      decoration: const BoxDecoration(
                        color: kTeal,
                        borderRadius: BorderRadius.vertical(top: Radius.circular(4)),
                      ),
                    ),
                  ),
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(width: 3, height: 10, color: Colors.white),
                      Container(width: 10, height: 3, color: Colors.white),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                  border: Border.all(color: kTealGlow, width: 1.5),
                ),
                child: Stack(
                  children: [
                    Positioned(top: 6, left: 6, child: _win()),
                    Positioned(top: 6, right: 6, child: _win()),
                    Positioned(top: 22, left: 6, child: _win()),
                    Positioned(top: 22, right: 6, child: _win()),
                    Positioned(
                      bottom: 0,
                      left: 25,
                      child: Container(
                        width: 14,
                        height: 20,
                        decoration: const BoxDecoration(
                          color: kTeal,
                          borderRadius: BorderRadius.vertical(top: Radius.circular(2)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static Widget _win() => Container(
        width: 10,
        height: 9,
        decoration: BoxDecoration(
          color: kTealGlow.withValues(alpha: 0.85),
          borderRadius: BorderRadius.circular(1),
        ),
      );
}

class _HomeIcon extends StatelessWidget {
  const _HomeIcon({required this.dark});

  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      right: 2,
      bottom: 2,
      child: Icon(
        Icons.home_outlined,
        size: 36,
        color: dark ? kTealLight : kTeal,
      ),
    );
  }
}

class _WalkingPerson extends StatelessWidget {
  const _WalkingPerson({required this.legTurns});

  final double legTurns;

  @override
  Widget build(BuildContext context) {
    final left = (legTurns - 0.5) * 0.1;
    final right = (0.5 - legTurns) * 0.1;
    return SizedBox(
      width: 20,
      height: 36,
      child: Column(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: const BoxDecoration(color: kTealMid, shape: BoxShape.circle),
          ),
          Container(
            width: 9,
            height: 14,
            margin: const EdgeInsets.only(top: 1),
            decoration: const BoxDecoration(
              color: kTeal,
              borderRadius: BorderRadius.vertical(top: Radius.circular(2)),
            ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Transform.rotate(
                angle: left,
                alignment: Alignment.topCenter,
                child: Container(
                  width: 4,
                  height: 7,
                  decoration: const BoxDecoration(
                    color: kTealDarkLeg,
                    borderRadius: BorderRadius.vertical(bottom: Radius.circular(2)),
                  ),
                ),
              ),
              const SizedBox(width: 2),
              Transform.rotate(
                angle: right,
                alignment: Alignment.topCenter,
                child: Container(
                  width: 4,
                  height: 7,
                  decoration: const BoxDecoration(
                    color: kTealDarkLeg,
                    borderRadius: BorderRadius.vertical(bottom: Radius.circular(2)),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DocChip extends StatelessWidget {
  const _DocChip({required this.dark});

  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 16,
      height: 20,
      padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 3),
      decoration: BoxDecoration(
        color: dark ? Colors.white.withValues(alpha: 0.1) : Colors.white,
        border: Border.all(
          color: dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow,
          width: 1.5,
        ),
        borderRadius: BorderRadius.circular(2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(height: 2, width: double.infinity, color: kTealGlow.withValues(alpha: 0.8)),
          const SizedBox(height: 2),
          Container(height: 2, width: 10, color: kTealGlow.withValues(alpha: 0.8)),
          const SizedBox(height: 2),
          Container(height: 2, width: double.infinity, color: kTealGlow.withValues(alpha: 0.8)),
          const SizedBox(height: 2),
          Container(height: 2, width: 10, color: kTealGlow.withValues(alpha: 0.8)),
        ],
      ),
    );
  }
}
