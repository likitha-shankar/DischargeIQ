/// services/appointment_edits.dart
///
/// Patient corrections to follow-up appointments.
///
/// Clinics reschedule, and Agent 1 extracts what the document said on the day
/// it was written. A patient whose cardiology visit moved to the 27th has no
/// way to make the app agree with reality, so the appointment they are
/// actually attending is not the one the app reminds them about.
///
/// THE KEYING RULE, which is the whole reason this file is separate from the
/// edit itself: every edit is stored against the key of the ORIGINAL
/// appointment, never the edited one.
///
/// [appointmentKey] is built from provider, specialty and date. Date is the
/// field most likely to be corrected, so keying an edit by its own new values
/// would change the key the moment it was saved - detaching the edit from the
/// appointment it edits, and detaching the done-tick in
/// [AppointmentStatusStore], which is keyed the same way. The tick would
/// silently move to an appointment that no longer exists.
///
/// So: the document's own values are the identity, the edit is an overlay,
/// and [applyAppointmentEdit] merges them for display.
///
/// As with the recovery timeline, the original is kept and the change is
/// labelled. A corrected appointment must never be indistinguishable from
/// what the hospital wrote.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/appointment_status.dart';

/// The fields a patient may correct. Deliberately not "any field": these are
/// the four a patient can know better than the document.
const kEditableAppointmentFields = ['date', 'provider', 'specialty', 'reason'];

/// One patient correction to one appointment.
class AppointmentEdit {
  const AppointmentEdit({
    required this.originalKey,
    required this.changes,
    required this.originals,
    this.createdAt,
  });

  /// [appointmentKey] of the appointment as the DOCUMENT gave it. Never
  /// recomputed from the edited values - see the keying rule above.
  final String originalKey;

  /// Field name to new value, for changed fields only.
  final Map<String, String> changes;

  /// Field name to what the document said, for the same fields. Kept so the
  /// patient can always see the original, and so an edit can be undone.
  final Map<String, String> originals;

  final DateTime? createdAt;

  /// An edit must be anchored to an appointment, change something, and carry
  /// what it replaced. Anything else cannot be attributed or undone.
  bool get isValid {
    if (originalKey.isEmpty || changes.isEmpty) return false;
    // Every changed field must have its original recorded, even if that
    // original was empty - "the document said nothing here" is information.
    for (final field in changes.keys) {
      if (!kEditableAppointmentFields.contains(field)) return false;
      if (!originals.containsKey(field)) return false;
    }
    return true;
  }

  /// Human-readable list of what was changed, for the card's label.
  String get summary {
    final names = changes.keys.map((f) => f == 'date' ? 'date' : f).toList()
      ..sort();
    return 'You changed the ${names.join(' and ')}';
  }

  Map<String, dynamic> toJson() => {
        'originalKey': originalKey,
        'changes': changes,
        'originals': originals,
        'createdAt': (createdAt ?? DateTime.now()).toIso8601String(),
      };

  /// Rebuild from stored JSON, or null when the row is unusable.
  ///
  /// Null rather than throwing: one bad row from an older build must not take
  /// out the Appointments tab.
  static AppointmentEdit? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final key = '${raw['originalKey'] ?? ''}';
    final changes = _stringMap(raw['changes']);
    final originals = _stringMap(raw['originals']);
    if (key.isEmpty || changes.isEmpty) return null;
    final edit = AppointmentEdit(
      originalKey: key,
      changes: changes,
      originals: originals,
      createdAt: DateTime.tryParse('${raw['createdAt'] ?? ''}'),
    );
    return edit.isValid ? edit : null;
  }

  static Map<String, String> _stringMap(dynamic raw) {
    if (raw is! Map) return {};
    return {
      for (final entry in raw.entries)
        if (entry.value != null) '${entry.key}': '${entry.value}',
    };
  }
}

/// The appointment as the patient should see it: the document's values with
/// any correction applied on top.
///
/// Returns the original map untouched when there is no edit, so callers can
/// use this unconditionally.
Map applyAppointmentEdit(Map appointment, AppointmentEdit? edit) {
  if (edit == null || edit.changes.isEmpty) return appointment;
  return {...appointment, ...edit.changes};
}

/// Device-local corrections, one key per document.
class AppointmentEditsStore {
  static String _key(String docId) => 'appointment_edits_$docId';

  /// Every correction for [docId], indexed by the ORIGINAL appointment key.
  static Future<Map<String, AppointmentEdit>> load(String docId) async {
    if (docId.isEmpty) return {};
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(docId));
      if (raw == null || raw.isEmpty) return {};
      final decoded = jsonDecode(raw);
      if (decoded is! List) return {};
      final out = <String, AppointmentEdit>{};
      for (final row in decoded) {
        final edit = AppointmentEdit.fromJson(row);
        // Later rows win, so re-editing a field replaces rather than stacks.
        if (edit != null) out[edit.originalKey] = edit;
      }
      return out;
    } on FormatException {
      // Corrupt blob - the patient's appointments still render from the
      // document, which is the safe state to fall back to.
      return {};
    }
  }

  /// Record a correction against [original], returning the updated set.
  ///
  /// [changes] carries only the fields the patient actually altered; the
  /// originals are read from [original] here rather than trusted from the
  /// caller, so what is stored as "the document said" always did.
  static Future<Map<String, AppointmentEdit>> save({
    required String docId,
    required Map original,
    required Map<String, String> changes,
  }) async {
    final key = appointmentKey(original);
    if (docId.isEmpty || key.isEmpty || changes.isEmpty) return load(docId);

    final originals = <String, String>{
      for (final field in changes.keys) field: '${original[field] ?? ''}',
    };
    final edit = AppointmentEdit(
      originalKey: key,
      changes: changes,
      originals: originals,
      createdAt: DateTime.now(),
    );
    if (!edit.isValid) return load(docId);

    final current = await load(docId);
    final updated = {...current, key: edit};
    await _write(docId, updated);
    return updated;
  }

  /// Drop the correction on one appointment, restoring the document's values.
  static Future<Map<String, AppointmentEdit>> remove(
      String docId, String originalKey) async {
    final current = await load(docId);
    final updated = {...current}..remove(originalKey);
    await _write(docId, updated);
    return updated;
  }

  static Future<void> _write(
      String docId, Map<String, AppointmentEdit> edits) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key(docId),
      jsonEncode(edits.values.map((e) => e.toJson()).toList()),
    );
  }
}
