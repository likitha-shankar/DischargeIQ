/// screens/scan_screen.dart
///
/// Camera scan path (Sprint 2, Task 2.2): photograph the paper discharge
/// document page by page, recognize text ON-DEVICE with Google ML Kit, review
/// the combined text, and send only the text to POST /analyze/text.
///
/// Privacy property: the photo never leaves the phone. Only recognized text
/// crosses the wire - images of paper medical documents stay on-device.
///
/// Density check: ML Kit needs roughly >16x16 px per character for reliable
/// recognition. Rather than measuring glyphs, we use a practical proxy - a
/// page that produced very little text triggers a retake prompt.
library;

import 'dart:io';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/screens/loading_screen.dart';
import 'package:dischargeiq_mobile/services/scan_session_store.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

/// Practical scan-quality proxy: a real discharge page yields hundreds of
/// characters. Below this the photo was likely blurry, dark, or cropped.
bool _looksPoor(ScannedPageData p) => p.text.trim().length < 120;

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _picker = ImagePicker();
  // Pages live in the provider so they survive analyze → results → "add more
  // pages" round trips. This is a reference, not a copy - mutations persist.
  late final List<ScannedPageData> _pages =
      context.read<DischargeProvider>().scanPages;
  bool _busy = false;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  @override
  void initState() {
    super.initState();
    // Restore a scan session interrupted by an app restart. Only when the
    // in-memory session is empty - a live session always wins.
    if (_pages.isEmpty) {
      ScanSessionStore.load().then((saved) {
        if (mounted && saved.isNotEmpty && _pages.isEmpty) {
          setState(() => _pages.addAll(saved));
        }
      });
    }
  }

  /// Persist after every mutation so a crash never loses scanned pages.
  void _persist() => ScanSessionStore.save(List.of(_pages));

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
        final page = ScannedPageData(
          text: result.text,
          blockCount: result.blocks.length,
          imagePath: shot.path,
        );
        if (!mounted) return;
        setState(() => _pages.add(page));
        _persist();
        if (_looksPoor(page)) {
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
    final outcome = await Navigator.push<Object?>(
      context,
      MaterialPageRoute<Object?>(
        builder: (_) => LoadingScreen(
          ocrText: text,
          fileName: 'camera-scan-${_pages.length}p',
        ),
      ),
    );
    // 'add_pages' = patient backed out to add a page - stay here, pages kept.
    if (outcome == 'add_pages') return;
    // LoadingScreen pops back here after setting the provider result; the
    // upload screen underneath reacts to the provider and shows results.
    if (mounted && context.mounted) Navigator.of(context).maybePop();
  }

  /// Opt-in enhanced cloud read: uploads the ORIGINAL PHOTOS so Gemini vision
  /// can transcribe handwriting the on-device recognizer cannot. Requires an
  /// explicit confirmation because it breaks the default photos-stay-on-phone
  /// rule - the patient must know and choose.
  Future<void> _analyzeEnhanced() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Use enhanced reading?'),
        content: const Text(
          'Your page photos will be uploaded securely so a stronger reader '
          'can transcribe handwriting. Photos are processed in memory and '
          'never stored on the server.\n\nUse the standard scan if you prefer '
          'photos to stay on this phone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: kTeal),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Upload & read'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final outcome = await Navigator.push<Object?>(
      context,
      MaterialPageRoute<Object?>(
        builder: (_) => LoadingScreen(
          imagePaths: [for (final p in _pages) p.imagePath],
          fileName: 'enhanced-scan-${_pages.length}p',
        ),
      ),
    );
    if (outcome == 'add_pages') return;
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
        actions: [
          // Pages persist across the app on purpose (add-more-pages flow);
          // this is the explicit way to abandon a scan session.
          if (_pages.isNotEmpty)
            TextButton(
              onPressed: _busy
                  ? null
                  : () { setState(_pages.clear); _persist(); },
              child: const Text('Start over',
                  style: TextStyle(color: Colors.white, fontSize: 13)),
            ),
        ],
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
                  'Photograph each page of your discharge papers. Lay one '
                  'page at a time on a clear surface and fill the frame - '
                  'the camera reads everything it can see. Standard reading '
                  'happens on your phone - photos are not uploaded. For '
                  'handwritten notes, use "Enhanced read" below (uploads '
                  'photos securely, with your permission).',
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
                    // Long-press-drag to reorder: page order = reading order
                    // for OCR text, so the patient can fix out-of-order shots
                    // instead of retaking them.
                    : ReorderableListView.builder(
                        itemCount: _pages.length,
                        onReorder: (from, to) => setState(() {
                          if (to > from) to--;
                          _pages.insert(to, _pages.removeAt(from));
                          _persist();
                        }),
                        itemBuilder: (context, i) {
                          final p = _pages[i];
                          return Container(
                            key: ObjectKey(p),
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: _dark ? kCardDark : kCardLight,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: _looksPoor(p)
                                    ? kTier2
                                    : (_dark ? kBorderDark : kBorderLight),
                                width: _looksPoor(p) ? 1.5 : 1,
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Icon(Icons.drag_indicator,
                                        size: 18,
                                        color: _dark
                                            ? kTextHintDark
                                            : kTextHintLight),
                                    const SizedBox(width: 4),
                                    Text('Page ${i + 1}',
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w700)),
                                    const SizedBox(width: 8),
                                    if (_looksPoor(p))
                                      const Text('⚠ low text - retake?',
                                          style: TextStyle(
                                              fontSize: 12, color: kTier2)),
                                    const Spacer(),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline, size: 20),
                                      tooltip: 'Remove page',
                                      onPressed: () {
                                        setState(() => _pages.removeAt(i));
                                        _persist();
                                      },
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
              const SizedBox(height: 8),
              // Enhanced cloud read: available whenever pages exist - no
              // minimum-text gate, because handwriting often yields almost
              // nothing on-device (which is exactly when this path helps).
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _dark ? kTealGlow : kTeal,
                  side: BorderSide(color: _dark ? kTealGlow : kTeal),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: (_pages.isNotEmpty && !_busy) ? _analyzeEnhanced : null,
                icon: const Icon(Icons.auto_fix_high_outlined, size: 18),
                label: const Text('Handwritten or hard to read? Enhanced read'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
