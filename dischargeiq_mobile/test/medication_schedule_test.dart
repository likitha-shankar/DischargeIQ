/// test/medication_schedule_test.dart
///
/// Unit checks for the medication reminder schedule builder
/// (services/medication_schedule.dart): frequency wording → suggested slots,
/// the PRN never-schedule rule, the discontinued-med exclusion, the
/// unrecognized-frequency flag, and JSON round-tripping. Pure Dart.
library;

import 'package:dischargeiq_mobile/services/medication_schedule.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('frequency wording maps to expected slot counts', () {
    expect(suggestTimes('once daily')!.length, 1);
    expect(suggestTimes('every morning')!.single.hour, 9);
    expect(suggestTimes('at bedtime')!.single.hour, 21);
    expect(suggestTimes('twice daily')!.length, 2);
    expect(suggestTimes('three times a day')!.length, 3);
    expect(suggestTimes('every 6 hours')!.length, 4);
    expect(suggestTimes('as needed for pain'), isEmpty);
    expect(suggestTimes('with a full glass of water'), isNull);
  });

  test('schedule builder: skips discontinued, flags PRN and unknown', () {
    final plan = buildSuggestedSchedule({
      'medications': [
        {'name': 'Furosemide', 'dose': '40 mg', 'frequency': 'every morning', 'status': 'new'},
        {'name': 'Warfarin', 'dose': '5 mg', 'frequency': 'as needed', 'status': 'continued'},
        {'name': 'OldDrug', 'dose': '10 mg', 'frequency': 'daily', 'status': 'discontinued'},
        {'name': 'Mystery', 'dose': '1 tab', 'frequency': 'per the chart', 'status': 'new'},
      ],
    });
    expect(plan.length, 3); // discontinued excluded
    expect(plan[0].times.single.hour, 9);
    expect(plan[1].asNeeded, isTrue);
    expect(plan[1].times, isEmpty);
    expect(plan[2].frequencyRecognized, isFalse);
    expect(plan[2].times.length, 1); // one default slot, never more
    // Verbatim rule: dose and frequency text unchanged.
    expect(plan[0].doseText, '40 mg');
    expect(plan[2].frequencyText, 'per the chart');
  });

  test('plan JSON round-trips', () {
    final plan = buildSuggestedSchedule({
      'medications': [
        {'name': 'Lisinopril', 'dose': '10 mg', 'frequency': 'twice daily', 'status': 'new'},
      ],
    });
    final back = MedReminder.fromJson(plan.single.toJson());
    expect(back.name, 'Lisinopril');
    expect(back.times.length, 2);
    expect(back.times[1].hour, 21);
    expect(back.asNeeded, isFalse);
  });
}
