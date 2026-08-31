// End-to-end check of the appointment date rule against REAL extracted data.
//
// The unit tests use invented appointments. This one feeds the actual values
// from the committed demo fixtures through the same functions, because the
// rule only matters if it agrees with what Agent 1 really produces - free-text
// dates, null providers, and all.
import 'package:dischargeiq_mobile/services/appointment_status.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Verbatim from evaluation/corpus_outputs/{heart_failure_01,copd_01}.json.
  final real = [
    {'provider': 'Dr. Anne Fitzgerald', 'specialty': 'Cardiology', 'date': '2026-04-02'},
    {'provider': 'Dr. Laura Chen', 'specialty': 'Primary Care', 'date': '2026-04-05'},
    {'provider': null, 'specialty': 'Cardiac Rehabilitation', 'date': '2026-04-12'},
    {'provider': 'Dr. Anne Fitzgerald', 'specialty': 'Pulmonology', 'date': '2026-03-24'},
    {'provider': 'Dr. James Okafor', 'specialty': 'Primary Care', 'date': '2026-03-26'},
    {'provider': null, 'specialty': 'Pulmonary Rehabilitation', 'date': '2026-04-02'},
  ];

  test('every demo-fixture appointment parses and reads as past', () {
    final now = DateTime(2026, 8, 29);
    for (final a in real) {
      expect(isAppointmentPast(a, now: now), isTrue,
          reason: 'expected ${a['date']} to be past on 2026-08-29');
    }
  });

  test('every demo-fixture appointment is markable', () {
    // An empty key means no tick is offered. A null provider must still be
    // markable via specialty and date, or a third of the demo list would
    // silently have no control.
    for (final a in real) {
      expect(appointmentKey(a), isNotEmpty,
          reason: 'no key for provider=${a['provider']} spec=${a['specialty']}');
    }
  });

  test('the two same-provider appointments get different keys', () {
    // Dr. Anne Fitzgerald appears in both fixtures on different dates.
    expect(appointmentKey(real[0]), isNot(equals(appointmentKey(real[3]))));
  });
}
