import 'package:dischargeiq_mobile/services/scan_session_store.dart';
import 'package:flutter/foundation.dart';

/// One camera-scanned page. Lives in the provider so pages SURVIVE the
/// scan → analyze → results round trip: a patient who scanned only page 1
/// can come back, add page 2, and re-analyze without re-photographing.
class ScannedPageData {
  const ScannedPageData({
    required this.text,
    required this.blockCount,
    required this.imagePath,
  });

  final String text;
  final int blockCount;
  final String imagePath;
}

/// In-memory pipeline result and last upload metadata (cleared when app closes).
class DischargeProvider extends ChangeNotifier {
  Map<String, dynamic>? _result;
  Uint8List? _lastPdfBytes;
  String _lastFileName = 'document.pdf';
  String? _activeDocId;

  /// Scan-session pages. Mutated in place by the scan screen; intentionally
  /// not wired into notifyListeners (only the scan screen reads it).
  final List<ScannedPageData> scanPages = [];

  Map<String, dynamic>? get result => _result;
  Uint8List? get lastPdfBytes => _lastPdfBytes;
  String get lastFileName => _lastFileName;

  /// DocumentStore id of the active analysis, or null when it was not saved
  /// (rejected/dead runs). Scopes per-document engagement state - section
  /// stars are awarded against this id, never globally.
  String? get activeDocId => _activeDocId;

  bool get hasResult => _result != null;

  /// True when the current result came from the camera-scan path - the only
  /// path where "add more pages" makes sense.
  bool get isScanSession =>
      _lastFileName.startsWith('camera-scan') ||
      _lastFileName.startsWith('enhanced-scan');

  void setResult(
    Map<String, dynamic> data, {
    Uint8List? pdfBytes,
    String? fileName,
    String? docId,
  }) {
    _result = data;
    _activeDocId = docId;
    if (pdfBytes != null) {
      _lastPdfBytes = pdfBytes;
      // A fresh PDF analysis makes any old camera-scan session stale -
      // in memory and on disk.
      scanPages.clear();
      ScanSessionStore.clear();
    }
    if (fileName != null) _lastFileName = fileName;
    notifyListeners();
  }

  void clear() {
    _result = null;
    _lastPdfBytes = null;
    _lastFileName = 'document.pdf';
    _activeDocId = null;
    notifyListeners();
  }
}
