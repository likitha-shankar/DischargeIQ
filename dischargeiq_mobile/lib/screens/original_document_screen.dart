/// screens/original_document_screen.dart
///
/// "View original" (patient trust feature): shows exactly what the analysis
/// was built from - the uploaded PDF (rendered natively via pdfx/PDFKit) or
/// the scanned page photos (straight from local files). Pure viewer, no
/// network: the bytes are already on the device.
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

/// Viewer for the original PDF bytes.
class OriginalPdfScreen extends StatefulWidget {
  const OriginalPdfScreen({super.key, required this.pdfBytes, required this.fileName});

  final Uint8List pdfBytes;
  final String fileName;

  @override
  State<OriginalPdfScreen> createState() => _OriginalPdfScreenState();
}

class _OriginalPdfScreenState extends State<OriginalPdfScreen> {
  late final PdfControllerPinch _controller = PdfControllerPinch(
    document: PdfDocument.openData(widget.pdfBytes),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: Text(widget.fileName, style: const TextStyle(fontSize: 15)),
      ),
      body: PdfViewPinch(controller: _controller),
    );
  }
}

/// Viewer for scanned page photos (swipe between pages, pinch to zoom).
class OriginalPhotosScreen extends StatelessWidget {
  const OriginalPhotosScreen({super.key, required this.imagePaths});

  final List<String> imagePaths;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: Text('Scanned pages (${imagePaths.length})',
            style: const TextStyle(fontSize: 15)),
      ),
      body: PageView.builder(
        itemCount: imagePaths.length,
        itemBuilder: (context, i) {
          final file = File(imagePaths[i]);
          return InteractiveViewer(
            maxScale: 5,
            child: Center(
              child: file.existsSync()
                  ? Image.file(file)
                  : const Padding(
                      padding: EdgeInsets.all(32),
                      child: Text(
                        'This photo is no longer available - scan photos are '
                        'temporary and cleared by the system over time.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.white70),
                      ),
                    ),
            ),
          );
        },
      ),
    );
  }
}
