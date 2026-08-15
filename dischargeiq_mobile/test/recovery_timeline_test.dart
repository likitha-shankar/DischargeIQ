/// test/recovery_timeline_test.dart
///
/// Unit checks for the recovery journey map parser (services/
/// recovery_timeline.dart): phase splitting from Agent 4 markdown-ish text,
/// the conservative fewer-than-two-phases fallback, week-range math for the
/// "you are here" marker, and null-over-guess on unparseable dates.
library;

import 'package:dischargeiq_mobile/services/recovery_timeline.dart';
import 'package:flutter_test/flutter_test.dart';

const _agent4Text = '''
**Week 1:**
- You will feel tired at home. This is normal.
- Weigh yourself every morning.

**Weeks 2-4:**
- Start short walks.
- Keep limiting salt.

**Weeks 5-6:**
- You may return to light activities.
''';

void main() {
  test('parses week phases with titles, ranges, and bullets', () {
    final phases = parseRecoveryPhases(_agent4Text);
    expect(phases.length, 3);
    expect(phases[0].title, 'Week 1');
    expect(phases[0].weekStart, 1);
    expect(phases[0].weekEnd, 1);
    expect(phases[0].bullets.length, 2);
    expect(phases[1].weekStart, 2);
    expect(phases[1].weekEnd, 4);
    expect(phases[2].bullets.single, contains('light activities'));
  });

  test('falls back to empty on unstructured text (a wrong map is worse)', () {
    expect(parseRecoveryPhases('Rest well and take your medicines daily.'),
        isEmpty);
    expect(parseRecoveryPhases('**Week 1:**\n- only one phase'), isEmpty);
  });

  test('you-are-here lands in the right week range', () {
    final phases = parseRecoveryPhases(_agent4Text);
    final d0 = DateTime(2026, 7, 1);
    // Day 3 → week 1 → phase 0
    expect(currentPhaseIndex(phases, '2026-07-01', now: d0.add(const Duration(days: 3))), 0);
    // Day 15 → week 3 → phase 1 (Weeks 2-4)
    expect(currentPhaseIndex(phases, '2026-07-01', now: d0.add(const Duration(days: 15))), 1);
    // Day 40 → week 6 → phase 2
    expect(currentPhaseIndex(phases, '2026-07-01', now: d0.add(const Duration(days: 40))), 2);
    // Far past the last range → stays on the final phase
    expect(currentPhaseIndex(phases, '2026-07-01', now: d0.add(const Duration(days: 100))), 2);
  });

  test('no marker without a parseable discharge date', () {
    final phases = parseRecoveryPhases(_agent4Text);
    expect(currentPhaseIndex(phases, null), isNull);
    expect(currentPhaseIndex(phases, 'unknown'), isNull);
    // Future discharge date (data error) → no marker, never a guess.
    expect(
        currentPhaseIndex(phases, '2099-01-01', now: DateTime(2026, 7, 1)),
        isNull);
  });

  group('non-week sections', () {
    // Verbatim shape of the trailing section Agent 4 emits after the last
    // week. It used to fall into that week's bullet list, so the Recovery
    // tab showed "When to expect improvement" as a bullet of Week 3-4.
    const guide = '''
**Week 1:**
- Rest often.

**Week 3-4:**
- You can walk for longer.

**When to expect improvement:**
- Improvement can be slow and takes time.
- Progress will happen week by week.
''';

    test('a trailing section is its own block, not the last week\'s bullets', () {
      final sections = parseRecoverySections(guide);
      expect(sections, hasLength(3));
      expect(sections.last.title, 'When to expect improvement');
      expect(sections.last.weekStart, isNull);
      expect(sections.last.bullets, hasLength(2));
      // The dangerous part: week 3-4 keeping advice that is not its own.
      final week34 = sections[1];
      expect(week34.bullets, ['You can walk for longer.']);
      expect(week34.bullets.join(' '), isNot(contains('Improvement can be slow')));
    });

    test('weekPhases keeps only the week-shaped sections', () {
      final weeks = weekPhases(parseRecoverySections(guide));
      expect(weeks.map((w) => w.title), ['Week 1', 'Week 3-4']);
    });

    test('the two-heading rule still applies to weeks alone', () {
      // One week heading plus a trailing section is not a timeline.
      const thin = '''
**Week 1:**
- Rest often.

**When to expect improvement:**
- Slowly.
''';
      expect(parseRecoveryPhases(thin), isEmpty);
      expect(parseRecoverySections(thin), hasLength(2));
    });
  });
}
