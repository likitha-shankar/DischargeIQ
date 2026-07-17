/// services/scan_session_store.dart
///
/// Persists the in-progress camera-scan session (OCR text per page) to the
/// app's PRIVATE documents directory so a half-finished scan survives an app
/// restart - a patient who photographed 5 pages must never lose them to a
/// crash or a phone reboot. On-device only, best-effort: storage failures
/// never break the scan flow. Cleared when a new PDF analysis starts.
library;

import 'dart:convert' show jsonDecode, jsonEncode;
import 'dart:io';

import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:path_provider/path_provider.dart';

class ScanSessionStore {
  static Future<File> _file() async {
    final base = await getApplicationDocumentsDirectory();
    return File('${base.path}/scan_session.json');
  }

  /// Persist the current page list. Empty list deletes the file.
  static Future<void> save(List<ScannedPageData> pages) async {
    try {
      final f = await _file();
      if (pages.isEmpty) {
        if (await f.exists()) await f.delete();
        return;
      }
      await f.writeAsString(jsonEncode([
        for (final p in pages)
          {'text': p.text, 'blockCount': p.blockCount, 'imagePath': p.imagePath},
      ]));
    } catch (_) {
      // Best-effort: a failed save must never break scanning.
    }
  }

  /// Restore a previously saved session; [] when none exists or unreadable.
  /// Image files may have been purged by the OS since - the OCR text is the
  /// part that matters for analysis, so pages are restored regardless.
  static Future<List<ScannedPageData>> load() async {
    try {
      final f = await _file();
      if (!await f.exists()) return [];
      final raw = jsonDecode(await f.readAsString());
      if (raw is! List) return [];
      return [
        for (final e in raw.whereType<Map>())
          ScannedPageData(
            text: '${e['text'] ?? ''}',
            blockCount: (e['blockCount'] as num?)?.toInt() ?? 0,
            imagePath: '${e['imagePath'] ?? ''}',
          ),
      ];
    } catch (_) {
      return [];
    }
  }

  static Future<void> clear() => save(const []);
}
