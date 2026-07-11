/// services/calendar_link.dart
///
/// Builds the Google Calendar "add event" template URL for a follow-up
/// appointment (Task 2.2 calendar action). Pure Dart - no Flutter imports -
/// so date parsing and URL shape are unit-testable without a device.
/// Extraction dates are free text (Agent 1 never fabricates or normalizes),
/// so parsing is best-effort: a recognized date becomes an all-day event;
/// anything else ("TBD", null, partial text) still opens the template with
/// title and details prefilled and the patient picks the date themselves.
library;

/// Month-name lookup for "July 20, 2026" style dates. Three-letter prefixes
/// cover the common abbreviations (Jan, Feb, ... Dec).
const Map<String, int> _months = {
  'jan': 1,
  'feb': 2,
  'mar': 3,
  'apr': 4,
  'may': 5,
  'jun': 6,
  'jul': 7,
  'aug': 8,
  'sep': 9,
  'oct': 10,
  'nov': 11,
  'dec': 12,
};

/// Best-effort parse of a free-text appointment date.
///
/// Handles the three shapes seen in discharge documents:
///   - ISO: 2026-07-20 (anything DateTime.tryParse accepts)
///   - US numeric: 7/20/2026 or 07-20-2026
///   - Month name: July 20, 2026 / Jul 20 2026 / 20 July 2026
///
/// Returns null when no full date is recognizable - callers must treat null
/// as "let the patient pick", never guess.
DateTime? parseAppointmentDate(String? text) {
  if (text == null) return null;
  final t = text.trim();
  if (t.isEmpty) return null;

  final iso = DateTime.tryParse(t);
  if (iso != null) return iso;

  // US numeric: M/d/yyyy or M-d-yyyy.
  final num = RegExp(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b').firstMatch(t);
  if (num != null) {
    final m = int.parse(num.group(1)!);
    final d = int.parse(num.group(2)!);
    final y = int.parse(num.group(3)!);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return DateTime(y, m, d);
  }

  // Month-name styles, name-first or day-first.
  final lower = t.toLowerCase();
  final nameFirst =
      RegExp(r'\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b')
          .firstMatch(lower);
  final dayFirst =
      RegExp(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?,?\s+(\d{4})\b')
          .firstMatch(lower);
  final match = nameFirst ?? dayFirst;
  if (match != null) {
    final nameIsFirst = match == nameFirst;
    final name = (nameIsFirst ? match.group(1) : match.group(2))!;
    final d = int.parse((nameIsFirst ? match.group(2) : match.group(1))!);
    final y = int.parse(match.group(3)!);
    final m = _months[name.substring(0, 3)];
    if (m != null && d >= 1 && d <= 31) return DateTime(y, m, d);
  }

  return null;
}

String _yyyymmdd(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}'
    '${d.month.toString().padLeft(2, '0')}'
    '${d.day.toString().padLeft(2, '0')}';

/// Google Calendar event-template link for one extracted appointment.
///
/// All fields are the raw Agent 1 extraction values and may be null. When
/// [dateText] parses, the event is all-day on that date (template format
/// YYYYMMDD/YYYYMMDD+1); otherwise the dates parameter is omitted and
/// Google Calendar defaults to "today" for the patient to change.
///
/// ponytail: universal https link, works wherever a browser exists. Native
/// calendar write (device_calendar + permissions) is the upgrade path if
/// testers ask for it.
Uri buildCalendarLink({
  String? provider,
  String? specialty,
  String? reason,
  String? dateText,
}) {
  final what = specialty ?? provider ?? 'appointment';
  final details = [
    if (provider != null && provider.isNotEmpty) 'Provider: $provider',
    if (reason != null && reason.isNotEmpty) 'Reason: $reason',
    if (dateText != null && dateText.isNotEmpty) 'Date in document: $dateText',
    'Added from your DischargeIQ discharge summary.',
  ].join('\n');

  final date = parseAppointmentDate(dateText);
  return Uri.https('calendar.google.com', '/calendar/render', {
    'action': 'TEMPLATE',
    'text': 'Follow-up: $what',
    'details': details,
    if (date != null)
      'dates':
          '${_yyyymmdd(date)}/${_yyyymmdd(date.add(const Duration(days: 1)))}',
  });
}
