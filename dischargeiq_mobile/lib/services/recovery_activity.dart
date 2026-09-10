/// services/recovery_activity.dart
///
/// What the patient has actually DONE, resolved onto the recovery timeline's
/// week phases. Pure Dart - no Flutter, no storage - so the week-window maths
/// is unit-testable, and the IO stays in the callers that already own it.
///
/// WHY THIS EXISTS
/// ---------------
/// The recovery rail's fill has only ever meant elapsed time:
/// `currentPhaseIndex` is days-since-discharge divided by seven, and it reads
/// nothing the patient did. Sit untouched for three weeks and the marker
/// still advances to week 3. Beside a weight log, quests and a journey theme,
/// a filled bar reads as "you are doing well", which is a claim the app was
/// never in a position to make.
///
/// WHAT THIS DOES AND DOES NOT CLAIM
/// ---------------------------------
/// It counts patient-CONFIRMED actions: appointments they ticked off, days
/// they logged a weight, notes they wrote on a phase. Every one is something
/// the person did in the app on purpose.
///
/// It is NOT a measure of clinical recovery, and nothing here should ever be
/// labelled as one. A patient can do everything the app asks and still be
/// unwell; a patient can recover perfectly and never open the app. Activity
/// and healing are different quantities, and the UI has to keep saying so.
///
/// An empty phase is therefore rendered as ABSENCE, never as failure. There
/// is no red, no zero, no "incomplete" - a week with nothing logged may be a
/// week that asked nothing. `appointment_status.dart` records the same
/// reasoning about its own list: a checklist a patient cannot satisfy stops
/// being a checklist and becomes a source of guilt.
library;

import 'package:dischargeiq_mobile/services/appointment_status.dart';
import 'package:dischargeiq_mobile/services/calendar_link.dart'
    show parseAppointmentDate;
import 'package:dischargeiq_mobile/services/health_log.dart' show WeightEntry;
import 'package:dischargeiq_mobile/services/recovery_notes.dart';
import 'package:dischargeiq_mobile/services/recovery_timeline.dart';

/// What one phase of the timeline has recorded against it.
class PhaseActivity {
  const PhaseActivity({
    this.appointmentsKept = 0,
    this.daysWeighed = 0,
    this.notesAdded = 0,
  });

  /// Appointments the patient ticked off whose date falls inside this phase.
  final int appointmentsKept;

  /// Distinct days inside this phase with a logged weight.
  final int daysWeighed;

  /// Notes the patient attached to this phase. Undated by nature - a note
  /// belongs to the phase it was written on, not to the day it was written.
  final int notesAdded;

  int get total => appointmentsKept + daysWeighed + notesAdded;

  bool get any => total > 0;

  /// One short line for the phase, or null when there is nothing to say.
  ///
  /// Returns null rather than "nothing yet" deliberately: an empty phase
  /// shows no line at all. See the library note on absence versus failure.
  String? get summary {
    if (!any) return null;
    final parts = <String>[
      if (appointmentsKept > 0)
        '$appointmentsKept appointment${appointmentsKept == 1 ? '' : 's'} kept',
      if (daysWeighed > 0)
        '$daysWeighed day${daysWeighed == 1 ? '' : 's'} weighed',
      if (notesAdded > 0) '$notesAdded note${notesAdded == 1 ? '' : 's'}',
    ];
    return parts.join(' · ');
  }
}

/// The day-offset window a phase covers, counted from the discharge date.
///
/// Deliberately mirrors `currentPhaseIndex`: there, a day offset `d` falls in
/// week `(d ~/ 7) + 1`. So a phase spanning weeks `ws..we` owns the offsets
/// `(ws - 1) * 7` up to but not including `we * 7`. Deriving this a second
/// time by a different route is how the rail's fill and its activity would
/// end up disagreeing about which week a Tuesday belongs to.
///
/// Returns null for a phase whose heading names no week ("When you feel
/// ready"), which cannot own a date window at all.
(int, int)? phaseDayWindow(RecoveryPhase phase) {
  final start = phase.weekStart;
  if (start == null) return null;
  final end = phase.weekEnd ?? start;
  return ((start - 1) * 7, end * 7);
}

/// Whole days from [discharged] to [when], ignoring clock time.
///
/// Both are floored to midnight first. Without that, a weight logged at 9am
/// on the seventh day comes out as day 6 and lands in the previous week -
/// an off-by-one that would be invisible except at phase boundaries, which
/// is exactly where anyone would look to check it.
int _dayOffset(DateTime discharged, DateTime when) {
  final from = DateTime(discharged.year, discharged.month, discharged.day);
  final to = DateTime(when.year, when.month, when.day);
  return to.difference(from).inDays;
}

/// Parse a `HealthLog.dayKey` string ("2026-03-27") back to a date.
///
/// Returns null on anything unparseable rather than throwing: the weight log
/// is patient data that has survived app upgrades, and one malformed row must
/// not take out the whole rail.
DateTime? _parseDayKey(String key) {
  final parts = key.split('-');
  if (parts.length != 3) return null;
  final year = int.tryParse(parts[0]);
  final month = int.tryParse(parts[1]);
  final day = int.tryParse(parts[2]);
  if (year == null || month == null || day == null) return null;
  return DateTime(year, month, day);
}

/// Resolve every recorded action onto its phase.
///
/// Args:
///   phases: The week phases the rail draws, in order.
///   discharged: Resolved discharge date - the patient's correction when they
///     gave one, the document's otherwise. Null when unknown, which is the
///     case for roughly two thirds of real documents.
///   appointments: Raw extracted appointments, as the results screen holds
///     them.
///   doneKeys: `appointmentKey` values the patient has ticked off.
///   weights: Logged weights, newest first.
///   edits: Notes and edits attached to phases by title.
///
/// Returns:
///   One [PhaseActivity] per phase, index-aligned with [phases].
///
/// Note:
///   With a null [discharged], dated evidence cannot be placed on a week at
///   all, so appointments and weights are dropped and only notes survive -
///   those are keyed by phase title and need no date. Placing them anyway,
///   by assuming the upload date, would put a patient who uploaded a
///   fortnight late at week one of their own recovery.
List<PhaseActivity> activityByPhase({
  required List<RecoveryPhase> phases,
  required DateTime? discharged,
  required List<dynamic> appointments,
  required Set<String> doneKeys,
  required List<WeightEntry> weights,
  required RecoveryEdits edits,
}) {
  final keptPerPhase = List<int>.filled(phases.length, 0);
  final weighedPerPhase = List<Set<int>>.generate(phases.length, (_) => <int>{});

  if (discharged != null) {
    for (final raw in appointments) {
      if (raw is! Map) continue;
      // Only appointments the patient actually confirmed. An appointment
      // whose date has passed is not evidence of anything - the whole point
      // of the tick is that attendance is the patient's to assert.
      if (!doneKeys.contains(appointmentKey(raw))) continue;
      final when = parseAppointmentDate(raw['date'] as String?);
      if (when == null) continue;
      final offset = _dayOffset(discharged, when);
      final index = _phaseForOffset(phases, offset);
      if (index != null) keptPerPhase[index]++;
    }

    for (final entry in weights) {
      final when = _parseDayKey(entry.day);
      if (when == null) continue;
      final offset = _dayOffset(discharged, when);
      final index = _phaseForOffset(phases, offset);
      // A Set of offsets, so two weigh-ins on one day count once. The store
      // keys by day already, but the rail must not depend on that staying
      // true to avoid overstating what the patient did.
      if (index != null) weighedPerPhase[index].add(offset);
    }
  }

  return [
    for (var i = 0; i < phases.length; i++)
      PhaseActivity(
        appointmentsKept: keptPerPhase[i],
        daysWeighed: weighedPerPhase[i].length,
        notesAdded: edits.notesFor(phases[i].title).length,
      ),
  ];
}

/// Index of the phase owning [offset] days after discharge, or null.
///
/// Negative offsets - an appointment dated before the discharge, which real
/// documents do carry - belong to no phase and are dropped rather than
/// clamped onto week one.
int? _phaseForOffset(List<RecoveryPhase> phases, int offset) {
  if (offset < 0) return null;
  for (var i = 0; i < phases.length; i++) {
    final window = phaseDayWindow(phases[i]);
    if (window == null) continue;
    if (offset >= window.$1 && offset < window.$2) return i;
  }
  return null;
}
