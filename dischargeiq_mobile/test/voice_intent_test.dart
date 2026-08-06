/// test/voice_intent_test.dart
///
/// Tests the spoken-command parser behind the chat's microphone.
///
/// The failure that matters is misrouting: sending a real clinical question
/// into tab navigation would silently swallow it, so anything ambiguous must
/// fall through to the grounded chat.
library;

import 'package:dischargeiq_mobile/services/voice_intent.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('read requests', () {
    test('names the right tab for each section', () {
      const cases = {
        'read me my medications': 1,
        'read the warning signs': 3,
        'read out what happened': 0,
        'can you read my appointments': 2,
        'please read the recovery section': 4,
      };
      cases.forEach((phrase, expectedTab) {
        final intent = parseVoiceIntent(phrase);
        expect(intent.kind, VoiceIntentKind.readSection, reason: phrase);
        expect(intent.tabIndex, expectedTab, reason: phrase);
      });
    });

    test('every readable tab has a spoken label', () {
      for (final index in kReadableSections.keys) {
        expect(kSectionSpokenLabels[index], isNotNull);
      }
    });

    test('a longer keyword beats a shorter one inside it', () {
      // "follow up visit" must not be won by "visit" alone; both point at the
      // appointments tab here, but the rule protects future overlaps.
      expect(parseVoiceIntent('read my follow up visit').tabIndex, 2);
    });

    test('casing and punctuation do not matter', () {
      expect(parseVoiceIntent('READ MY MEDICINES!').kind,
          VoiceIntentKind.readSection);
    });
  });

  group('stop requests', () {
    test('plain stop phrases are recognised', () {
      for (final phrase in ['stop', 'stop reading', 'be quiet', 'pause']) {
        expect(parseVoiceIntent(phrase).kind, VoiceIntentKind.stopSpeaking,
            reason: phrase);
      }
    });

    test('a sentence that merely contains "stop" is still a question', () {
      // The dangerous case: someone asking about stopping a medication must
      // reach the grounded chat, which declines safely, rather than being
      // read as a command to shut up.
      final intent = parseVoiceIntent('should I stop taking my warfarin?');
      expect(intent.kind, VoiceIntentKind.question);
    });
  });

  group('questions', () {
    test('a clinical question is never routed to navigation', () {
      const questions = [
        'what is heart failure',
        'how do I take my medicines',
        'when should I call the doctor',
        'tell me about my medications',
        'my chest hurts right now',
        'can I lift my grandchild',
      ];
      for (final q in questions) {
        expect(parseVoiceIntent(q).kind, VoiceIntentKind.question, reason: q);
      }
    });

    test('a read verb with no section is a question, not a blind jump', () {
      expect(parseVoiceIntent('read that again').kind, VoiceIntentKind.question);
      expect(parseVoiceIntent('read').kind, VoiceIntentKind.question);
    });

    test('a section name with no read verb stays a question', () {
      // "my medications" alone is a topic, not a command - answering beats
      // reciting the whole tab at someone.
      expect(parseVoiceIntent('my medications').kind, VoiceIntentKind.question);
    });

    test('empty input is a question, not a crash', () {
      expect(parseVoiceIntent('').kind, VoiceIntentKind.question);
      expect(parseVoiceIntent('   ').kind, VoiceIntentKind.question);
    });
  });
}
