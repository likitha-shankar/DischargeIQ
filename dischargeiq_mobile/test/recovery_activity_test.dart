/// Recovery activity: what the patient did, placed on the right week.
///
/// The rail's fill has always meant elapsed time. These tests cover the
/// second channel - confirmed actions - and most of them are about the seam
/// between the two, because that is where this can go quietly wrong:
///
///   - a day landing in the wrong week at a phase boundary
///   - an appointment counted before the patient ticked it
///   - a date placed at all when the discharge date is unknown
///
/// None of those would throw. The rail would simply attribute a patient's
/// week-2 clinic visit to week 1 and look entirely normal doing it.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:dischargeiq_mobile/services/appointment_status.dart'
    show appointmentKey;
import 'package:dischargeiq_mobile/services/health_log.dart'
    show HealthLog, WeightEntry;
import 'package:dischargeiq_mobile/services/recovery_activity.dart';
import 'package:dischargeiq_mobile/services/recovery_notes.dart';
import 'package:dischargeiq_mobile/services/recovery_timeline.dart';

/// Weeks 1, 2-3, 4-6 - the shape Agent 4 actually returns.
const _phases = [
  RecoveryPhase(title: 'Week 1', bullets: [], weekStart: 1, weekEnd: 1),
  RecoveryPhase(title: 'Weeks 2-3', bullets: [], weekStart: 2, weekEnd: 3),
  RecoveryPhase(title: 'Weeks 4-6', bullets: [], weekStart: 4, weekEnd: 6),
];

final _discharge = DateTime(2026, 3, 27);

/// An appointment [days] after discharge, with the key the store would use.
Map<String, dynamic> _appt(int days, {String specialty = 'Cardiology'}) {
  final when = _discharge.add(Duration(days: days));
  return {
    'specialty': specialty,
    'date': '${when.year}-${when.month.toString().padLeft(2, '0')}-'
        '${when.day.toString().padLeft(2, '0')}',
  };
}

WeightEntry _weight(int days) {
  final when = _discharge.add(Duration(days: days));
  return WeightEntry(day: HealthLog.dayKey(when), pounds: 180);
}

/// Distinguishes "the test did not mention a discharge date" from "the test
/// means there is none".
///
/// The helper used `discharged ?? _discharge`, which quietly substituted the
/// real date back in whenever a test passed null - so the whole no-discharge-
/// date group asserted nothing, and passed while doing it. A default that
/// swallows the value under test is worse than no default.
const Object _unset = Object();

List<PhaseActivity> _run({
  List<dynamic> appointments = const [],
  Set<String> done = const {},
  List<WeightEntry> weights = const [],
  RecoveryEdits edits = RecoveryEdits.empty,
  Object? discharged = _unset,
  List<RecoveryPhase> phases = _phases,
}) =>
    activityByPhase(
      phases: phases,
      discharged:
          identical(discharged, _unset) ? _discharge : discharged as DateTime?,
      appointments: appointments,
      doneKeys: done,
      weights: weights,
      edits: edits,
    );

void main() {
  group('week windows line up with the rail', () {
    test('a phase owns exactly its weeks in day offsets', () {
      expect(phaseDayWindow(_phases[0]), (0, 7));
      expect(phaseDayWindow(_phases[1]), (7, 21));
      expect(phaseDayWindow(_phases[2]), (21, 42));
    });

    test('a heading with no week owns no window', () {
      expect(
        phaseDayWindow(const RecoveryPhase(title: 'When ready', bullets: [])),
        isNull,
      );
    });

    test('day 7 is week 2, not week 1', () {
      // The classic off-by-one. currentPhaseIndex puts day 7 in week 2
      // ((7 ~/ 7) + 1), so activity must agree or the fill and the ticks
      // disagree about the same Tuesday.
      final result = _run(weights: [_weight(6), _weight(7)]);
      expect(result[0].daysWeighed, 1, reason: 'day 6 is still week 1');
      expect(result[1].daysWeighed, 1, reason: 'day 7 has crossed into week 2');
    });
  });

  group('appointments count only once the patient says so', () {
    test('an unticked appointment contributes nothing', () {
      final appointments = [_appt(9)];
      expect(_run(appointments: appointments)[1].appointmentsKept, 0);
    });

    test('a ticked appointment lands on its own week', () {
      final appointment = _appt(9);
      final result = _run(
        appointments: [appointment],
        done: {appointmentKey(appointment)},
      );
      expect(result[1].appointmentsKept, 1);
      expect(result[0].appointmentsKept, 0);
      expect(result[2].appointmentsKept, 0);
    });

    test('an appointment dated before discharge is dropped, not clamped', () {
      // Real documents carry these - the clinic booked before the patient
      // went home. Clamping it onto week 1 would credit the patient for
      // something that happened before their recovery started.
      final appointment = _appt(-3);
      final result = _run(
        appointments: [appointment],
        done: {appointmentKey(appointment)},
      );
      expect(result.every((phase) => phase.appointmentsKept == 0), isTrue);
    });

    test('an appointment past the last phase is dropped', () {
      final appointment = _appt(60); // week 9, beyond weeks 4-6
      final result = _run(
        appointments: [appointment],
        done: {appointmentKey(appointment)},
      );
      expect(result.every((phase) => phase.appointmentsKept == 0), isTrue);
    });
  });

  group('weights', () {
    test('two weigh-ins on one day count once', () {
      final result = _run(weights: [_weight(3), _weight(3)]);
      expect(result[0].daysWeighed, 1);
    });

    test('a malformed day key is skipped, not thrown on', () {
      final result = _run(weights: [
        const WeightEntry(day: 'not-a-date', pounds: 180),
        _weight(2),
      ]);
      expect(result[0].daysWeighed, 1);
    });
  });

  group('no discharge date', () {
    test('dated evidence is dropped rather than guessed onto week 1', () {
      // Two thirds of real documents have no usable discharge date. Assuming
      // the upload date would restart a late-uploaded recovery at week one.
      final appointment = _appt(9);
      final result = _run(
        discharged: null,
        appointments: [appointment],
        done: {appointmentKey(appointment)},
        weights: [_weight(2)],
      );
      expect(result.every((phase) => phase.total == 0), isTrue);
    });

    test('notes still count, because they need no date', () {
      final edits = RecoveryEdits([
        RecoveryEdit(
            kind: RecoveryEditKind.note, phase: 'Weeks 2-3', text: 'Felt dizzy'),
      ]);
      final result = _run(discharged: null, edits: edits);
      expect(result[1].notesAdded, 1);
    });
  });

  group('an empty phase reads as absence, never as failure', () {
    test('a phase with nothing recorded offers no summary line', () {
      expect(const PhaseActivity().summary, isNull);
      expect(const PhaseActivity().any, isFalse);
    });

    test('the summary names only what happened', () {
      const activity = PhaseActivity(appointmentsKept: 1, daysWeighed: 3);
      expect(activity.summary, '1 appointment kept · 3 days weighed');
      expect(activity.summary, isNot(contains('0')));
    });

    test('singulars and plurals both read correctly', () {
      expect(const PhaseActivity(daysWeighed: 1).summary, '1 day weighed');
      expect(const PhaseActivity(notesAdded: 2).summary, '2 notes');
    });
  });

  test('activity is index-aligned with the phases it was given', () {
    expect(_run().length, _phases.length);
    expect(_run(phases: const []).length, 0);
  });
}
