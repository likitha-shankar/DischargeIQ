/// test/calendar_link_test.dart
///
/// Unit checks for the add-to-calendar helper (services/calendar_link.dart):
/// best-effort date parsing across the formats seen in discharge documents,
/// the null-over-guess rule for unparseable dates, and the Google Calendar
/// template URL shape. Pure Dart - no platform channels.
library;

import 'package:dischargeiq_mobile/services/calendar_link.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses ISO, US numeric, and month-name dates', () {
    expect(parseAppointmentDate('2026-07-20'), DateTime(2026, 7, 20));
    expect(parseAppointmentDate('7/20/2026'), DateTime(2026, 7, 20));
    expect(parseAppointmentDate('07-20-2026'), DateTime(2026, 7, 20));
    expect(parseAppointmentDate('July 20, 2026'), DateTime(2026, 7, 20));
    expect(parseAppointmentDate('Jul 20 2026'), DateTime(2026, 7, 20));
    expect(parseAppointmentDate('20 July 2026'), DateTime(2026, 7, 20));
    expect(
      parseAppointmentDate('Follow up on August 3rd, 2026 at 2 PM'),
      DateTime(2026, 8, 3),
    );
  });

  test('returns null instead of guessing on unparseable dates', () {
    expect(parseAppointmentDate(null), isNull);
    expect(parseAppointmentDate(''), isNull);
    expect(parseAppointmentDate('TBD'), isNull);
    expect(parseAppointmentDate('within 2 weeks'), isNull);
    expect(parseAppointmentDate('call to schedule'), isNull);
  });

  test('link carries title, details, and all-day dates when parseable', () {
    final url = buildCalendarLink(
      provider: 'Dr. Chen',
      specialty: 'Cardiology',
      reason: 'Medication review',
      dateText: '2026-07-20',
    );
    expect(url.host, 'calendar.google.com');
    expect(url.path, '/calendar/render');
    expect(url.queryParameters['action'], 'TEMPLATE');
    expect(url.queryParameters['text'], 'Follow-up: Cardiology');
    expect(url.queryParameters['details'], contains('Dr. Chen'));
    expect(url.queryParameters['details'], contains('Medication review'));
    expect(url.queryParameters['dates'], '20260720/20260721');
  });

  test('link omits dates and falls back to provider when data is sparse', () {
    final url = buildCalendarLink(provider: 'Dr. Chen', dateText: 'TBD');
    expect(url.queryParameters['text'], 'Follow-up: Dr. Chen');
    expect(url.queryParameters.containsKey('dates'), isFalse);

    final bare = buildCalendarLink();
    expect(bare.queryParameters['text'], 'Follow-up: appointment');
  });

  test('calendar star is registered in the display list, not the tab list', () {
    expect(kAllStarKeys, contains(kCalendarStarKey));
    expect(kSectionStarKeys, isNot(contains(kCalendarStarKey)));
    expect(kAllStarKeys.length, kSectionStarKeys.length + 1);
    expect(kSectionStarLabels[kCalendarStarKey], isNotEmpty);
  });
}
