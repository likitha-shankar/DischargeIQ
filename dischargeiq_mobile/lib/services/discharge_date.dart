/// services/discharge_date.dart
///
/// The date the patient actually left hospital, which the whole recovery
/// timeline is measured from.
///
/// WHY THIS EXISTS. `currentPhaseIndex` anchors on `extraction.discharge_date`
/// and returns null without it - no "you are here" marker, no week position,
/// just the shape of a timeline with the patient nowhere in it. Measured on
/// the 106-document corpus, **only 35 documents (33%) carry a discharge
/// date**. So the feature worked for a third of real paperwork and silently
/// did nothing for the rest.
///
/// It also could not be corrected. If Agent 1 read the wrong date, or read an
/// admission date as a discharge date, the patient was shown the wrong week
/// with no way to fix it.
///
/// The timeline anchors on the DOCUMENT's date, never the upload date, and
/// that is deliberate: a summary uploaded two weeks after discharge should
/// place the patient in week three, not restart their recovery. This store
/// keeps that property - it supplies a date when the document has none, or
/// corrects one the document got wrong. It never substitutes "today".
///
/// Same provenance rule as the appointment and recovery edits: the document's
/// own value is preserved, the override is labelled, and it can be undone.
library;

import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/calendar_link.dart'
    show parseAppointmentDate;

/// Where the date driving the timeline came from.
enum DischargeDateSource {
  /// Agent 1 read it out of the discharge document.
  document,

  /// The patient supplied or corrected it.
  patient,

  /// Neither - the timeline cannot be positioned.
  unknown,
}

/// The date in force for one document, and where it came from.
class EffectiveDischargeDate {
  const EffectiveDischargeDate({
    required this.source,
    this.date,
    this.documentValue,
  });

  final DischargeDateSource source;

  /// Parsed date, or null when [source] is unknown.
  final DateTime? date;

  /// What the document said, kept even when the patient has overridden it so
  /// the original is always recoverable.
  final String? documentValue;

  /// ISO date string for the parsers downstream, or '' when unknown.
  String get isoText => date == null
      ? ''
      : '${date!.year.toString().padLeft(4, '0')}-'
          '${date!.month.toString().padLeft(2, '0')}-'
          '${date!.day.toString().padLeft(2, '0')}';

  bool get isKnown => date != null;

  /// True when the patient's value differs from what the document said - the
  /// case the UI must label, as opposed to merely filling in a blank.
  bool get correctsTheDocument {
    if (source != DischargeDateSource.patient) return false;
    final fromDoc = parseAppointmentDate(documentValue);
    if (fromDoc == null) return false;
    return !_sameDay(fromDoc, date!);
  }

  static bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;
}

/// Device-local discharge-date overrides, one per document.
class DischargeDateStore {
  static String _key(String docId) => 'discharge_date_$docId';

  /// The patient's override for [docId], or null when they have not set one.
  static Future<DateTime?> loadOverride(String docId) async {
    if (docId.isEmpty) return null;
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(docId));
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw);
  }

  /// Record the date the patient says they left hospital.
  ///
  /// A future date is refused. Recovery is measured forward from discharge,
  /// so a date that has not happened yet produces a negative elapsed time,
  /// which `currentPhaseIndex` already discards - storing it would leave the
  /// patient with an override that silently does nothing.
  static Future<bool> save(String docId, DateTime date, {DateTime? now}) async {
    if (docId.isEmpty) return false;
    final today = now ?? DateTime.now();
    final endOfToday = DateTime(today.year, today.month, today.day, 23, 59);
    if (date.isAfter(endOfToday)) return false;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key(docId),
      DateTime(date.year, date.month, date.day).toIso8601String(),
    );
    return true;
  }

  /// Drop the override, restoring whatever the document said.
  static Future<void> clear(String docId) async {
    if (docId.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key(docId));
  }

  /// Resolve which date the timeline should use.
  ///
  /// The patient's value wins when present. Otherwise the document's is
  /// parsed; an unparseable one ("in 2 weeks", "TBD") counts as unknown
  /// rather than being guessed at, which is the same rule
  /// `isAppointmentPast` follows.
  static Future<EffectiveDischargeDate> resolve({
    required String docId,
    required String? documentValue,
  }) async {
    final override = await loadOverride(docId);
    if (override != null) {
      return EffectiveDischargeDate(
        source: DischargeDateSource.patient,
        date: override,
        documentValue: documentValue,
      );
    }
    final fromDocument = parseAppointmentDate(documentValue);
    if (fromDocument != null) {
      return EffectiveDischargeDate(
        source: DischargeDateSource.document,
        date: fromDocument,
        documentValue: documentValue,
      );
    }
    return EffectiveDischargeDate(
      source: DischargeDateSource.unknown,
      documentValue: documentValue,
    );
  }
}
