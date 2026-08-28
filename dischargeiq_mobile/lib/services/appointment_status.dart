/// services/appointment_status.dart
///
/// Tracks which follow-up appointments the patient has marked as done, per
/// document. Pure Dart apart from SharedPreferences, so the key derivation is
/// unit-testable without a device.
///
/// Why this exists: an appointment whose date has passed still shows on the
/// results screen with an "Add to calendar" button, which is the only action
/// offered and the one action that no longer makes sense. LOF review, 26 Aug
/// 2026 (18:05): let users mark past appointments as completed or take
/// appropriate action. A list a patient cannot act on stops being a checklist
/// and becomes a source of guilt.
///
/// Deliberately local-only. Whether someone attended an appointment is not a
/// clinical record, it is the patient's own note to themselves, and the repo
/// rule keeps free text and personal state off the server.
library;

import 'package:shared_preferences/shared_preferences.dart';

import 'calendar_link.dart';

/// A stable identifier for one appointment within one document.
///
/// Extracted appointments have no id, and the list can be regenerated, so the
/// key is derived from the fields a patient would use to recognise it. Date is
/// included because the same provider can legitimately appear twice; reason is
/// not, because it is the field most likely to be reworded between runs.
///
/// Returns an empty string when there is nothing identifying at all, and
/// callers treat that as unmarkable rather than lumping every blank
/// appointment under one shared key.
String appointmentKey(Map appointment) {
  final parts = [
    '${appointment['provider'] ?? ''}'.trim().toLowerCase(),
    '${appointment['specialty'] ?? ''}'.trim().toLowerCase(),
    '${appointment['date'] ?? ''}'.trim().toLowerCase(),
  ].where((p) => p.isNotEmpty).toList();
  return parts.join('|');
}

/// Whether this appointment's date is in the past.
///
/// An unparseable or missing date is NOT past. Agent 1 never normalises dates,
/// so plenty arrive as "in 2 weeks" or "TBD", and guessing that those have
/// elapsed would mark live appointments as history.
///
/// Compares whole days, so an appointment earlier today still counts as
/// upcoming until tomorrow - a patient with a 4pm clinic should not see it
/// greyed out over breakfast.
bool isAppointmentPast(Map appointment, {DateTime? now}) {
  final parsed = parseAppointmentDate(appointment['date'] as String?);
  if (parsed == null) return false;
  final today = now ?? DateTime.now();
  final startOfToday = DateTime(today.year, today.month, today.day);
  return parsed.isBefore(startOfToday);
}

/// Per-document store of appointments the patient marked done.
class AppointmentStatusStore {
  static String _key(String docId) => 'appointments_done.$docId';

  /// Keys marked done for one document.
  ///
  /// Corrupt or missing data yields an empty set. Losing these marks is a
  /// cosmetic loss; throwing here would break the appointments tab.
  static Future<Set<String>> load(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return (prefs.getStringList(_key(docId)) ?? const []).toSet();
    } catch (_) {
      return <String>{};
    }
  }

  /// Mark one appointment done. No-op for an unidentifiable appointment.
  static Future<void> markDone(String docId, Map appointment) async {
    final key = appointmentKey(appointment);
    if (key.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final current = (prefs.getStringList(_key(docId)) ?? const []).toSet()
        ..add(key);
      await prefs.setStringList(_key(docId), current.toList());
    } catch (_) {
      // Best-effort: a failed write must not block the tap.
    }
  }

  /// Undo. Marking done is reversible on purpose - a patient who taps the
  /// wrong row must be able to put it back, and an irreversible tick would
  /// make people avoid the feature.
  static Future<void> markNotDone(String docId, Map appointment) async {
    final key = appointmentKey(appointment);
    if (key.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final current = (prefs.getStringList(_key(docId)) ?? const []).toSet()
        ..remove(key);
      await prefs.setStringList(_key(docId), current.toList());
    } catch (_) {
      // Best-effort, as above.
    }
  }

  /// Forget every mark for one document, for use when it is deleted.
  static Future<void> clear(String docId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_key(docId));
    } catch (_) {
      // Best-effort, as above.
    }
  }
}
