// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _WarningsBody extends StatelessWidget {
  const _WarningsBody({
    required this.escalationText,
    required this.extraction,
    required this.simulator,
  });
  final String escalationText;
  final dynamic extraction;
  final dynamic simulator;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final rawFlags = ext['red_flag_symptoms'];
    final flags = rawFlags is List
        ? rawFlags.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];
    final src = escalationText.toUpperCase();
    final hasTiers = src.contains('CALL 911') || src.contains('ER TODAY') || src.contains('CALL YOUR DOCTOR');

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      children: [
        const _SectionHero(
          icon: Icons.emergency_outlined,
          title: 'Warning signs',
          subtitle: 'When to call your doctor - and when to call 911',
          tint: kTier1,
        ),
        // Safety notice
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: dark ? kTier1.withValues(alpha: 0.15) : kTier1Bg,
            borderRadius: BorderRadius.circular(kRadiusField),
            border: Border.all(color: kTier1.withValues(alpha: 0.3)),
          ),
          child: Text(
            'This guide is AI-generated. Call your care team to confirm what needs emergency care for your situation.',
            style: TextStyle(fontSize: 12, color: dark ? kTier1 : const Color(0xFF7F1D1D)),
          ),
        ),

        // Red-flag bullets from extraction - FALLBACK ONLY. When Agent 5's
        // three-tier guide exists it restates these same symptoms with
        // explanations, so showing both is pure duplication (patient
        // feedback July 2026: overwhelming).
        if (flags.isNotEmpty && !hasTiers) ...[
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: dark ? kTier1.withValues(alpha: 0.12) : const Color(0xFFFCEBEB),
              borderRadius: BorderRadius.circular(kRadiusField),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Go to the ER or call 911 if you have:',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: dark ? kTier1 : const Color(0xFF7F1D1D),
                  ),
                ),
                const SizedBox(height: 8),
                ...flags.map(
                  (f) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          margin: const EdgeInsets.only(top: 5, right: 10),
                          decoration: const BoxDecoration(
                            color: Color(0xFFC0392B),
                            shape: BoxShape.circle,
                          ),
                        ),
                        Expanded(
                          child: Text(
                            f,
                            style: TextStyle(
                              fontSize: 13,
                              color: dark ? kTextPrimaryDark : const Color(0xFF7F1D1D),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],

        // Nothing to show: the source document named no warning signs and
        // Agent 5 produced no tiers. Common on real paperwork - warning signs
        // appear in only ~34% of the MTSamples corpus - so this tab must say
        // so rather than render an empty panel under the hero. The safety note
        // is general guidance, labelled as such, because leaving a patient
        // with no escalation information at all is its own risk.
        if (!hasTiers && flags.isEmpty)
          const EmptySection(
            icon: Icons.emergency_outlined,
            title: 'No warning signs listed',
            message:
                'Your document did not list specific symptoms to watch for. '
                'That does not mean there are none. Ask your doctor or nurse '
                'which symptoms should worry you, and write them down before '
                'you leave.',
            safetyNote:
                'Call 911 for chest pain, trouble breathing, heavy bleeding, '
                'fainting, or sudden weakness in the face or arms. This is '
                'general advice for anyone, not taken from your paperwork.',
          ),

        // 3-tier escalation cards
        if (hasTiers) ...[
          const SizedBox(height: 8),
          _EscalationTier(
            title: 'CALL 911 IMMEDIATELY',
            body: _extractTierBullets(escalationText, 'CALL 911 IMMEDIATELY', 'GO TO THE ER TODAY'),
            fg: kTier1,
            bg: kTier1Bg,
            dark: dark,
          ),
          _EscalationTier(
            title: 'GO TO THE ER TODAY',
            body: _extractTierBullets(escalationText, 'GO TO THE ER TODAY', 'CALL YOUR DOCTOR'),
            fg: kTier2,
            bg: kTier2Bg,
            dark: dark,
          ),
          // Only the routine tier collapses. Together the three tiers run to
          // ~275 words and 16 bullets on a real document, which is too much
          // red-and-amber to scan when frightened. This is the one tier where
          // a tap costs nothing: by definition it is the "call during office
          // hours" list, not an emergency.
          _EscalationTier(
            title: 'CALL YOUR DOCTOR',
            body: _extractTierBullets(escalationText, 'CALL YOUR DOCTOR', null),
            fg: kTier3,
            bg: kTier3Bg,
            dark: dark,
            collapsible: true,
          ),
        ] else if (!hasTiers && escalationText.isNotEmpty)
          Text(
            escalationText,
            style: TextStyle(
              fontSize: 14,
              height: 1.5,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
        // AI-review questions render BELOW all escalation content: a patient
        // opening this tab in a crisis must hit the 911 list first, not
        // meta-commentary about their document.
        _GapCallout(
          simulator: simulator,
          keywords: const ['symptom', 'emergency', '911', 'er ', 'warning', 'sign', 'fever', 'pain', 'breathe', 'bleeding'],
          dark: dark,
        ),
      ],
    );
  }
}

class _EscalationTier extends StatefulWidget {
  const _EscalationTier({
    required this.title,
    required this.body,
    required this.fg,
    required this.bg,
    required this.dark,
    this.collapsible = false,
  });
  final String title;
  final List<String> body;
  final Color fg;
  final Color bg;
  final bool dark;

  /// Whether this tier may start collapsed.
  ///
  /// ONLY the non-urgent "call your doctor" tier sets this. The 911 and
  /// same-day ER tiers are always fully visible: putting emergency criteria
  /// behind a tap would mean a frightened patient has to go looking for the
  /// thing that tells them to call an ambulance. Density is worth reducing,
  /// but never at that price.
  final bool collapsible;

  @override
  State<_EscalationTier> createState() => _EscalationTierState();
}

class _EscalationTierState extends State<_EscalationTier> {
  late bool _open = !widget.collapsible;

  @override
  Widget build(BuildContext context) {
    final title = widget.title;
    final body = widget.body;
    final fg = widget.fg;
    final bg = widget.bg;
    final dark = widget.dark;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? fg.withValues(alpha: 0.18) : bg,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border.all(color: fg.withValues(alpha: dark ? 0.45 : 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.collapsible)
            InkWell(
              onTap: () => setState(() => _open = !_open),
              child: Row(
                children: [
                  Expanded(
                    child: Text(title,
                        style: TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 13, color: fg)),
                  ),
                  // The count stays visible while collapsed, so the patient
                  // knows something is there rather than assuming it is empty.
                  Text(
                    '${body.length} to watch for',
                    style: TextStyle(fontSize: 11.5, color: fg),
                  ),
                  Icon(_open ? Icons.expand_less : Icons.expand_more,
                      size: 20, color: fg),
                ],
              ),
            )
          else
            Text(title,
                style: TextStyle(
                    fontWeight: FontWeight.w700, fontSize: 13, color: fg)),
          if (_open) const SizedBox(height: 8),
          if (_open)
            ...body.map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 6, right: 8),
                    decoration: BoxDecoration(color: fg, shape: BoxShape.circle),
                  ),
                  Expanded(
                    child: Text(
                      line,
                      style: TextStyle(
                        fontSize: 13,
                        height: 1.4,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Recovery tab - activity/dietary restrictions + discharge condition + timeline.
