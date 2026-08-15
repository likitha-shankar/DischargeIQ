import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Local-only health log backing the v2 weight trend and adherence record.
///
/// Nothing here touches the backend. Every entry is written to
/// SharedPreferences on this phone, scoped per document id so switching
/// people in the person switcher does not mix two patients' records.
/// Deleting the app deletes it, same as the rest of the app's data.
///
/// Keys:
///   `weights_<docId>`  JSON list of {d: yyyy-MM-dd, lb: double}
///   `doses_<docId>`    JSON map of "yyyy-MM-dd|slotId" -> true
class HealthLog {
  const HealthLog._();

  static String _wKey(String docId) => 'weights_$docId';
  static String _dKey(String docId) => 'doses_$docId';

  static String dayKey(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';

  // ---------------------------------------------------------------- weights

  /// Most recent first, capped at 60 days so the store cannot grow forever.
  static Future<List<WeightEntry>> weights(String docId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_wKey(docId));
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      final out = list
          .map((m) => WeightEntry(
                day: '${m['d']}',
                pounds: (m['lb'] as num).toDouble(),
              ))
          .toList()
        ..sort((a, b) => b.day.compareTo(a.day));
      return out;
    } catch (_) {
      return const [];
    }
  }

  /// One reading per day - logging twice replaces the day's value rather
  /// than appending, because the number that matters is the morning weight.
  static Future<void> logWeight(String docId, double pounds,
      {DateTime? when}) async {
    final prefs = await SharedPreferences.getInstance();
    final key = dayKey(when ?? DateTime.now());
    final existing = await weights(docId);
    final merged = <String, double>{
      for (final e in existing) e.day: e.pounds,
      key: pounds,
    };
    final entries = merged.entries.toList()
      ..sort((a, b) => b.key.compareTo(a.key));
    final capped = entries.take(60).toList();
    await prefs.setString(
      _wKey(docId),
      jsonEncode([
        for (final e in capped) {'d': e.key, 'lb': e.value}
      ]),
    );
  }

  /// Day-over-day change in pounds, or null when there is nothing to compare.
  /// Positive means gained. This is the number the discharge paperwork cares
  /// about: +3 lb in a day is an ER-today sign.
  static Future<double?> overnightChange(String docId) async {
    final w = await weights(docId);
    if (w.length < 2) return null;
    return w[0].pounds - w[1].pounds;
  }

  // ------------------------------------------------------------------ doses

  static Future<Set<String>> _doseSet(String docId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_dKey(docId));
    if (raw == null || raw.isEmpty) return <String>{};
    try {
      return (jsonDecode(raw) as Map).keys.map((k) => '$k').toSet();
    } catch (_) {
      return <String>{};
    }
  }

  static Future<bool> isDoseTaken(String docId, String slotId,
      {DateTime? when}) async {
    final set = await _doseSet(docId);
    return set.contains('${dayKey(when ?? DateTime.now())}|$slotId');
  }

  /// Returns the new state, so callers can setState on the result.
  static Future<bool> toggleDose(String docId, String slotId,
      {DateTime? when}) async {
    final prefs = await SharedPreferences.getInstance();
    final set = await _doseSet(docId);
    final key = '${dayKey(when ?? DateTime.now())}|$slotId';
    final nowTaken = !set.contains(key);
    if (nowTaken) {
      set.add(key);
    } else {
      set.remove(key);
    }
    await prefs.setString(
      _dKey(docId),
      jsonEncode({for (final k in set) k: true}),
    );
    return nowTaken;
  }

  /// Which of today's slots are ticked.
  static Future<Set<String>> takenToday(String docId, {DateTime? when}) async {
    final prefix = '${dayKey(when ?? DateTime.now())}|';
    final set = await _doseSet(docId);
    return set
        .where((k) => k.startsWith(prefix))
        .map((k) => k.substring(prefix.length))
        .toSet();
  }

  /// Adherence over the last [days] days for a schedule of [slotsPerDay]
  /// slots. Returns one bucket per day, oldest first, each 0.0-1.0.
  /// Days before the first ever entry are reported as null (not missed) so
  /// a patient on day 3 is not shown four weeks of failure.
  static Future<List<double?>> adherence(
    String docId, {
    required int slotsPerDay,
    int days = 28,
  }) async {
    if (slotsPerDay <= 0) return List<double?>.filled(days, null);
    final set = await _doseSet(docId);
    if (set.isEmpty) return List<double?>.filled(days, null);
    final firstDay = set.map((k) => k.split('|').first).reduce(
          (a, b) => a.compareTo(b) < 0 ? a : b,
        );
    final today = DateTime.now();
    final out = <double?>[];
    for (var i = days - 1; i >= 0; i--) {
      final d = dayKey(today.subtract(Duration(days: i)));
      if (d.compareTo(firstDay) < 0) {
        out.add(null);
        continue;
      }
      final hits = set.where((k) => k.startsWith('$d|')).length;
      out.add((hits / slotsPerDay).clamp(0.0, 1.0));
    }
    return out;
  }

  /// Whole-period percentage, ignoring days before the first entry.
  static Future<int?> adherencePercent(
    String docId, {
    required int slotsPerDay,
    int days = 28,
  }) async {
    final buckets = await adherence(docId, slotsPerDay: slotsPerDay, days: days);
    final real = buckets.whereType<double>().toList();
    if (real.isEmpty) return null;
    final avg = real.reduce((a, b) => a + b) / real.length;
    return (avg * 100).round();
  }

  static Future<void> clearFor(String docId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_wKey(docId));
    await prefs.remove(_dKey(docId));
  }
}

class WeightEntry {
  const WeightEntry({required this.day, required this.pounds});

  final String day;
  final double pounds;
}
