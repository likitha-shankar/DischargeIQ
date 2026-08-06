/// services/document_store.dart
///
/// On-device document library (decision D-6): every successful analysis is
/// saved to the app's PRIVATE documents directory - the analysis result JSON
/// plus the original PDF when one exists - so the patient can reopen past
/// documents without re-uploading (and without re-burning pipeline quota).
/// Nothing here ever touches the server or the database; deleting the app
/// deletes the library. Every method is best-effort: storage failures must
/// never break the analyze flow.
library;

import 'dart:convert' show jsonDecode, jsonEncode;
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'package:dischargeiq_mobile/services/learning_goals.dart';

/// True when a partial run produced nothing a patient can use: extraction
/// failed (the orchestrator's sentinel) or every narrative section is empty.
/// Typical cause: model quota exhausted mid-run. Shared by the results
/// screen (render a friendly failed screen), the loading screen (skip
/// saving), and the library (purge legacy entries).
bool isUnusableRun(Map<String, dynamic> r) {
  if ('${r['pipeline_status']}' != 'partial') return false;
  final ex = r['extraction'];
  final extractionFailed =
      ex is! Map || '${ex['primary_diagnosis'] ?? ''}' == 'Extraction failed';
  final allEmpty = [
    'diagnosis_explanation',
    'medication_rationale',
    'recovery_trajectory',
    'escalation_guide',
  ].every((k) {
    final t = '${r[k] ?? ''}'.trim();
    return t.isEmpty || t == 'null';
  });
  return extractionFailed || allEmpty;
}

/// One saved analysis: metadata for the list row + file locations.
class SavedDocument {
  const SavedDocument({
    required this.id,
    required this.fileName,
    required this.diagnosis,
    required this.savedAt,
    required this.hasPdf,
    this.personId,
  });

  final String id;
  final String fileName;
  final String diagnosis;
  final DateTime savedAt;
  final bool hasPdf;

  /// Person this document belongs to, or null for documents saved before
  /// people existed. Those stay readable and can be filed later - an
  /// unassigned document is a tidying task, never a lost one.
  final String? personId;
}

/// The app's Documents directory, healed if a stray FILE is squatting on the
/// path.
///
/// Observed on a real device after a container restore went wrong: a file
/// named "Documents" sat where the directory belongs, so every write under it
/// failed - profile saves returned "could not save" forever and analysed
/// documents silently never reached the library, with no error surfaced
/// anywhere. Both stores route through this so one repair fixes both.
Future<Directory> healedDocumentsDir() async {
  final base = await getApplicationDocumentsDirectory();
  final asDir = Directory(base.path);
  if (!await asDir.exists()) {
    final squatter = File(base.path);
    if (await squatter.exists()) await squatter.delete();
    await asDir.create(recursive: true);
  }
  return asDir;
}

class DocumentStore {
  static Future<Directory> _dir() async {
    final base = await healedDocumentsDir();
    final dir = Directory('${base.path}/saved_documents');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  /// A document id that is not already taken.
  ///
  /// The id was the millisecond timestamp alone, which collides when two
  /// documents are saved inside the same millisecond - the second write then
  /// silently overwrote the first, losing a saved discharge summary. Measured:
  /// eight rapid saves produced six documents. The suffix loop makes the id
  /// unique without changing its sortable timestamp prefix.
  static Future<String> _nextId(Directory dir) async {
    final base = DateTime.now().millisecondsSinceEpoch.toString();
    if (!await File('${dir.path}/$base.json').exists()) return base;
    for (var suffix = 1; suffix < 1000; suffix++) {
      final candidate = '$base-$suffix';
      if (!await File('${dir.path}/$candidate.json').exists()) return candidate;
    }
    // A thousand documents in one millisecond is not a real scenario; fall
    // back to microseconds rather than returning a known-colliding id.
    return DateTime.now().microsecondsSinceEpoch.toString();
  }

  /// Persist one successful analysis. Rejected documents are not saved -
  /// there is nothing for the patient to come back to.
  ///
  /// Returns the new document id (callers use it to scope per-document
  /// engagement state, e.g. SectionStarStore), or null when nothing was
  /// saved (rejected run or write failure).
  static Future<String?> save({
    required Map<String, dynamic> result,
    required String fileName,
    Uint8List? pdfBytes,
    String? personId,
  }) async {
    try {
      if ('${result['pipeline_status']}' == 'rejected') return null;
      final dir = await _dir();
      final id = await _nextId(dir);
      final extraction = result['extraction'];
      final diagnosis = (extraction is Map)
          ? '${extraction['primary_diagnosis'] ?? 'Discharge summary'}'
          : 'Discharge summary';
      if (pdfBytes != null) {
        await File('${dir.path}/$id.pdf').writeAsBytes(pdfBytes);
      }
      await File('${dir.path}/$id.json').writeAsString(jsonEncode({
        'file_name': fileName,
        'diagnosis': diagnosis,
        'saved_at': DateTime.now().toIso8601String(),
        if (personId != null) 'person_id': personId,
        'result': result,
      }));
      return id;
    } catch (_) {
      // Best-effort: a full disk or sandbox hiccup must not fail the analysis.
      return null;
    }
  }

  /// All saved documents, newest first. Corrupt entries are skipped.
  static Future<List<SavedDocument>> list() async {
    try {
      final dir = await _dir();
      final docs = <SavedDocument>[];
      await for (final f in dir.list()) {
        if (f is! File || !f.path.endsWith('.json')) continue;
        try {
          final meta = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
          final id = f.uri.pathSegments.last.replaceAll('.json', '');
          docs.add(SavedDocument(
            id: id,
            fileName: '${meta['file_name'] ?? 'document'}',
            diagnosis: '${meta['diagnosis'] ?? ''}',
            savedAt: DateTime.tryParse('${meta['saved_at']}') ?? DateTime(2000),
            hasPdf: await File('${dir.path}/$id.pdf').exists(),
            personId: meta['person_id'] is String
                ? meta['person_id'] as String
                : null,
          ));
        } catch (_) {
          continue; // skip one bad file, keep the rest of the library
        }
      }
      docs.sort((a, b) => b.savedAt.compareTo(a.savedAt));
      return docs;
    } catch (_) {
      return const [];
    }
  }

  /// Narrow a document list to one person, or return it whole for "All".
  ///
  /// Every surface that shows documents per profile - the library, the
  /// recovery journey, the puzzle picker - must agree on what a profile owns.
  /// The journey card once listed its own way and showed another profile's
  /// progress, so the rule lives here and each caller reuses it.
  ///
  /// Args:
  ///   all:      Documents from [list], newest first.
  ///   personId: Profile to narrow to; null means every document.
  ///
  /// Returns:
  ///   The documents belonging to that person, in the order given.
  static List<SavedDocument> forPerson(
    List<SavedDocument> all,
    String? personId,
  ) =>
      personId == null
          ? all
          : all.where((d) => d.personId == personId).toList();

  /// File an existing document under a person, or clear it with a null id.
  ///
  /// Used when someone adds people after already saving documents, and when a
  /// person is deleted and their documents need refiling. Rewrites only the
  /// metadata key, leaving the stored analysis untouched.
  static Future<bool> assignPerson(String id, String? personId) async {
    try {
      final dir = await _dir();
      final file = File('${dir.path}/$id.json');
      final meta = (jsonDecode(await file.readAsString()) as Map)
          .cast<String, dynamic>();
      if (personId == null) {
        meta.remove('person_id');
      } else {
        meta['person_id'] = personId;
      }
      await file.writeAsString(jsonEncode(meta));
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Load one saved analysis result (and PDF bytes when present).
  /// Returns null when the entry is missing or unreadable. Legacy entries
  /// saved before the dead-run filter existed are purged here on contact -
  /// the library self-heals instead of resurfacing a quota-dead analysis.
  static Future<(Map<String, dynamic>, Uint8List?)?> load(String id) async {
    try {
      final dir = await _dir();
      final meta = jsonDecode(await File('${dir.path}/$id.json').readAsString())
          as Map<String, dynamic>;
      final result = (meta['result'] as Map).cast<String, dynamic>();
      if (isUnusableRun(result)) {
        await delete(id);
        return null;
      }
      final pdfFile = File('${dir.path}/$id.pdf');
      final pdf = await pdfFile.exists() ? await pdfFile.readAsBytes() : null;
      return (result, pdf);
    } catch (_) {
      return null;
    }
  }

  /// Remove one saved document (json + pdf) and the per-document engagement
  /// state keyed to it. Best-effort.
  ///
  /// Ids are timestamps, so a future document could in principle reuse one.
  /// Clearing the learning goals here means a new document can never open
  /// showing the goals and self-ratings of a deleted one.
  static Future<void> delete(String id) async {
    try {
      final dir = await _dir();
      for (final ext in const ['.json', '.pdf']) {
        final f = File('${dir.path}/$id$ext');
        if (await f.exists()) await f.delete();
      }
    } catch (_) {}
    await LearningGoalStore.clear(id);
  }
}
