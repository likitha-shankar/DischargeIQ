/// screens/scan_screen.dart
///
/// Camera scan path (Sprint 2, Task 2.2): photograph the paper discharge
/// document page by page, recognize text ON-DEVICE with Google ML Kit, review
/// the combined text, and send only the text to POST /analyze/text.
///
/// Privacy property: the photo never leaves the phone. Only recognized text
/// crosses the wire — images of paper medical documents stay on-device.
///
/// Density check: ML Kit needs roughly >16x16 px per character for reliable
/// recognition. Rather than measuring glyphs, we use a practical proxy — a
/// page that produced very little text triggers a retake prompt.
library;

import 'dart:io';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/screens/loading_screen.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';

/// One captured page: recognized text + basic quality info.
class _ScannedPage {
  _ScannedPage({required this.text, required this.blockCount});

  final String text;
  final int blockCount;

  /// Practical scan-quality proxy: a real discharge page yields hundreds of
  /// characters. Below this the photo was likely blurry, dark, or cropped.
  bool get looksPoor => text.trim().length < 120;
}

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _picker = ImagePicker();
  final List<_ScannedPage> _pages = [];
  bool _busy = false;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  Future<void> _capture(ImageSource source) async {
    setState(() => _busy = true);
    try {
      final shot = await _picker.pickImage(
        source: source,
        // Cap the long edge well above ML Kit's density needs while keeping
        // on-device processing fast; no compression artifacts at 92.
        maxWidth: 2400,
        imageQuality: 92,
      );
      if (shot == null) return; // user cancelled the camera sheet

      final recognizer = TextRecognizer(script: TextRecognitionScript.latin);
      try {
        final result =
            await recognizer.processImage(InputImage.fromFile(File(shot.path)));
        final page = _ScannedPage(
          text: result.text,
          blockCount: result.blocks.length,
        );
        if (!mounted) return;
        setState(() => _pages.add(page));
        if (page.looksPoor) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text(
              'That page captured very little text. Retake it with the full '
              'page visible and good lighting, then remove this one.',
            ),
            duration: Duration(seconds: 5),
          ));
        }
      } finally {
        await recognizer.close();
      }
    } catch (err) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not read that photo. $err')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String get _combinedText => [
        for (var i = 0; i < _pages.length; i++)
          '[PAGE ${i + 1}]\n${_pages[i].text.trim()}'
      ].join('\n\n');

  Future<void> _analyze() async {
    final text = _combinedText;
    await Navigator.push<void>(
      context,
      MaterialPageRoute<void>(
        builder: (_) => LoadingScreen(
          ocrText: text,
          fileName: 'camera-scan-${_pages.length}p',
        ),
      ),
    );
    // LoadingScreen pops back here after setting the provider result; the
    // upload screen underneath reacts to the provider and shows results.
    if (mounted && context.mounted) Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    final totalChars = _pages.fold<int>(0, (n, p) => n + p.text.trim().length);
    final canAnalyze = _pages.isNotEmpty && totalChars >= 120 && !_busy;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('Scan your document'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _dark ? kCardDark : kTealPale,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'Photograph each page of your discharge papers. Reading '
                  'happens on your phone — the photos are never uploaded.',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: _dark ? kTextSecondaryDark : kTextPrimaryLight,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Expanded(
                child: _pages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.document_scanner_outlined,
                                size: 56,
                                color: _dark ? kTealGlow : kTealMid),
                            const SizedBox(height: 12),
                            Text(
                              'No pages scanned yet',
                              style: TextStyle(
                                color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.separated(
                        itemCount: _pages.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, i) {
                          final p = _pages[i];
                          return Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: _dark ? kCardDark : kCardLight,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: p.looksPoor
                                    ? kTier2
                                    : (_dark ? kBorderDark : kBorderLight),
                                width: p.looksPoor ? 1.5 : 1,
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text('Page ${i + 1}',
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w700)),
                                    const SizedBox(width: 8),
                                    if (p.looksPoor)
                                      const Text('⚠ low text — retake?',
                                          style: TextStyle(
                                              fontSize: 12, color: kTier2)),
                                    const Spacer(),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline, size: 20),
                                      tooltip: 'Remove page',
                                      onPressed: () =>
                                          setState(() => _pages.removeAt(i)),
                                    ),
                                  ],
                                ),
                                Text(
                                  p.text.trim(),
                                  maxLines: 3,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 12.5,
                                    height: 1.35,
                                    color: _dark
                                        ? kTextSecondaryDark
                                        : kTextSecondaryLight,
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _busy ? null : () => _capture(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: const Text('From photos'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: kTealMid),
                      onPressed: _busy ? null : () => _capture(ImageSource.camera),
                      icon: _busy
                          ? const SizedBox(
                              width: 16, height: 16,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.photo_camera_outlined),
                      label: Text(_pages.isEmpty ? 'Scan a page' : 'Add a page'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: kTeal,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: canAnalyze ? _analyze : null,
                child: Text(
                  _pages.isEmpty
                      ? 'Analyze'
                      : 'Analyze ${_pages.length} ${_pages.length == 1 ? "page" : "pages"}',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
