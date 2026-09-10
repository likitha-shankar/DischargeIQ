// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

/// What happened.
///
/// The redesign (Aug 2026) leads with the explanation's first sentence as a
/// headline, because that sentence IS the answer to "what happened to me",
/// and demotes the coded diagnosis to a supporting card that still carries
/// its SourceQuote provenance. Nothing the original showed was dropped: the
/// per-diagnosis audio explainer and the collapsible, glossary-aware
/// [PatientText] rendering are the same widgets the old layout used.
class _DiagnosisBody extends StatelessWidget {
  const _DiagnosisBody({
    required this.explanation,
    required this.extraction,
    this.documentType = '',
    this.result = const {},
    this.sessionId = '',
    required this.onNext,
  });

  final String explanation;
  final dynamic extraction;

  /// Router classification - drives the per-diagnosis audio explainer.
  final String documentType;

  /// The full pipeline result, sent to `/media/case` to narrate THIS
  /// document. Empty in tests that render the section on its own.
  final Map<String, dynamic> result;

  /// Backend session id, reused from `pdf_session_id` like the quiz does.
  final String sessionId;

  /// Moves to the Medications tab. The closing card is the one place this
  /// section points forward, so the patient is handed the next question
  /// rather than left to find the tab strip.
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final primaryDx = '${ext['primary_diagnosis'] ?? ''}';
    final rawSec = ext['secondary_diagnoses'];
    final secList = rawSec is List
        ? rawSec.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];

    final sentences = _splitLead(explanation);
    final medCount = _medCount(ext);

    return SectionScroll(
      children: [
        const SectionEyebrow('What happened'),
        const SizedBox(height: 8),
        if (sentences.lead.isNotEmpty) ...[
          SectionHeadline(sentences.lead, size: 25),
          const SizedBox(height: 14),
        ],
        // Audio explainer - the accessibility path for anyone who cannot
        // comfortably read the summary.
        //
        // No longer gated on documentType: the per-case explainer narrates
        // the patient's own document, so it works for an "unknown"
        // classification too. The card hides itself when neither the per-case
        // nor the per-condition source is available.
        AudioExplainerCard(
          documentType: documentType,
          sessionId: sessionId,
          pipelinePayload: result,
        ),
        const SizedBox(height: 4),
        if (primaryDx.isNotEmpty || secList.isNotEmpty) ...[
          SectionCard(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (primaryDx.isNotEmpty) ...[
                  const SectionMiniLabel('Main condition'),
                  const SizedBox(height: 4),
                  Text(
                    primaryDx,
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w600,
                      color: c.text,
                    ),
                  ),
                  // Provenance (trust feature): the exact document passage
                  // Agent 1 extracted this diagnosis from.
                  SourceQuote(source: ext['primary_diagnosis_source']),
                ],
                if (secList.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Divider(height: 1, color: c.lineSoft),
                  const SizedBox(height: 12),
                  const SectionMiniLabel('Also treated'),
                  const SizedBox(height: 6),
                  ...secList.map(
                    (dx) => Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 16,
                            height: 6,
                            margin: const EdgeInsets.only(top: 6, right: 9),
                            decoration: BoxDecoration(
                              color: sdTealLight,
                              borderRadius: BorderRadius.circular(3),
                            ),
                          ),
                          Expanded(
                            child: Text(
                              dx,
                              style: TextStyle(fontSize: 13.5, color: c.text),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 14),
        ],
        if (explanation.isEmpty)
          const EmptySection(
            icon: Icons.monitor_heart_outlined,
            title: 'No diagnosis explanation',
            message:
                'We could not find a clear diagnosis in your document to '
                'explain. Ask your care team what your main condition is '
                'called, and what it means for you.',
          )
        else
          // PatientText, not a bare Text: it renders the agent's markdown,
          // links glossary terms and collapses a long explanation. A plain
          // Text here leaked ** into the patient's face.
          PatientText(text: sentences.rest, collapsible: true),
        if (medCount > 0) ...[
          const SizedBox(height: 16),
          SectionCard(
            onTap: onNext,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Next: the $medCount medicines you came home with',
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: c.text,
                    ),
                  ),
                ),
                Icon(Icons.arrow_forward, size: 20, color: c.accent),
              ],
            ),
          ),
        ],
      ],
    );
  }

  /// How many medicines the patient came home with, for the closing card.
  int _medCount(Map ext) {
    final m = ext['medications'];
    return m is List ? m.length : 0;
  }

  /// First sentence becomes the headline, the rest stays body copy.
  ///
  /// A "sentence" longer than 180 characters is a paragraph, not a headline,
  /// so in that case everything stays in the body and no headline is shown.
  static _Lead _splitLead(String text) {
    final t = text.trim();
    if (t.isEmpty) return const _Lead('', '');
    final idx = t.indexOf(RegExp(r'(?<=[.!?])\s'));
    if (idx < 0 || idx > 180) return _Lead('', t);
    return _Lead(t.substring(0, idx).trim(), t.substring(idx).trim());
  }
}

/// A diagnosis explanation split into its headline sentence and the rest.
class _Lead {
  const _Lead(this.lead, this.rest);
  final String lead;
  final String rest;
}
/// Medications tab - per-drug cards with status badge + expandable rationale.
class _MedicationsBody extends StatelessWidget {
  const _MedicationsBody({
    required this.rationaleText,
    required this.extraction,
    required this.simulator,
  });
  final String rationaleText;
  final dynamic extraction;
  final dynamic simulator;

  static const _borderColor = {
    'new': kMedNew,
    'changed': kMedChanged,
    'continued': kMedContinued,
    'discontinued': kMedDiscontinued,
  };

  static const _badgeLabel = {
    'new': 'NEW',
    'changed': 'CHANGED',
    'continued': 'CONTINUED',
    'discontinued': 'STOPPED',
  };

  Map<String, String> _parseRationale(String text) {
    final blocks = <String, String>{};
    for (final block in text.split(RegExp(r'\n\s*\n'))) {
      final trimmed = block.trim();
      if (trimmed.isEmpty) continue;
      final nl = trimmed.indexOf('\n');
      if (nl < 0) continue;
      var header = trimmed.substring(0, nl).trim();
      final body = trimmed.substring(nl + 1).trim();
      if (!header.endsWith(':') || body.isEmpty) continue;
      header = header.replaceAll(RegExp(r' [--] stopping:?$', caseSensitive: false), '').replaceAll(':', '').trim();
      if (header.isNotEmpty) blocks[header.toLowerCase()] = body;
    }
    return blocks;
  }

  String? _findRationale(String name, Map<String, String> blocks) {
    final needle = name.trim().toLowerCase();
    if (blocks.containsKey(needle)) return blocks[needle];
    for (final key in blocks.keys) {
      if (key.startsWith(needle) || needle.startsWith(key)) return blocks[key];
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final meds = ext['medications'];
    final medList = meds is List ? meds.whereType<Map>().toList() : <Map>[];
    final rationale = _parseRationale(rationaleText);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      children: [
        const _SectionHero(
          icon: Icons.medication_outlined,
          title: 'Your medications',
          subtitle: 'What each one is for and how to take it',
        ),
        if (medList.isNotEmpty) ...[
          // Medication reminders (competitor-gap B1): patient-confirmed
          // daily nudges, scheduled locally on the phone only.
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            child: Material(
              color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
              borderRadius: BorderRadius.circular(kRadiusField),
              child: InkWell(
                borderRadius: BorderRadius.circular(kRadiusField),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => MedicationRemindersScreen(
                      extraction: extraction is Map
                          ? (extraction as Map).cast<String, dynamic>()
                          : <String, dynamic>{},
                    ),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                  child: Row(
                    children: [
                      Icon(Icons.notifications_active_outlined,
                          size: 19, color: dark ? kTealGlow : kTeal),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          'Never miss a dose - set up daily reminders',
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: dark ? kTealGlow : kTeal,
                          ),
                        ),
                      ),
                      Icon(Icons.chevron_right,
                          size: 18, color: dark ? kTealGlow : kTeal),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
        if (medList.isEmpty)
          const EmptySection(
            icon: Icons.medication_outlined,
            title: 'No medications listed',
            message:
                'Your document did not include a list of medicines to take at '
                'home. Keep taking what you took before unless your care team '
                'told you otherwise, and ask them to confirm your list.',
          )
        else
          // Every medicine, always on screen.
          //
          // This list used to collapse after five behind a "Show all" toggle,
          // on CDC plain-language guidance that readers with limited health
          // literacy may not comfortably process more than five items at
          // once. That guidance is about absorbing comparable items in one
          // pass, not about a reference list a patient scrolls and returns
          // to - and the collapse created the worse failure: 30% of corpus
          // documents carry more than five medications (worst case 23), so
          // roughly a third of patients could close the app never knowing
          // the later ones existed. Density is a cosmetic problem; a
          // prescription nobody saw is a safety one.
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: medList.asMap().entries.map((e) {
            final med = e.value;
            final name = '${med['name'] ?? 'Unknown'}';
            final status = '${med['status'] ?? ''}'.toLowerCase();
            final dose = '${med['dose'] ?? ''}';
            final freq = '${med['frequency'] ?? ''}';
            final duration = '${med['duration'] ?? ''}';
            final details = [dose, freq, duration].where((s) => s.isNotEmpty).join(' · ');
            final borderCol = _borderColor[status] ?? kTextHintLight;
            final badgeTxt = _badgeLabel[status] ?? '';
            final rationaleBody = _findRationale(name, rationale);
            return _MedCard(
              name: name,
              details: details,
              status: status,
              borderColor: borderCol,
              badgeText: badgeTxt,
              rationale: rationaleBody,
              source: med['source'],
              dark: dark,
            );
            }).toList(),
          ),
        // AI-review questions BELOW the medication list - same rule as the
        // warning tab: the patient's actual content first, meta last.
        _GapCallout(
          simulator: simulator,
          keywords: const ['medication', 'medicine', 'drug', 'dose', 'pill', 'tablet', 'inhaler', 'insulin', 'prescription'],
          dark: dark,
        ),
      ],
    );
  }
}

class _MedCard extends StatefulWidget {
  const _MedCard({
    required this.name,
    required this.details,
    required this.status,
    required this.borderColor,
    required this.badgeText,
    required this.rationale,
    this.source,
    required this.dark,
  });
  final String name;
  final String details;
  final String status;
  final Color borderColor;
  final String badgeText;
  final String? rationale;
  final dynamic source; // SourceSpan map - provenance for this medication
  final bool dark;

  @override
  State<_MedCard> createState() => _MedCardState();
}

class _MedCardState extends State<_MedCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: widget.dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border(left: BorderSide(color: widget.borderColor, width: 4)),
        boxShadow: widget.dark
            ? null
            : [const BoxShadow(color: Color(0x0A000000), blurRadius: 4, offset: Offset(0, 1))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.name,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                          color: widget.dark ? kTextPrimaryDark : kTextPrimaryLight,
                        ),
                      ),
                      if (widget.details.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          widget.details,
                          style: TextStyle(
                            fontSize: 12,
                            color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                          ),
                        ),
                      ],
                      SourceQuote(source: widget.source),
                      if (widget.status == 'changed') ...[
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF3C7),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'Changed from previous prescription',
                            style: TextStyle(fontSize: 10, color: Color(0xFF92400E)),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (widget.badgeText.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: widget.borderColor,
                      borderRadius: BorderRadius.circular(kRadiusField),
                    ),
                    child: Text(
                      widget.badgeText,
                      style: const TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (widget.rationale != null) ...[
            InkWell(
              borderRadius: const BorderRadius.only(
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(8),
              ),
              onTap: () => setState(() => _expanded = !_expanded),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    Text(
                      _expanded ? 'Hide explanation' : 'Why you\'re taking this',
                      style: TextStyle(
                        fontSize: 11,
                        color: widget.dark ? kTealGlow : kTeal,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(
                      _expanded ? Icons.expand_less : Icons.expand_more,
                      size: 14,
                      color: widget.dark ? kTealGlow : kTeal,
                    ),
                  ],
                ),
              ),
            ),
            if (_expanded)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: Text(
                  widget.rationale!,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ),
          ] else
            const SizedBox(height: 10),
        ],
      ),
    );
  }
}

/// Warning Signs tab - red-flag bullet list + 3-tier escalation cards with bullets.
