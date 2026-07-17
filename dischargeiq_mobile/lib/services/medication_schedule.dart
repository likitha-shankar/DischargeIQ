/// services/medication_schedule.dart
///
/// Medication reminder schedule (competitor-gap feature B1): turns Agent 1's
/// extracted medications into a SUGGESTED daily reminder schedule the
/// patient reviews and confirms. Pure Dart - parsing and serialization are
/// unit-testable without a device.
///
/// Safety rules, in code not prose:
///   - Dose and frequency are shown VERBATIM from the document - never
///     normalized, never recalculated.
///   - Suggested times are a convenience mapping of common frequency
///     wording; the patient confirms or edits every time before anything
///     is scheduled. Unrecognized frequencies get one default slot and a
///     "check your pharmacy label" flag rather than a guess at more.
///   - Discontinued medications are excluded. "As needed" medications are
///     listed but never scheduled.
library;

import 'dart:convert' show jsonDecode, jsonEncode;

import 'package:shared_preferences/shared_preferences.dart';

/// One reminder time (24h clock). Plain ints so this file stays Flutter-free.
class ReminderTime {
  const ReminderTime(this.hour, this.minute);

  final int hour;
  final int minute;

  String get label {
    final h12 = hour % 12 == 0 ? 12 : hour % 12;
    final ampm = hour < 12 ? 'AM' : 'PM';
    return '$h12:${minute.toString().padLeft(2, '0')} $ampm';
  }

  Map<String, int> toJson() => {'h': hour, 'm': minute};
  factory ReminderTime.fromJson(Map<String, dynamic> j) =>
      ReminderTime((j['h'] as num).toInt(), (j['m'] as num).toInt());
}

/// One medication's reminder plan.
class MedReminder {
  MedReminder({
    required this.name,
    required this.doseText,
    required this.frequencyText,
    required this.times,
    this.asNeeded = false,
    this.frequencyRecognized = true,
  });

  final String name;

  /// Verbatim from the document - never altered.
  final String doseText;
  final String frequencyText;

  /// Patient-editable reminder times.
  List<ReminderTime> times;

  /// PRN medication: listed, never scheduled.
  final bool asNeeded;

  /// False when the frequency wording was not recognized - UI shows a
  /// "check your pharmacy label" note next to the single default slot.
  final bool frequencyRecognized;

  Map<String, dynamic> toJson() => {
        'name': name,
        'dose': doseText,
        'freq': frequencyText,
        'times': [for (final t in times) t.toJson()],
        'prn': asNeeded,
        'recognized': frequencyRecognized,
      };

  factory MedReminder.fromJson(Map<String, dynamic> j) => MedReminder(
        name: '${j['name'] ?? ''}',
        doseText: '${j['dose'] ?? ''}',
        frequencyText: '${j['freq'] ?? ''}',
        times: [
          for (final t in (j['times'] as List? ?? []))
            ReminderTime.fromJson((t as Map).cast<String, dynamic>())
        ],
        asNeeded: j['prn'] == true,
        frequencyRecognized: j['recognized'] != false,
      );
}

/// Common frequency wordings → suggested daily slots. Times follow typical
/// pharmacy guidance spacing; the patient confirms every one.
List<ReminderTime>? suggestTimes(String frequency) {
  final f = frequency.toLowerCase();
  if (f.isEmpty) return null;
  if (RegExp(r'as needed|prn|if needed|when needed').hasMatch(f)) {
    return const []; // PRN - never scheduled
  }
  if (RegExp(r'four times|4 times|qid|every 6 hours|q6h').hasMatch(f)) {
    return const [ReminderTime(8, 0), ReminderTime(12, 0), ReminderTime(16, 0), ReminderTime(20, 0)];
  }
  if (RegExp(r'three times|3 times|tid|every 8 hours|q8h').hasMatch(f)) {
    return const [ReminderTime(9, 0), ReminderTime(14, 0), ReminderTime(21, 0)];
  }
  if (RegExp(r'twice|two times|2 times|bid|every 12 hours|q12h').hasMatch(f)) {
    return const [ReminderTime(9, 0), ReminderTime(21, 0)];
  }
  if (RegExp(r'bed|night|evening|pm\b|qhs').hasMatch(f)) {
    return const [ReminderTime(21, 0)];
  }
  if (RegExp(r'morning|am\b|qam|breakfast').hasMatch(f)) {
    return const [ReminderTime(9, 0)];
  }
  if (RegExp(r'once|daily|every day|per day|qd\b').hasMatch(f)) {
    return const [ReminderTime(9, 0)];
  }
  return null; // unrecognized wording - caller flags it
}

/// Build the suggested plan from the extraction map. Discontinued
/// medications are excluded entirely.
List<MedReminder> buildSuggestedSchedule(Map<String, dynamic> extraction) {
  final meds = extraction['medications'];
  if (meds is! List) return [];
  final plan = <MedReminder>[];
  for (final m in meds.whereType<Map>()) {
    final name = '${m['name'] ?? ''}'.trim();
    if (name.isEmpty) continue;
    final status = '${m['status'] ?? ''}'.toLowerCase();
    if (status == 'discontinued') continue;
    final freq = '${m['frequency'] ?? ''}'.trim();
    final suggested = suggestTimes(freq);
    final prn = suggested != null && suggested.isEmpty;
    plan.add(MedReminder(
      name: name,
      doseText: '${m['dose'] ?? ''}'.trim(),
      frequencyText: freq,
      times: prn
          ? []
          : List.of(suggested ?? const [ReminderTime(9, 0)]),
      asNeeded: prn,
      frequencyRecognized: suggested != null,
    ));
  }
  return plan;
}

/// Fingerprint of a plan/extraction: sorted med names. Used to detect that
/// a SAVED plan belongs to a different document than the one on screen.
String planFingerprint(Iterable<String> medNames) =>
    (medNames.map((n) => n.trim().toLowerCase()).toList()..sort()).join('|');

/// Persistence for the active reminder plan (one plan per phone - matches
/// the single-patient beta model, see issue I-11).
class MedScheduleStore {
  static const _kKey = 'med_reminder_plan';

  static Future<void> save(List<MedReminder> plan, {required bool enabled}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kKey, jsonEncode({
        'enabled': enabled,
        'fingerprint': planFingerprint(plan.map((m) => m.name)),
        'meds': [for (final m in plan) m.toJson()],
      }));
    } catch (_) {}
  }

  /// Load the saved plan ONLY when it matches [currentFingerprint] - a plan
  /// saved from a different document must never surface for this one.
  /// Returns (plan, enabled, isStale): isStale means an enabled plan from
  /// another document exists (UI warns that old reminders may still fire).
  static Future<(List<MedReminder>, bool, bool)> load(
      {String? currentFingerprint}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_kKey);
      if (raw == null) return (const <MedReminder>[], false, false);
      final j = jsonDecode(raw) as Map<String, dynamic>;
      final saved = '${j['fingerprint'] ?? ''}';
      final enabled = j['enabled'] == true;
      if (currentFingerprint != null && saved != currentFingerprint) {
        // Different document: hand back nothing, but flag if its reminders
        // are still active so the UI can say so.
        return (const <MedReminder>[], false, enabled);
      }
      return (
        [
          for (final m in (j['meds'] as List? ?? []))
            MedReminder.fromJson((m as Map).cast<String, dynamic>())
        ],
        enabled,
        false,
      );
    } catch (_) {
      return (const <MedReminder>[], false, false);
    }
  }

  static Future<void> clear() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kKey);
    } catch (_) {}
  }
}
