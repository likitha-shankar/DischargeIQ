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
    this.customTitle,
  });

  final String id;
  final String fileName;
  final String diagnosis;
  final DateTime savedAt;
  final bool hasPdf;

  /// A name the patient typed, or null to use the generated one.
  ///
  /// Stored ALONGSIDE the extracted diagnosis rather than replacing it. The
  /// generated title comes from `primary_diagnosis`, which is clinical
  /// content the rest of the app reads; overwriting it to change a label
  /// would edit the extraction record to fix a display string.
  ///
  /// It also has to be reversible. A patient who renames a document and later
  /// wants the clinical name back would otherwise have no way to recover it
  /// short of re-uploading.
  final String? customTitle;

  /// What the library should show: the patient's name for it, else the
  /// diagnosis, else the file name.
  ///
  /// One getter so every surface agrees. The row, the delete confirmation and
  /// any future share sheet must not disagree about what a document is
  /// called - a dialog saying `"camera-scan-3p" will be removed` about a
  /// document the patient renamed "Mum's heart summary" reads as a different
  /// document, which is a bad moment for a destructive action.
  String get displayTitle {
    final custom = (customTitle ?? '').trim();
    if (custom.isNotEmpty) return custom;
    return diagnosis.isNotEmpty ? diagnosis : fileName;
  }

  /// True when the patient has given this document their own name.
  bool get isRenamed => (customTitle ?? '').trim().isNotEmpty;

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

  /// The id of a saved document with this `document_hash`, or null.
  ///
  /// Returns the OLDEST match, so repeated re-uploads keep converging on one
  /// entry rather than hopping between duplicates created before this
  /// existed.
  static Future<String?> _existingIdForHash(Directory dir, String hash) async {
    if (hash.isEmpty) return null;
    final matches = <String>[];
    await for (final entry in dir.list()) {
      if (entry is! File || !entry.path.endsWith('.json')) continue;
      try {
        final meta =
            jsonDecode(await entry.readAsString()) as Map<String, dynamic>;
        if ('${meta['document_hash'] ?? ''}' == hash) {
          matches.add(entry.uri.pathSegments.last.replaceAll('.json', ''));
        }
      } catch (_) {
        continue; // one unreadable entry must not block the match
      }
    }
    if (matches.isEmpty) return null;
    matches.sort();
    return matches.first;
  }

  /// The person a saved document is filed under, or null.
  ///
  /// Null covers three cases that behave the same way here: no such entry,
  /// an unreadable one, and one that was never filed.
  static Future<String?> _personIdOf(Directory dir, String id) async {
    try {
      final file = File('${dir.path}/$id.json');
      if (!await file.exists()) return null;
      final meta = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      return meta['person_id'] is String ? meta['person_id'] as String : null;
    } catch (_) {
      return null;
    }
  }

  /// The patient's own name for a saved document, or null.
  static Future<String?> _customTitleOf(Directory dir, String id) async {
    try {
      final file = File('${dir.path}/$id.json');
      if (!await file.exists()) return null;
      final meta = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      final title = meta['custom_title'];
      return title is String && title.trim().isNotEmpty ? title : null;
    } catch (_) {
      return null;
    }
  }

  /// Persist one successful analysis. Rejected documents are not saved -
  /// there is nothing for the patient to come back to.
  ///
  /// Re-uploading a document already in the library UPDATES that entry in
  /// place and returns its existing id, rather than adding a second copy.
  ///
  /// That is not tidiness. Ten stores key off the document id - appointment
  /// ticks and edits, weights, doses, recovery notes, the corrected discharge
  /// date, learning goals, section stars, quiz bests. A duplicate entry gets
  /// a new id, so every one of those reads back empty: the patient's own
  /// work is orphaned under the old id, still on disk and unreachable.
  /// Nothing throws and nothing looks broken. It simply appears as though
  /// they never did any of it, and the recovery activity dots - which read
  /// those same ticks - quietly empty out with it.
  ///
  /// Matching is on the server's `document_hash`, the same SHA-256 the
  /// /analyze cache keys on, so client and server cannot disagree about what
  /// counts as the same document. A genuinely revised summary hashes
  /// differently and correctly lands as a new entry.
  ///
  /// Returns the document id (callers use it to scope per-document
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
      final hash = '${result['document_hash'] ?? ''}';
      // Absent on documents saved before the server sent a hash, and on a
      // client running ahead of the deploy. Both fall back to the old
      // behaviour - a new entry - which is wrong but no worse than before.
      final existing = await _existingIdForHash(dir, hash);
      final id = existing ?? await _nextId(dir);
      final extraction = result['extraction'];
      final diagnosis = (extraction is Map)
          ? '${extraction['primary_diagnosis'] ?? 'Discharge summary'}'
          : 'Discharge summary';
      if (pdfBytes != null) {
        await File('${dir.path}/$id.pdf').writeAsBytes(pdfBytes);
      }
      // Updating an entry must not silently unfile it. A re-upload made
      // before any profiles exist carries a null personId, and writing that
      // over an existing assignment would move a filed document into the
      // Unassigned bucket for no reason the patient could see.
      final owner = personId ?? await _personIdOf(dir, id);
      // A re-upload must not silently rename the document back. The patient
      // named it; a fresh analysis of the same paperwork does not withdraw
      // that. Same reasoning as the person assignment above.
      final title = await _customTitleOf(dir, id);
      await File('${dir.path}/$id.json').writeAsString(jsonEncode({
        'file_name': fileName,
        'diagnosis': diagnosis,
        // Refreshed on an update: the entry genuinely was just re-analysed,
        // and the library sorts newest-first, so it surfaces where the
        // patient has just been looking.
        'saved_at': DateTime.now().toIso8601String(),
        if (owner != null) 'person_id': owner,
        if (title != null) 'custom_title': title,
        if (hash.isNotEmpty) 'document_hash': hash,
        'result': result,
      }));
      return id;
    } catch (_) {
      // Best-effort: a full disk or sandbox hiccup must not fail the analysis.
      return null;
    }
  }

  /// Give a document the patient's own name, or clear it back to generated.
  ///
  /// Args:
  ///   id: Document to rename.
  ///   title: The new name. Null, empty or whitespace CLEARS the override, so
  ///     the generated diagnosis title comes back - renaming is reversible
  ///     without re-uploading.
  ///
  /// Returns:
  ///   bool: True when the change was written.
  ///
  /// Note:
  ///   Only the label is touched. `result`, and the extracted
  ///   `primary_diagnosis` inside it, are rewritten byte-for-byte as they
  ///   were - a display preference must never edit the clinical record it is
  ///   displaying.
  static Future<bool> rename(String id, String? title) async {
    try {
      final dir = await _dir();
      final file = File('${dir.path}/$id.json');
      if (!await file.exists()) return false;
      final meta = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      final cleaned = (title ?? '').trim();
      if (cleaned.isEmpty) {
        meta.remove('custom_title');
      } else {
        // Bounded so one pasted paragraph cannot make every library row
        // unreadable. Truncation is silent because the field is also
        // length-limited in the dialog; this is the backstop.
        meta['custom_title'] =
            cleaned.length > 80 ? cleaned.substring(0, 80) : cleaned;
      }
      await file.writeAsString(jsonEncode(meta));
      return true;
    } catch (_) {
      return false;
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
            customTitle: meta['custom_title'] is String
                ? meta['custom_title'] as String
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
