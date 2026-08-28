// Tests for marking follow-up appointments done (LOF review 26 Aug 2026).
//
// The two things worth getting right are the date rule and the key.
//
// The date rule decides whether a patient is offered "mark as done" at all.
// Calling a live appointment past would grey out something they still need to
// attend, which is worse than the problem being fixed.
//
// The key decides whether a mark survives. Appointments have no id and the
// list can be regenerated from the same document, so a key that shifts between
// runs loses the patient's marks silently.

import 'package:dischargeiq_mobile/services/appointment_status.dart';
import 'package:flutter_test/flutter_test.dart';

Map _appt({String? provider, String? specialty, String? date, String? reason}) => {
      'provider': provider,
      'specialty': specialty,
      'date': date,
      'reason': reason,
    };

void main() {
  group('isAppointmentPast', () {
    final now = DateTime(2026, 8, 26);

    test('a date before today is past', () {
      expect(isAppointmentPast(_appt(date: '2026-08-01'), now: now), isTrue);
    });

    test('a date after today is not past', () {
      expect(isAppointmentPast(_appt(date: '2026-09-15'), now: now), isFalse);
    });

    test('today is NOT past', () {
      // A patient with a 4pm clinic should not see it greyed out at breakfast.
      expect(isAppointmentPast(_appt(date: '2026-08-26'), now: now), isFalse);
    });

    test('an unparseable date is never past', () {
      // Agent 1 never normalises dates, so "in 2 weeks" and "TBD" are common.
      // Guessing those have elapsed would retire live appointments.
      for (final text in ['in 2 weeks', 'TBD', 'as needed', 'call to schedule']) {
        expect(isAppointmentPast(_appt(date: text), now: now), isFalse,
            reason: 'must not treat "$text" as past');
      }
    });

    test('a missing date is never past', () {
      expect(isAppointmentPast(_appt(date: null), now: now), isFalse);
      expect(isAppointmentPast(_appt(date: ''), now: now), isFalse);
    });

    test('handles the US and month-name formats the parser accepts', () {
      expect(isAppointmentPast(_appt(date: '8/01/2026'), now: now), isTrue);
      expect(isAppointmentPast(_appt(date: 'July 20, 2026'), now: now), isTrue);
      expect(isAppointmentPast(_appt(date: 'Dec 1, 2026'), now: now), isFalse);
    });
  });

  group('appointmentKey', () {
    test('is stable across identical appointments', () {
      final a = _appt(provider: 'Dr. Chen', specialty: 'Cardiology', date: '2026-09-01');
      final b = _appt(provider: 'Dr. Chen', specialty: 'Cardiology', date: '2026-09-01');
      expect(appointmentKey(a), equals(appointmentKey(b)));
    });

    test('ignores case and surrounding whitespace', () {
      final a = _appt(provider: 'Dr. Chen', specialty: 'Cardiology');
      final b = _appt(provider: '  DR. CHEN ', specialty: 'cardiology');
      expect(appointmentKey(a), equals(appointmentKey(b)));
    });

    test('ignores reason, which is the field most likely to be reworded', () {
      final a = _appt(provider: 'Dr. Chen', date: '2026-09-01', reason: 'follow-up');
      final b = _appt(provider: 'Dr. Chen', date: '2026-09-01', reason: 'post-discharge review');
      expect(appointmentKey(a), equals(appointmentKey(b)));
    });

    test('same provider on different dates are different appointments', () {
      final a = _appt(provider: 'Dr. Chen', date: '2026-09-01');
      final b = _appt(provider: 'Dr. Chen', date: '2026-10-01');
      expect(appointmentKey(a), isNot(equals(appointmentKey(b))));
    });

    test('different providers are different appointments', () {
      expect(appointmentKey(_appt(provider: 'Dr. Chen')),
          isNot(equals(appointmentKey(_appt(provider: 'Dr. Patel')))));
    });

    test('an appointment with nothing identifying yields an empty key', () {
      // Callers treat this as unmarkable rather than filing every blank
      // appointment under one shared key, which would mark them all at once.
      expect(appointmentKey(_appt()), isEmpty);
      expect(appointmentKey(_appt(reason: 'general review')), isEmpty);
    });
  });
}
