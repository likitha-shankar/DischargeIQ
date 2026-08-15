/// services/recovery_timeline.dart
///
/// Recovery journey map (gamification wave 3): parses Agent 4's week-by-week
/// recovery text into phases so the Recovery tab can draw a visual path with
/// a "you are here" marker. Pure Dart - no Flutter - so the parsing and the
/// which-week-am-I-in math are unit-testable.
///
/// Parsing is deliberately conservative: if the text does not contain at
/// least two recognizable phase headings ("Week 1:", "**Weeks 2-4**", ...),
/// callers fall back to plain text. A wrong map is worse than no map.
library;

import 'package:dischargeiq_mobile/services/calendar_link.dart' show parseAppointmentDate;

/// One phase of the recovery timeline.
class RecoveryPhase {
  const RecoveryPhase({
    required this.title,
    required this.bullets,
    this.weekStart,
    this.weekEnd,
  });

  final String title;
  final List<String> bullets;

  /// Week range covered, when the heading names one ("Weeks 2-4" → 2..4).
  /// Null when the heading is not week-shaped ("When you feel ready").
  final int? weekStart;
  final int? weekEnd;
}

final _headingRe = RegExp(
  r'^\s*\**\s*(weeks?\s+(\d+)(?:\s*[-–]\s*(\d+))?[^:*]*)[:*]*\s*$',
  caseSensitive: false,
);

/// A heading that is NOT week-shaped, in Agent 4's two styles: a whole line
/// in bold ("**When to expect improvement:**") or a markdown hash heading.
///
/// These used to fall through to the bullet branch, so a section title landed
/// inside the previous week's bullet list with a dot beside it - which is
/// what made the Recovery tab read as if the last week owned advice that
/// belongs to the whole recovery.
final _otherHeadingRe = RegExp(
  r'^\s*(?:#{1,6}\s*)?\*\*(.+?)\*\*\s*:?\s*$|^\s*#{1,6}\s+(.+?)\s*$',
);

/// Every heading-led block in the text, week-shaped or not, in document
/// order. Blocks with a null [RecoveryPhase.weekStart] are sections that
/// belong to the recovery as a whole rather than to one week.
List<RecoveryPhase> parseRecoverySections(String text) {
  final sections = <RecoveryPhase>[];
  String? title;
  int? ws, we;
  var bullets = <String>[];

  void flush() {
    final t = title;
    if (t != null) {
      sections.add(RecoveryPhase(
          title: t, bullets: bullets, weekStart: ws, weekEnd: we));
    }
    bullets = <String>[];
  }

  for (final raw in text.split('\n')) {
    final line = raw.trim();
    if (line.isEmpty) continue;

    final week = _headingRe.firstMatch(line);
    if (week != null) {
      flush();
      title = week.group(1)!.replaceAll(RegExp(r'\*+'), '').trim();
      ws = int.tryParse(week.group(2) ?? '');
      we = int.tryParse(week.group(3) ?? '') ?? ws;
      continue;
    }

    final other = _otherHeadingRe.firstMatch(line);
    if (other != null) {
      flush();
      title = (other.group(1) ?? other.group(2) ?? '')
          .replaceAll(RegExp(r'\*+'), '')
          .replaceFirst(RegExp(r':\s*$'), '')
          .trim();
      ws = null;
      we = null;
      if (title.isEmpty) title = null;
      continue;
    }

    if (title != null) {
      bullets.add(line.replaceFirst(RegExp(r'^[-*•]\s*'), ''));
    }
  }
  flush();
  return sections;
}

/// The week-shaped sections, or [] when there are fewer than two of them.
///
/// Under two headings there is no timeline to draw and the caller must show
/// plain text instead: a wrong map is worse than no map.
List<RecoveryPhase> weekPhases(List<RecoveryPhase> sections) {
  final weeks = sections.where((s) => s.weekStart != null).toList();
  return weeks.length >= 2 ? weeks : const [];
}

/// Parse Agent 4 text into week phases. Returns [] when fewer than two phase
/// headings are found - the caller must then show plain text instead.
List<RecoveryPhase> parseRecoveryPhases(String text) =>
    weekPhases(parseRecoverySections(text));

/// Which phase the patient is in NOW, from the extracted discharge date.
/// Returns null when the date is missing/unparseable or no phase matches -
/// the map then renders without a marker rather than guessing.
int? currentPhaseIndex(List<RecoveryPhase> phases, String? dischargeDateText,
    {DateTime? now}) {
  final discharged = parseAppointmentDate(dischargeDateText);
  if (discharged == null) return null;
  final days = (now ?? DateTime.now()).difference(discharged).inDays;
  if (days < 0) return null;
  final week = (days ~/ 7) + 1;
  for (var i = 0; i < phases.length; i++) {
    final p = phases[i];
    if (p.weekStart != null && week >= p.weekStart! && week <= (p.weekEnd ?? p.weekStart!)) {
      return i;
    }
  }
  // Past the last named week range → the final phase is "now".
  final last = phases.last;
  if (last.weekEnd != null && week > last.weekEnd!) return phases.length - 1;
  return null;
}
