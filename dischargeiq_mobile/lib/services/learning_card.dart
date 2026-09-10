/// services/learning_card.dart
///
/// Splits a learning card into what a patient sees immediately and what sits
/// behind one tap. Pure Dart, so the rules are unit-testable.
///
/// WHY
/// ---
/// The cards showed the entire agent output for a domain. Measured across the
/// 106-document corpus: about 4,000 characters across the five cards on a
/// median document, roughly four minutes of reading, with a worst-case
/// medications card of 6,957 on its own. That sits between a baseline quiz and
/// a post-quiz, for someone who has just left hospital. Feedback, 10 Sep 2026:
/// condense the learning cards, balancing detail with brevity.
///
/// CONDENSE, NEVER TRUNCATE
/// ------------------------
/// Nothing is removed. The card leads with the FACTS - the extracted list of
/// medicines, dates or symptoms - because those are what the question was
/// about, and they are short. The agent's prose explanation follows, cut at a
/// LINE boundary so a bullet or sentence is never sliced in half, with the
/// remainder one tap away.
///
/// A budget that silently drops the tail would be the omission failure this
/// project measures everywhere else, introduced deliberately in the one place
/// a patient is being taught.
///
/// WHAT IS NEVER COLLAPSED
/// -----------------------
/// The warning-signs card. Agent 5's output is the three-tier escalation guide
/// and the top tier is "call 911". Hiding any of it behind a tap to save a
/// patient forty seconds of reading is not a trade worth making, and hard
/// rule 3 already forbids ambiguity in that output. It stays whole.
library;

/// One learning card, split into an always-visible part and an optional rest.
class LearningCard {
  const LearningCard({
    required this.domain,
    required this.summary,
    this.more,
  });

  final String domain;

  /// Always on screen: the facts, plus as much explanation as fits.
  final String summary;

  /// The remainder, or null when there is nothing more to show.
  final String? more;

  bool get hasMore => (more ?? '').trim().isNotEmpty;

  /// Everything, as the card read before condensing. Used by tests to assert
  /// that nothing was lost, and by any caller that needs the whole text.
  String get full => hasMore ? '$summary\n$more' : summary;
}

/// Domains whose card is shown whole, whatever its length.
///
/// Only one, and it is not a length judgement: the warning-signs card carries
/// emergency routing.
const Set<String> _neverCollapse = {'red_flags'};

/// How much explanation rides along with the facts before the fold.
///
/// Chosen so a card fits a phone screen beside its heading without scrolling,
/// not from a readability formula - the constraint here is attention, not
/// reading grade, and the text has already passed the grade gate.
const int _proseBudget = 280;

/// Build a card from its facts and its explanation.
///
/// Args:
///   domain: Quiz domain the card covers ("medications", "red_flags", ...).
///   facts: Short extracted list - medicines, dates, symptoms. Always shown in
///     full, because this is what the question asked about.
///   prose: The agent's explanation. Split at a line boundary if long.
///
/// Returns:
///   LearningCard with `more` set only when there was genuinely something left
///   over. A card that just fits is not given an empty "read more".
LearningCard buildLearningCard({
  required String domain,
  required String facts,
  required String prose,
}) {
  final factText = facts.trim();
  final proseText = prose.trim();

  if (_neverCollapse.contains(domain)) {
    return LearningCard(
      domain: domain,
      summary: [factText, proseText].where((s) => s.isNotEmpty).join('\n\n'),
    );
  }

  if (proseText.length <= _proseBudget) {
    return LearningCard(
      domain: domain,
      summary: [factText, proseText].where((s) => s.isNotEmpty).join('\n\n'),
    );
  }

  // Accumulate whole lines. Splitting mid-line would cut a bullet or a
  // sentence in half, which reads as a rendering bug rather than as a
  // deliberate fold.
  final lines = proseText.split('\n');
  final kept = <String>[];
  var used = 0;
  for (final line in lines) {
    // Always keep the first line even when it alone exceeds the budget: a
    // fold that shows nothing is worse than one that shows slightly too much.
    if (kept.isNotEmpty && used + line.length > _proseBudget) break;
    kept.add(line);
    used += line.length + 1;
  }
  final rest = lines.sublist(kept.length).join('\n').trim();

  return LearningCard(
    domain: domain,
    summary: [factText, kept.join('\n').trim()]
        .where((s) => s.isNotEmpty)
        .join('\n\n'),
    more: rest.isEmpty ? null : rest,
  );
}
