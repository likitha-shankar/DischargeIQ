// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

/// Warning signs. The safety-critical section.
///
/// The redesign (Aug 2026) changes weight, not content. The old layout drew
/// three tinted boxes of equal size, which flattened the one hierarchy in
/// this app that must never be flat: tier 1 now has a solid header, heavier
/// body type and a real Call 911 button; tier 2 stays open in amber; tier 3
/// collapses behind its own count, which is the decision the old layout
/// already made.
///
/// The rule that does not change: tiers 1 and 2 are NEVER collapsible.
/// Putting emergency criteria behind a tap would mean a frightened patient
/// has to go looking for the thing that tells them to call an ambulance.
///
/// Everything the original showed is still here: the AI-generated notice
/// above the tiers, each symptom's explanation, the Agent 6 follow-up
/// questions below, and the general 911 advice when the document listed
/// nothing.
class _WarningsBody extends StatefulWidget {
  const _WarningsBody({
    required this.escalationText,
    required this.extraction,
    required this.simulator,
  });

  final String escalationText;
  final dynamic extraction;
  final dynamic simulator;

  @override
  State<_WarningsBody> createState() => _WarningsBodyState();
}

class _WarningsBodyState extends State<_WarningsBody> {
  bool _tier3Open = false;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = widget.extraction is Map
        ? widget.extraction as Map
        : <dynamic, dynamic>{};

    // Tier data does NOT exist in the extraction schema: red_flag_symptoms is
    // one flat list with no urgency attached. The tiers live only in Agent 5's
    // prose, under headers it is contractually required to emit, so they are
    // parsed from there. The extraction keys are still checked first in case a
    // future schema carries them directly.
    var tier1 = _items(ext, const ['call_911_signs', 'emergency_signs', 'tier_1']);
    var tier2 = _items(ext, const ['er_today_signs', 'urgent_signs', 'tier_2']);
    var tier3 = _items(ext, const ['call_doctor_signs', 'tier_3']);

    if (tier1.isEmpty && tier2.isEmpty && tier3.isEmpty) {
      final parsed = parseEscalationTiers(widget.escalationText);
      tier1 = parsed.call911;
      tier2 = parsed.erToday;
      tier3 = parsed.callDoctor;
    }

    // Last resort only. red_flag_symptoms carries no urgency, so putting it in
    // a tier would be inventing one - it goes in the lowest tier, which is the
    // safe direction to be wrong in only because the tier headings still tell
    // the patient what each level means.
    if (tier1.isEmpty && tier2.isEmpty && tier3.isEmpty) {
      tier3 = _items(ext, const ['red_flag_symptoms', 'warning_signs']);
    }

    final hasTiers = tier1.isNotEmpty || tier2.isNotEmpty || tier3.isNotEmpty;

    return SectionScroll(
      children: [
        const SectionEyebrow('Warning signs', color: sdDanger),
        const SizedBox(height: 8),
        if (hasTiers) ...[
          const SectionHeadline('Three levels. Start at the top.', size: 22),
          const SizedBox(height: 14),
        ],
        // The AI-generated notice sits ABOVE the tiers, where the original
        // put it. It is the HITL framing on the one tab where acting on a
        // wrong answer is dangerous, so it is not a footnote.
        const _EscalationDisclaimer(),
        const SizedBox(height: 12),
        if (hasTiers) ...[
          if (tier1.isNotEmpty) ...[
            _Tier1Card(items: tier1),
            const SizedBox(height: 12),
          ],
          if (tier2.isNotEmpty) ...[
            _Tier2Card(items: tier2),
            const SizedBox(height: 12),
          ],
          if (tier3.isNotEmpty) ...[
            _Tier3Card(
              items: tier3,
              open: _tier3Open,
              onToggle: () => setState(() => _tier3Open = !_tier3Open),
            ),
            const SizedBox(height: 12),
          ],
        ] else if (widget.escalationText.trim().isNotEmpty)
          // Agent 5 produced prose without its required headers. Show it
          // whole rather than parse a tier out of text that has none - and
          // NOT collapsible: escalation text must never sit behind a tap.
          PatientText(text: widget.escalationText)
        else
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
        // Agent 6 questions render BELOW all escalation content: a patient
        // opening this tab in a crisis must hit the 911 list first, not
        // meta-commentary about their document.
        _GapCallout(
          simulator: widget.simulator,
          keywords: const [
            'symptom', 'emergency', '911', 'er ', 'warning',
            'sign', 'fever', 'pain', 'breathe', 'bleeding',
          ],
          dark: dark,
        ),
      ],
    );
  }

  /// Symptom lists carried directly on the extraction, if a future schema
  /// ever adds them. Plain strings there have no explanation to split off.
  List<EscalationItem> _items(Map ext, List<String> keys) {
    for (final k in keys) {
      final v = ext[k];
      if (v is List && v.isNotEmpty) {
        return v
            .map((e) => '$e')
            .where((e) => e.trim().isNotEmpty)
            .map((e) => EscalationItem(e, ''))
            .toList();
      }
    }
    return const [];
  }
}

/// "Written by AI, confirm with your care team." Kept prominent and tinted
/// like the tier it warns about, rather than greyed out at the bottom.
class _EscalationDisclaimer extends StatelessWidget {
  const _EscalationDisclaimer();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
      decoration: BoxDecoration(
        color: dark ? sdDanger.withValues(alpha: 0.15) : sdDangerTint,
        borderRadius: BorderRadius.circular(sdRadiusInner),
        border: Border.all(color: dark ? sdDanger.withValues(alpha: 0.3) : sdDangerLine),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline,
              size: 17, color: dark ? const Color(0xFFFFB4B4) : sdDanger),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              'This guide is written by AI from your discharge paperwork. '
              'Call your care team to confirm what counts as an emergency '
              'for you.',
              style: TextStyle(
                fontSize: 12,
                height: 1.5,
                color: dark ? const Color(0xFFFFD5D5) : const Color(0xFF7F1D1D),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Hand a URL to the phone, and say so plainly when it cannot open it.
///
/// Failing silently is not acceptable on the tier-1 card: someone tapping
/// "Call 911" must not be left looking at a screen that did nothing.
Future<void> _open(BuildContext context, Uri url) async {
  final messenger = ScaffoldMessenger.of(context);
  var opened = false;
  try {
    opened = await launchUrl(url, mode: LaunchMode.externalApplication);
  } on PlatformException {
    opened = false;
  } on MissingPluginException {
    opened = false;
  }
  if (!opened) {
    messenger.showSnackBar(
      const SnackBar(content: Text('Could not start that call from here.')),
    );
  }
}

/// Tier 1. Solid header, a real phone action, never collapsible.
class _Tier1Card extends StatelessWidget {
  const _Tier1Card({required this.items});

  final List<EscalationItem> items;

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: sdDangerTint,
        borderRadius: BorderRadius.circular(sdRadiusCard),
        border: Border.all(color: sdDanger, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: sdDanger,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: const Row(
              children: [
                Icon(Icons.emergency, size: 20, color: Colors.white),
                SizedBox(width: 10),
                Text(
                  'CALL 911 NOW IF',
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.3,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 11),
                    child: _TierBullet(
                      item: item,
                      color: sdDanger,
                      emphasis: true,
                    ),
                  ),
              ],
            ),
          ),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: sdDanger,
                shape: const RoundedRectangleBorder(),
              ),
              onPressed: () => _open(context, Uri(scheme: 'tel', path: '911')),
              icon: const Icon(Icons.call, size: 21),
              label: const Text(
                'Call 911',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Tier 2. Amber, open by default: same-day care is still urgent.
class _Tier2Card extends StatelessWidget {
  const _Tier2Card({required this.items});

  final List<EscalationItem> items;

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: sdWarnTint,
        borderRadius: BorderRadius.circular(sdRadiusCard),
        border: Border.all(color: sdWarnLine),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFFF5E4C4))),
            ),
            child: const Row(
              children: [
                Icon(Icons.schedule, size: 19, color: sdWarn),
                SizedBox(width: 10),
                Text(
                  'GO TO THE ER TODAY IF',
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5,
                    color: sdWarnInk,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 13, 16, 5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _TierBullet(item: item, color: sdWarn),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Tier 3. The only collapsible tier, by definition the "call during office
/// hours" list. Together the three tiers run to ~275 words on a real
/// document, which is too much red and amber to scan when frightened.
class _Tier3Card extends StatelessWidget {
  const _Tier3Card({
    required this.items,
    required this.open,
    required this.onToggle,
  });

  final List<EscalationItem> items;
  final bool open;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: sdSafeTint,
        borderRadius: BorderRadius.circular(sdRadiusCard),
        border: Border.all(color: sdSafeLine),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onToggle,
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Row(
                  children: [
                    const Icon(Icons.phone_in_talk_outlined,
                        size: 19, color: sdSafe),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        'CALL YOUR DOCTOR IF',
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.5,
                          color: sdSafeInk,
                        ),
                      ),
                    ),
                    Text(
                      items.length == 1 ? '1 thing' : '${items.length} things',
                      style: const TextStyle(
                          fontSize: 11.5, color: Color(0xFF316241)),
                    ),
                    Icon(open ? Icons.expand_less : Icons.expand_more,
                        size: 20, color: sdSafe),
                  ],
                ),
              ),
            ),
          ),
          if (open)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final item in items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _TierBullet(item: item, color: sdSafe),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// One symptom line: the symptom carries the weight, Agent 5's explanation
/// follows it in lighter type.
///
/// Both halves are shown. Showing the symptom alone made the tiers scannable
/// but stripped out why it matters, which is the detail that told a patient
/// whether their own symptom was the one being described.
class _TierBullet extends StatelessWidget {
  const _TierBullet({
    required this.item,
    required this.color,
    this.emphasis = false,
  });

  final EscalationItem item;

  /// Bullet colour, matching the tier.
  final Color color;

  /// Tier 1 only: heavier symptom type.
  final bool emphasis;

  @override
  Widget build(BuildContext context) {
    // These cards keep their light tint in dark mode - a tinted emergency
    // card that inverts stops reading as an emergency - so the text colour is
    // fixed against that tint rather than taken from the theme.
    const ink = sdInk;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 6,
          height: 6,
          margin: const EdgeInsets.only(top: 7, right: 10),
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: item.symptom,
                  style: TextStyle(
                    fontSize: emphasis ? 14.5 : 14,
                    height: 1.45,
                    fontWeight:
                        emphasis ? FontWeight.w600 : FontWeight.w500,
                    color: ink,
                  ),
                ),
                if (item.detail.isNotEmpty)
                  TextSpan(
                    text: '\n${item.detail}',
                    style: const TextStyle(
                      fontSize: 13,
                      height: 1.45,
                      fontWeight: FontWeight.w400,
                      color: Color(0xFF44554E),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
