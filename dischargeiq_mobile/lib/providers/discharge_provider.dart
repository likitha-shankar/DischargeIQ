import 'dart:typed_data';

import 'package:flutter/foundation.dart';

/// In-memory pipeline result and last upload metadata (cleared when app closes).
class DischargeProvider extends ChangeNotifier {
  Map<String, dynamic>? _result;
  Uint8List? _lastPdfBytes;
  String _lastFileName = 'document.pdf';

  Map<String, dynamic>? get result => _result;
  Uint8List? get lastPdfBytes => _lastPdfBytes;
  String get lastFileName => _lastFileName;

  bool get hasResult => _result != null;

  void setResult(
    Map<String, dynamic> data, {
    Uint8List? pdfBytes,
    String? fileName,
  }) {
    _result = data;
    if (pdfBytes != null) _lastPdfBytes = pdfBytes;
    if (fileName != null) _lastFileName = fileName;
    notifyListeners();
  }

  void clear() {
    _result = null;
    _lastPdfBytes = null;
    _lastFileName = 'document.pdf';
    notifyListeners();
  }
}
