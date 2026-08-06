/// services/voice_intent.dart
///
/// Works out what a spoken (or typed) chat message is actually asking for:
/// an answer, or for a section of the summary to be read out loud.
///
/// Clinical review, Aug 2026: an AI companion should be able to read a tab
/// aloud on request. That means "read me my medications" must NOT go to the
/// grounded chat endpoint - it is a navigation command, not a question.
///
/// Pure Dart, no Flutter, no plugins, so the matching rules are unit-testable
/// without a microphone or a device.
library;

/// What the patient's message is asking the app to do.
enum VoiceIntentKind {
  /// A normal question for the grounded chat.
  question,

  /// A request to read one section of the summary out loud.
  readSection,

  /// A request to stop talking. Recognised separately because someone asking
  /// for silence must never have to wait for an answer to finish first.
  stopSpeaking,
}

/// A parsed message: what it wants, and which tab it means.
class VoiceIntent {
  const VoiceIntent(this.kind, {this.tabIndex, this.sectionLabel});

  final VoiceIntentKind kind;

  /// Results tab index for [VoiceIntentKind.readSection]. Null otherwise.
  final int? tabIndex;

  /// Human label of the matched section, for the confirmation line.
  final String? sectionLabel;
}

/// Tab index → the words a patient might actually use for it.
///
/// Indices match the results screen tab order: What happened, Medications,
/// Appointments, Warning signs, Recovery. The quiz and AI-review tabs are
/// deliberately absent - "read me the quiz" is not a sensible request, and
/// reading the AI review aloud would recite the app's own gap analysis at
/// someone who asked about their care.
const Map<int, List<String>> kReadableSections = {
  0: ['what happened', 'diagnosis', 'condition', 'what is wrong', 'my illness'],
  1: ['medication', 'medicine', 'meds', 'pills', 'drugs', 'tablets'],
  2: ['appointment', 'follow up', 'follow-up', 'visit', 'next visit', 'doctor visit'],
  3: [
    'warning sign',
    'warning',
    'red flag',
    'when to call',
    'when should i call',
    'emergency',
    'danger',
  ],
  4: ['recovery', 'recover', 'getting better', 'activity', 'what can i do', 'timeline'],
};

/// Friendly label per tab, used in the app's spoken confirmation.
const Map<int, String> kSectionSpokenLabels = {
  0: 'what happened',
  1: 'your medications',
  2: 'your appointments',
  3: 'the warning signs',
  4: 'your recovery',
};

/// Verbs that mean "say this out loud", rather than "tell me the answer".
///
/// "tell me about my medications" is deliberately NOT here: it reads as a
/// question, and answering it is more useful than reciting a whole tab.
const List<String> _kReadVerbs = [
  'read',
  'read out',
  'read aloud',
  'say',
  'speak',
  'play',
  'narrate',
];

const List<String> _kStopPhrases = [
  'stop',
  'stop reading',
  'stop talking',
  'be quiet',
  'quiet',
  'shut up',
  'pause',
  'enough',
];

/// Classify one message.
///
/// Args:
///   raw: What the patient said or typed.
///
/// Returns:
///   A [VoiceIntent]. Anything not clearly a read or stop request is a
///   question, because misrouting a real question into navigation is far
///   worse than reading a tab the patient did not want.
VoiceIntent parseVoiceIntent(String raw) {
  final text = raw.toLowerCase().trim();
  if (text.isEmpty) return const VoiceIntent(VoiceIntentKind.question);

  // Stop first: a request for silence must not wait behind anything else.
  // Matched on the whole utterance so "stop" wins but "I stopped my pills"
  // stays a question.
  final stripped = text.replaceAll(RegExp(r'[^a-z\s]'), '').trim();
  if (_kStopPhrases.contains(stripped)) {
    return const VoiceIntent(VoiceIntentKind.stopSpeaking);
  }

  final hasReadVerb = _kReadVerbs.any((v) => RegExp('\\b$v\\b').hasMatch(text));
  if (!hasReadVerb) return const VoiceIntent(VoiceIntentKind.question);

  // A read verb with no recognisable section is still a question - "read"
  // alone tells us nothing about what to open.
  final match = _matchSection(text);
  if (match == null) return const VoiceIntent(VoiceIntentKind.question);

  return VoiceIntent(
    VoiceIntentKind.readSection,
    tabIndex: match,
    sectionLabel: kSectionSpokenLabels[match],
  );
}

/// Longest-keyword-wins section match, or null when nothing matches.
///
/// Longest first so "follow up visit" is not beaten by "visit", and so a
/// phrase containing two section words resolves to the more specific one.
int? _matchSection(String text) {
  int? best;
  var bestLength = 0;
  kReadableSections.forEach((index, keywords) {
    for (final keyword in keywords) {
      if (keyword.length > bestLength && text.contains(keyword)) {
        best = index;
        bestLength = keyword.length;
      }
    }
  });
  return best;
}
