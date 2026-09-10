/// services/added_appointments.dart
///
/// Follow-up appointments the PATIENT added, which their document never named.
///
/// WHY
/// ---
/// Feedback, 10 Sep 2026 (09:15): let people add follow-up appointments beyond
/// those listed in the PDF. The gap is real and common - only 90% of corpus
/// documents name any follow-up at all, and a discharge summary is written
/// before the clinic rings back with a date. Until now the app could correct
/// an appointment ([AppointmentEditsStore]) and tick one off
/// ([AppointmentStatusStore]) but could not know about one the paperwork
/// missed, so the appointment a patient is actually attending was invisible
/// to their reminders.
///
/// PROVENANCE IS THE POINT
/// -----------------------
/// An added appointment is stored SEPARATELY from the extraction and carries
/// `_added_by_patient`, so it can never be mistaken for something the hospital
/// wrote. Merging it into `extraction.follow_up_appointments` would have been
/// less code and would have destroyed the distinction the whole app rests on:
/// every fact a patient sees is either traceable to their document or visibly
/// marked as not. The same rule already governs recovery notes and
/// appointment corrections.
///
/// It also means nothing here can corrupt the extraction record that the
/// accuracy measurements score against.
///
/// KEYING
/// ------
/// Extracted appointments are identified by provider, specialty and date -
/// content-derived, because they have no id. That cannot work for an added
/// one: the patient will edit the date, the key would move, and the done-tick
/// would detach from it. So an added appointment gets a stable id at creation
/// and [appointmentKey] returns `added:<id>` for it, which keeps ticks and
/// corrections attached through any later edit.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Marker key placed on every patient-added appointment map.
const String kAddedByPatient = '_added_by_patient';

/// Stable id key, so the appointment survives its own edits.
const String kAddedId = '_added_id';

/// True when this appointment came from the patient rather than the document.
bool isPatientAdded(Map appointment) =>
    appointment[kAddedByPatient] == true ||
    '${appointment[kAddedId] ?? ''}'.isNotEmpty;

/// Per-document store of appointments the patient added themselves.
class AddedAppointmentsStore {
  static String _key(String docId) => 'added_appointments_$docId';

  /// Every appointment this patient added, oldest first.
  ///
  /// Returns an empty list on a corrupt or absent store rather than throwing:
  /// a bad entry must not take out the appointments tab.
  static Future<List<Map<String, dynamic>>> load(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(docId));
      if (raw == null || raw.isEmpty) return [];
      final decoded = jsonDecode(raw);
      if (decoded is! List) return [];
      return [
        for (final entry in decoded)
          if (entry is Map)
            {
              ...Map<String, dynamic>.from(entry),
              // Re-asserted on read. An entry that lost its marker in storage
              // would otherwise render as though the hospital wrote it, which
              // is the one outcome this file exists to prevent.
              kAddedByPatient: true,
            },
      ];
    } catch (_) {
      return [];
    }
  }

  /// Add one appointment. Returns the updated list.
  ///
  /// Args:
  ///   docId: Document this belongs to.
  ///   provider: Who the visit is with. May be empty if specialty is given.
  ///   specialty: Department or kind of visit.
  ///   date: As the patient wrote it. NOT normalised - "in 2 weeks" is a
  ///     real answer, and the rest of the app already handles unparseable
  ///     dates rather than guessing at them.
  ///   reason: Optional free text.
  ///   now: Injectable clock, for tests.
  static Future<List<Map<String, dynamic>>> add({
    required String docId,
    String provider = '',
    String specialty = '',
    String date = '',
    String reason = '',
    DateTime? now,
  }) async {
    final current = await load(docId);
    // Something identifying is required, or the entry cannot be told apart
    // from any other on the card and cannot be meaningfully edited later.
    if (provider.trim().isEmpty && specialty.trim().isEmpty) return current;
    final stamp = (now ?? DateTime.now()).microsecondsSinceEpoch.toString();
    current.add({
      'provider': provider.trim(),
      'specialty': specialty.trim(),
      'date': date.trim(),
      'reason': reason.trim(),
      kAddedByPatient: true,
      kAddedId: stamp,
    });
    await _write(docId, current);
    return current;
  }

  /// Remove one added appointment by its id. Returns the updated list.
  static Future<List<Map<String, dynamic>>> remove(
      String docId, String addedId) async {
    final current = await load(docId);
    current.removeWhere((a) => '${a[kAddedId] ?? ''}' == addedId);
    await _write(docId, current);
    return current;
  }

  /// Replace the fields of one added appointment, keeping its id.
  ///
  /// Editing in place rather than remove-and-re-add, so the done-tick and any
  /// correction keyed to it survive the change.
  static Future<List<Map<String, dynamic>>> update({
    required String docId,
    required String addedId,
    String? provider,
    String? specialty,
    String? date,
    String? reason,
  }) async {
    final current = await load(docId);
    for (final entry in current) {
      if ('${entry[kAddedId] ?? ''}' != addedId) continue;
      if (provider != null) entry['provider'] = provider.trim();
      if (specialty != null) entry['specialty'] = specialty.trim();
      if (date != null) entry['date'] = date.trim();
      if (reason != null) entry['reason'] = reason.trim();
    }
    await _write(docId, current);
    return current;
  }

  static Future<void> _write(
      String docId, List<Map<String, dynamic>> entries) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key(docId), jsonEncode(entries));
    } catch (_) {
      // Best-effort, like every other local store here: a storage failure
      // must not break the appointments tab.
    }
  }

  static Future<void> clear(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_key(docId));
    } catch (_) {}
  }
}
