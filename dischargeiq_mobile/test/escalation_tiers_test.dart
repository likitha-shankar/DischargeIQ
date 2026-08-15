/// test/escalation_tiers_test.dart
///
/// Tests the tier parser behind the warning-signs screen.
///
/// The failure that matters is a symptom landing in the WRONG tier: showing a
/// 911 symptom under "call your doctor" is the most dangerous mistake this app
/// could make, so the boundary cases are tested harder than the happy path.
///
/// The sample is a verbatim slice of real Agent 5 output taken off the device,
/// not invented for the test.
library;

import 'package:dischargeiq_mobile/services/escalation_tiers.dart';
import 'package:flutter_test/flutter_test.dart';

const _realGuide = '''
CALL 911 IMMEDIATELY
These symptoms are life-threatening. Do not drive yourself.
- Unresponsive or cannot be woken: This means your brain is not getting enough oxygen.
- Thoughts of harming yourself or others: Seek help right away from a crisis service.
- Seizure that lasts longer than 5 minutes: Call emergency services right away.

GO TO THE ER TODAY
Do not wait until tomorrow. Go within a few hours.
- Severe mood swings that feel out of control: Your doctor needs to know.
- Hearing voices or seeing things: This needs to be checked today.

CALL YOUR DOCTOR
During office hours is fine.
- Trouble sleeping for more than three nights: Your dose may need review.
''';

void main() {
  group('real Agent 5 output', () {
    final tiers = parseEscalationTiers(_realGuide);

    test('each tier gets its own symptoms', () {
      expect(tiers.call911, hasLength(3));
      expect(tiers.erToday, hasLength(2));
      expect(tiers.callDoctor, hasLength(1));
    });

    test('no symptom leaks across a tier boundary', () {
      // The dangerous direction: a 911 symptom appearing anywhere lower.
      expect(tiers.erToday.join(' '), isNot(contains('Unresponsive')));
      expect(tiers.callDoctor.join(' '), isNot(contains('Unresponsive')));
      expect(tiers.callDoctor.join(' '), isNot(contains('Hearing voices')));
      expect(tiers.call911.first.symptom, 'Unresponsive or cannot be woken');
    });

    test('the symptom and its explanation are both kept', () {
      // The explanation used to be discarded at the colon, which left the
      // tier cards reading as bare two-word phrases. Both halves survive now,
      // split so the card can weight the symptom over the reason.
      final item = tiers.callDoctor.single;
      expect(item.symptom, 'Trouble sleeping for more than three nights');
      expect(item.detail, 'Your dose may need review.');
    });

    test('a line with no colon still parses, with an empty explanation', () {
      final tiers = parseEscalationTiers('CALL 911\n- Chest pain');
      expect(tiers.call911.single.symptom, 'Chest pain');
      expect(tiers.call911.single.detail, isEmpty);
    });

    test('the intro sentence under a header is not read as a symptom', () {
      expect(tiers.call911.join(' '), isNot(contains('life-threatening')));
      expect(tiers.erToday.join(' '), isNot(contains('Do not wait')));
    });
  });

  group('degrading safely', () {
    test('empty or missing input yields empty tiers, never a crash', () {
      expect(parseEscalationTiers(null).isEmpty, isTrue);
      expect(parseEscalationTiers('').isEmpty, isTrue);
      expect(parseEscalationTiers('   ').isEmpty, isTrue);
    });

    test('prose with no headers yields nothing rather than guessing', () {
      // Callers must then show the prose. Inventing a tier from unstructured
      // text would be worse than showing no tiers at all.
      final tiers = parseEscalationTiers(
          'Watch out for chest pain and call someone if it happens.');
      expect(tiers.isEmpty, isTrue);
    });

    test('a missing middle tier does not swallow the next one', () {
      const guide = '''
CALL 911
- Chest pain

CALL YOUR DOCTOR
- Mild headache
''';
      final tiers = parseEscalationTiers(guide);
      expect(tiers.call911.map((e) => e.symptom), ['Chest pain']);
      expect(tiers.erToday, isEmpty);
      // The bug this guards: the 911 section running to the end of the
      // document and absorbing "Mild headache" as a 911 symptom.
      expect(tiers.callDoctor.map((e) => e.symptom), ['Mild headache']);
      expect(tiers.call911.join(' '), isNot(contains('Mild headache')));
    });

    test('the short header form is matched, not just the long one', () {
      // escalation_agent.py only guarantees "CALL 911", not
      // "CALL 911 IMMEDIATELY".
      final tiers = parseEscalationTiers('CALL 911\n- Chest pain');
      expect(tiers.call911.map((e) => e.symptom), ['Chest pain']);
    });

    test('bullet styles other than a dash are accepted', () {
      final tiers = parseEscalationTiers('CALL 911\n• Chest pain\n* Fainting');
      expect(tiers.call911.map((e) => e.symptom), ['Chest pain', 'Fainting']);
    });

    test('a paragraph starting with a dash is not shown as a symptom', () {
      final long = '- ${'word ' * 40}';
      expect(parseEscalationTiers('CALL 911\n$long').call911, isEmpty);
    });
  });
}
