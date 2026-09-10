/// Condensing learning cards without losing anything.
///
/// The cards showed a domain's entire agent output - about 4,000 characters
/// across five cards on a median corpus document, worst case 6,957 in the
/// medications card alone - between a baseline quiz and a post-quiz, for
/// someone who has just left hospital.
///
/// The danger in fixing that is obvious and worth testing hard: a length
/// budget that silently drops the tail is the omission failure this project
/// measures everywhere else, introduced on purpose in the one place a patient
/// is being taught. So the central assertion here is not "the card is short".
/// It is "nothing was lost".
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:dischargeiq_mobile/services/learning_card.dart';

/// Prose long enough to fold, in realistic multi-line shape.
String _longProse([int lines = 12]) => [
      for (var i = 1; i <= lines; i++)
        'This is explanation line $i, long enough to add up quickly.',
    ].join('\n');

void main() {
  group('nothing is ever lost', () {
    test('summary plus more reconstructs the whole explanation', () {
      const facts = '• Furosemide 40 mg\n• Lisinopril 20 mg';
      final prose = _longProse();
      final card = buildLearningCard(
          domain: 'medications', facts: facts, prose: prose);

      expect(card.hasMore, isTrue);
      for (var i = 1; i <= 12; i++) {
        expect(card.full, contains('explanation line $i'),
            reason: 'line $i vanished');
      }
      expect(card.full, contains('Furosemide 40 mg'));
    });

    test('every fact stays above the fold', () {
      // The facts are what the question asked about. Folding them away would
      // hide the answer behind a tap.
      final facts = [for (var i = 1; i <= 20; i++) '• Medicine $i'].join('\n');
      final card = buildLearningCard(
          domain: 'medications', facts: facts, prose: _longProse());
      for (var i = 1; i <= 20; i++) {
        expect(card.summary, contains('Medicine $i'));
      }
    });
  });

  group('the fold lands on a line boundary', () {
    test('no line is cut in half', () {
      final card = buildLearningCard(
          domain: 'activity', facts: '', prose: _longProse());
      for (final line in card.summary.split('\n')) {
        if (line.trim().isEmpty) continue;
        expect(line.trim(), endsWith('.'),
            reason: 'sliced mid-line: ${line.trim()}');
      }
    });

    test('a bullet list folds between bullets', () {
      const prose = '• Walk a little each day, building up slowly over time\n'
          '• Do not lift anything heavy for the first two weeks at all\n'
          '• Rest when you feel tired rather than pushing on through it\n'
          '• Ask someone to help you with the shopping for a little while\n'
          '• Go back to work only when your care team says it is fine';
      final card = buildLearningCard(
          domain: 'activity', facts: '', prose: prose);
      for (final line in card.summary.split('\n')) {
        if (line.trim().isNotEmpty) expect(line.trim(), startsWith('•'));
      }
    });

    test('one very long first line is kept rather than showing nothing', () {
      final prose = 'x' * 900;
      final card = buildLearningCard(
          domain: 'diagnosis', facts: '', prose: prose);
      expect(card.summary.trim(), isNotEmpty);
      expect(card.summary, contains('x'));
    });
  });

  group('short cards are left alone', () {
    test('a card that already fits gets no read-more', () {
      final card = buildLearningCard(
          domain: 'diagnosis',
          facts: '',
          prose: 'Your heart was not pumping as well as it should.');
      expect(card.hasMore, isFalse);
      expect(card.more, isNull);
    });

    test('an empty card produces nothing to expand', () {
      final card = buildLearningCard(domain: 'follow_up', facts: '', prose: '');
      expect(card.hasMore, isFalse);
      expect(card.summary, isEmpty);
    });
  });

  group('the warning-signs card is never folded', () {
    test('a long escalation guide stays whole', () {
      final guide = 'CALL 911 IMMEDIATELY\n${_longProse(20)}\n'
          'GO TO THE ER TODAY\nCALL YOUR DOCTOR';
      final card = buildLearningCard(
          domain: 'red_flags', facts: '• Chest pain', prose: guide);
      expect(card.hasMore, isFalse,
          reason: 'emergency routing must not sit behind a tap');
      expect(card.summary, contains('CALL 911 IMMEDIATELY'));
      expect(card.summary, contains('CALL YOUR DOCTOR'));
    });

    test('911 is on screen without any interaction', () {
      final card = buildLearningCard(
          domain: 'red_flags', facts: '', prose: 'Call 911 if you cannot breathe.\n${_longProse(30)}');
      expect(card.summary, contains('911'));
    });

    test('every other domain may fold', () {
      for (final domain in ['diagnosis', 'medications', 'activity', 'follow_up']) {
        final card = buildLearningCard(
            domain: domain, facts: '', prose: _longProse());
        expect(card.hasMore, isTrue, reason: '$domain did not fold');
      }
    });
  });

  group('it actually condenses', () {
    test('a long card is meaningfully shorter above the fold', () {
      final prose = _longProse(30);
      final card = buildLearningCard(
          domain: 'medications', facts: '• Furosemide', prose: prose);
      expect(card.summary.length, lessThan(prose.length ~/ 2),
          reason: 'no real reduction: ${card.summary.length} of ${prose.length}');
    });
  });
}
