/// services/share_summary.dart
///
/// Caregiver share (P-1) + understanding cards (gamification wave 3): pure
/// text builders that turn the analysis the patient already holds into a
/// clean, shareable plain-language summary. Sharing is ALWAYS
/// patient-initiated through the native share sheet - the app never sends
/// anything by itself, and no server is involved (the text is composed
/// on-device from on-device data).
library;

import 'package:dischargeiq_mobile/models/quiz.dart' show kDomainLabels;

const _kShareHeader = 'Shared from DischargeIQ · Patient education only - '
    'not medical advice. Always follow the care team\'s instructions.';

/// Full caregiver summary: diagnosis, medications, appointments, and the
/// warning signs - the four things a family member most needs to know.
String buildCaregiverSummary(Map<String, dynamic> result) {
  final ex = result['extraction'];
  final e = ex is Map ? ex : const {};
  final b = StringBuffer();

  b.writeln('MY DISCHARGE SUMMARY, IN PLAIN LANGUAGE');
  b.writeln(_kShareHeader);
  b.writeln();

  final dx = '${e['primary_diagnosis'] ?? ''}';
  if (dx.isNotEmpty && dx != 'Extraction failed') {
    b.writeln('WHAT HAPPENED');
    b.writeln('Main condition: $dx');
    final expl = '${result['diagnosis_explanation'] ?? ''}'.trim();
    if (expl.isNotEmpty) b.writeln(_plain(expl));
    b.writeln();
  }

  final meds = e['medications'];
  if (meds is List && meds.isNotEmpty) {
    b.writeln('MEDICATIONS');
    for (final m in meds.whereType<Map>()) {
      final parts = [
        '${m['name'] ?? ''}',
        '${m['dose'] ?? ''}',
        '${m['frequency'] ?? ''}',
      ].where((p) => p.isNotEmpty).join(' · ');
      final status = '${m['status'] ?? ''}';
      b.writeln('- $parts${status.isNotEmpty ? ' ($status)' : ''}');
    }
    b.writeln();
  }

  final appts = e['follow_up_appointments'];
  if (appts is List && appts.isNotEmpty) {
    b.writeln('APPOINTMENTS');
    for (final a in appts.whereType<Map>()) {
      b.writeln('- ${a['specialty'] ?? a['provider'] ?? 'Appointment'}: '
          '${a['date'] ?? 'date to be confirmed'}'
          '${a['reason'] != null ? ' - ${a['reason']}' : ''}');
    }
    b.writeln();
  }

  final flags = e['red_flag_symptoms'];
  if (flags is List && flags.isNotEmpty) {
    b.writeln('WARNING SIGNS TO WATCH FOR');
    for (final f in flags) {
      b.writeln('- $f');
    }
    b.writeln();
  }

  b.writeln('(Made with DischargeIQ from my hospital discharge papers.)');
  return b.toString().trim();
}

/// Understanding card for ONE mastered comprehension domain - the shareable
/// "I understand my medications" moment after a perfect domain score.
String buildUnderstandingCard(
    Map<String, dynamic> result, String domain) {
  final label = kDomainLabels[domain] ?? domain;
  final b = StringBuffer();
  b.writeln('I MASTERED: ${label.toUpperCase()} ✅');
  b.writeln('I answered every "$label" question about my own discharge '
      'plan correctly on my teach-back quiz.');
  b.writeln();

  final e = result['extraction'] is Map ? result['extraction'] as Map : const {};
  switch (domain) {
    case 'diagnosis':
      final dx = '${e['primary_diagnosis'] ?? ''}';
      if (dx.isNotEmpty) b.writeln('My condition: $dx');
    case 'medications':
      final meds = e['medications'];
      if (meds is List) {
        for (final m in meds.whereType<Map>()) {
          b.writeln('- ${m['name'] ?? ''} ${m['dose'] ?? ''}'.trim());
        }
      }
    case 'follow_up':
      final appts = e['follow_up_appointments'];
      if (appts is List) {
        for (final a in appts.whereType<Map>()) {
          b.writeln('- ${a['specialty'] ?? a['provider'] ?? 'Visit'}: ${a['date'] ?? 'TBD'}');
        }
      }
    case 'red_flags':
      final flags = e['red_flag_symptoms'];
      if (flags is List) {
        for (final f in flags) {
          b.writeln('- $f');
        }
      }
    default:
      break;
  }
  b.writeln();
  b.writeln(_kShareHeader);
  return b.toString().trim();
}

/// Strip markdown noise for share-sheet text.
String _plain(String text) => text
    .replaceAll(RegExp(r'[*#_`]'), '')
    .replaceAll(RegExp(r'\n{3,}'), '\n\n')
    .trim();
