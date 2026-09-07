/// services/recovery_notes.dart
///
/// Patient and care-team annotations on the recovery timeline.
///
/// Three kinds, deliberately NOT collapsed into one "edit" concept, because
/// who changed a clinical instruction is the whole question:
///
///   note        - the patient adds their own line. The hospital's text is
///                 untouched; the note sits beside it, labelled.
///   patientEdit - the patient rewrites one instruction. The original is kept
///                 forever and shown on demand, and the line is marked as
///                 changed by them. Nothing here reaches the care team.
///   correction  - someone clinical fixes a wrong instruction, recording who
///                 they are. Also keeps the original.
///
/// The safety rule this file exists to enforce: an edited instruction must
/// never be indistinguishable from what the hospital actually wrote. Every
/// override therefore carries its [RecoveryEdit.original] and an author, and
/// the UI is expected to show both. A store that quietly replaced text would
/// leave a patient reading their own guess in the hospital's voice.
///
/// Storage is per document and local to the device (SharedPreferences). None
/// of this syncs anywhere: a "correction" is a note from a clinician sitting
/// with the patient, NOT an authenticated clinical record, and the wording in
/// the UI must not imply otherwise.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Who authored an override, and therefore how much weight it carries.
enum RecoveryEditKind { note, patientEdit, correction }

/// One annotation against one line of the recovery timeline.
class RecoveryEdit {
  const RecoveryEdit({
    required this.kind,
    required this.phase,
    required this.text,
    this.bulletIndex,
    this.original,
    this.author,
    this.createdAt,
  });

  final RecoveryEditKind kind;

  /// Phase title the annotation belongs to ("Week 3-4"). Phases are matched
  /// by title rather than index: Agent 4 can return a different number of
  /// phases on a re-run, and an index would then point at the wrong week.
  final String phase;

  /// The replacement text, or the note's body.
  final String text;

  /// Which bullet was overridden. Null for a standalone note, which belongs
  /// to the phase rather than to any one line.
  final int? bulletIndex;

  /// What the document said before. Null only for a note, which replaces
  /// nothing. An override without this is invalid - see [isValid].
  final String? original;

  /// Name and role for a [RecoveryEditKind.correction]; null otherwise.
  final String? author;

  final DateTime? createdAt;

  /// An override must be traceable back to what it replaced, and a
  /// correction must name someone. Enforced on the way in, so nothing
  /// unattributable can be written to storage at all.
  bool get isValid {
    if (text.trim().isEmpty) return false;
    if (kind == RecoveryEditKind.note) return true;
    if (original == null || bulletIndex == null) return false;
    if (kind == RecoveryEditKind.correction) {
      return (author ?? '').trim().isNotEmpty;
    }
    return true;
  }

  /// Short label the UI puts on the changed line.
  String get attribution => switch (kind) {
        RecoveryEditKind.note => 'Your note',
        RecoveryEditKind.patientEdit => 'You changed this',
        RecoveryEditKind.correction => 'Corrected by ${author ?? 'care team'}',
      };

  Map<String, dynamic> toJson() => {
        'kind': kind.name,
        'phase': phase,
        'text': text,
        if (bulletIndex != null) 'bulletIndex': bulletIndex,
        if (original != null) 'original': original,
        if (author != null) 'author': author,
        'createdAt': (createdAt ?? DateTime.now()).toIso8601String(),
      };

  /// Rebuild from stored JSON, or null when the row is unreadable.
  ///
  /// Returns null rather than throwing: one corrupt entry from an older build
  /// must not take out the whole Recovery tab.
  static RecoveryEdit? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final kindName = '${raw['kind']}';
    RecoveryEditKind? kind;
    for (final k in RecoveryEditKind.values) {
      if (k.name == kindName) kind = k;
    }
    if (kind == null) return null;
    final phase = '${raw['phase'] ?? ''}';
    final text = '${raw['text'] ?? ''}';
    if (phase.isEmpty || text.isEmpty) return null;
    final index = raw['bulletIndex'];
    final edit = RecoveryEdit(
      kind: kind,
      phase: phase,
      text: text,
      bulletIndex: index is int ? index : null,
      original: raw['original'] == null ? null : '${raw['original']}',
      author: raw['author'] == null ? null : '${raw['author']}',
      createdAt: DateTime.tryParse('${raw['createdAt'] ?? ''}'),
    );
    // A stored row that fails validation is a row we cannot attribute, which
    // is exactly what must not be shown as if it were clinical text.
    return edit.isValid ? edit : null;
  }
}

/// Every annotation for one document, indexed for lookup by the UI.
class RecoveryEdits {
  const RecoveryEdits(this.all);

  final List<RecoveryEdit> all;

  static const RecoveryEdits empty = RecoveryEdits([]);

  /// The override in force for one bullet, or null when the document's own
  /// text stands. The most recent wins, so a clinician correcting after a
  /// patient edit replaces it rather than fighting over the same line.
  RecoveryEdit? overrideFor(String phase, int bulletIndex) {
    RecoveryEdit? best;
    for (final e in all) {
      if (e.kind == RecoveryEditKind.note) continue;
      if (e.phase != phase || e.bulletIndex != bulletIndex) continue;
      if (best == null ||
          (e.createdAt ?? DateTime(0)).isAfter(best.createdAt ?? DateTime(0))) {
        best = e;
      }
    }
    return best;
  }

  /// Free-standing notes on a phase, oldest first.
  List<RecoveryEdit> notesFor(String phase) => all
      .where((e) => e.kind == RecoveryEditKind.note && e.phase == phase)
      .toList()
    ..sort((a, b) => (a.createdAt ?? DateTime(0))
        .compareTo(b.createdAt ?? DateTime(0)));
}

/// Device-local persistence, one key per document.
class RecoveryNotesStore {
  static String _key(String docId) => 'recovery_edits_$docId';

  /// Everything stored for [docId]. Unreadable rows are dropped silently.
  static Future<RecoveryEdits> load(String docId) async {
    if (docId.isEmpty) return RecoveryEdits.empty;
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(docId));
      if (raw == null || raw.isEmpty) return RecoveryEdits.empty;
      final decoded = jsonDecode(raw);
      if (decoded is! List) return RecoveryEdits.empty;
      return RecoveryEdits(
        decoded.map(RecoveryEdit.fromJson).whereType<RecoveryEdit>().toList(),
      );
    } on FormatException {
      // Corrupt blob - the patient's own text is not worth crashing over,
      // and a fresh empty list lets them start again.
      return RecoveryEdits.empty;
    }
  }

  /// Append one annotation and return the updated set.
  ///
  /// Invalid entries are rejected outright rather than stored and filtered
  /// later, so unattributable text never reaches the device at all.
  static Future<RecoveryEdits> add(String docId, RecoveryEdit edit) async {
    if (docId.isEmpty || !edit.isValid) return load(docId);
    final current = await load(docId);
    final updated = [...current.all, edit];
    await _write(docId, updated);
    return RecoveryEdits(updated);
  }

  /// Drop one annotation, identified by kind, phase and bullet.
  ///
  /// This is how "undo my edit" restores the hospital's wording: removing the
  /// override makes the original text authoritative again.
  static Future<RecoveryEdits> remove(String docId, RecoveryEdit edit) async {
    final current = await load(docId);
    final updated = current.all
        .where((e) => !(e.kind == edit.kind &&
            e.phase == edit.phase &&
            e.bulletIndex == edit.bulletIndex &&
            e.text == edit.text))
        .toList();
    await _write(docId, updated);
    return RecoveryEdits(updated);
  }

  static Future<void> _write(String docId, List<RecoveryEdit> edits) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        _key(docId), jsonEncode(edits.map((e) => e.toJson()).toList()));
  }
}
