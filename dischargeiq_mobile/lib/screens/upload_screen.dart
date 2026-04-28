import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/screens/loading_screen.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

/// Design A (light) / Design B (dark) upload; follows [ThemeData] brightness.
class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  Uint8List? _bytes;
  String? _fileName;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf'],
      withData: true,
    );
    if (!mounted || r == null || r.files.isEmpty) return;
    final f = r.files.single;
    final bytes = f.bytes;
    if (bytes == null) return;
    setState(() {
      _bytes = bytes;
      _fileName = f.name;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              height: 52,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    Text(
                      'DischargeIQ',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                        color: _dark ? kTealGlow : kTextPrimaryLight,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      'Patient education only',
                      style: TextStyle(
                        fontSize: 10,
                        color: _dark ? kTextHintDark : kTextHintLight,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Column(
                  children: [
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                      decoration: BoxDecoration(
                        color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: _dark ? kTealGlow.withValues(alpha: 0.2) : kTealGlow,
                          width: 0.5,
                        ),
                      ),
                      child: Text(
                        'Your discharge, simplified',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: _dark ? kTealGlow : kTeal,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text.rich(
                      TextSpan(
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w500,
                          color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                          height: 1.25,
                        ),
                        children: [
                          const TextSpan(text: 'Understand everything\nthe doctor told '),
                          TextSpan(
                            text: 'you.',
                            style: TextStyle(
                              color: _dark ? kTealLight : kTeal,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Upload your PDF. Get plain answers. Go home ready.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 10,
                        color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                    const SizedBox(height: 20),
                    ..._stepTiles(),
                    const SizedBox(height: 16),
                    GestureDetector(
                      onTap: _pickFile,
                      child: CustomPaint(
                        foregroundPainter: _DashedBorderPainter(
                          color: _dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow,
                          strokeWidth: 1.5,
                          radius: 12,
                        ),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: _dark ? kTeal.withValues(alpha: 0.12) : kSurfaceLight,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            children: [
                              Container(
                                width: 40,
                                height: 40,
                                decoration: BoxDecoration(
                                  color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Icon(
                                  Icons.arrow_upward_rounded,
                                  color: _dark ? kTealGlow : kTeal,
                                  size: 22,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Tap to choose your discharge PDF',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: _dark ? kTextHintDark : kTextSecondaryLight,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'PDF format · Up to 200MB',
                                style: TextStyle(
                                  fontSize: 9,
                                  color: _dark ? kTextHintDark : kTextHintLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    if (_fileName != null) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: kTealPale,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          '${_fileName!} · ${_kb(_bytes?.length ?? 0)}',
                          style: const TextStyle(fontSize: 10, color: kTeal),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton(
                        onPressed: _bytes == null
                            ? null
                            : () async {
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute<void>(
                                    builder: (_) => LoadingScreen(
                                      pdfBytes: _bytes!,
                                      fileName: _fileName ?? 'document.pdf',
                                    ),
                                  ),
                                );
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: kTeal,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: kTeal.withValues(alpha: 0.4),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text(
                          'Upload & Analyze',
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.lock_outline, size: 12, color: _dark ? kTextHintDark : kTextHintLight),
                        const SizedBox(width: 4),
                        Text(
                          'Private · Deleted when you close the app',
                          style: TextStyle(
                            fontSize: 9,
                            color: _dark ? kTextHintDark : kTextHintLight,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _stepTiles() {
    const steps = [
      ('1', 'Your diagnosis', 'In words a friend would use'),
      ('2', 'Your medications', 'What each pill does and why'),
      ('3', 'Warning signs', 'When to call 911 vs your doctor'),
      ('4', 'Ask anything', 'AI chat from your document'),
    ];
    return steps.map((s) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: _dark ? kTeal.withValues(alpha: 0.15) : kSurfaceLight,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: _dark ? kTealMid.withValues(alpha: 0.2) : kBorderLight,
              width: 0.5,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 20,
                height: 20,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _dark ? kTealGlow.withValues(alpha: 0.15) : kTealPale,
                  shape: BoxShape.circle,
                ),
                child: Text(
                  s.$1,
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: _dark ? kTealLight : kTeal,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      s.$2,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    Text(
                      s.$3,
                      style: TextStyle(
                        fontSize: 9,
                        color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }

  static String _kb(int b) {
    if (b < 1024) return '$b B';
    return '${(b / 1024).toStringAsFixed(1)} KB';
  }
}

class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({
    required this.color,
    this.strokeWidth = 1.5,
    this.radius = 12,
  });

  final Color color;
  final double strokeWidth;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(
      Rect.fromLTWH(strokeWidth / 2, strokeWidth / 2, size.width - strokeWidth, size.height - strokeWidth),
      Radius.circular(radius),
    );
    final path = Path()..addRRect(r);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    _drawDashedPath(canvas, path, paint, dash: 6, gap: 4);
  }

  void _drawDashedPath(Canvas canvas, Path path, Paint paint, {required double dash, required double gap}) {
    for (final metric in path.computeMetrics()) {
      double d = 0;
      while (d < metric.length) {
        final next = d + dash;
        final extract = metric.extractPath(d, next.clamp(0, metric.length));
        canvas.drawPath(extract, paint);
        d = next + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedBorderPainter oldDelegate) {
    return oldDelegate.color != color ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.radius != radius;
  }
}
