// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

/// Recovery.
///
/// The redesign (Aug 2026) answers the two questions a patient actually has -
/// "where am I in this?" and "is my weight going the wrong way?" - with a
/// phase rail and a real weight trend, in place of the custom-painted journey
/// trail with its ridge flags and summit star.
///
/// What the original showed is still here: activity and food restrictions,
/// the condition at discharge, and phase text rendered through [PatientText]
/// so the agent's markdown does not leak as asterisks. Phases come from the
/// shared [parseRecoveryPhases] service, so this screen and the journey card
/// on the home page always agree on what week it is.
///
/// The weight series is local-only ([HealthLog]); no backend change.
class _RecoveryBody extends StatefulWidget {
  const _RecoveryBody({required this.trajectory, required this.extraction});

  final String trajectory;
  final dynamic extraction;

  @override
  State<_RecoveryBody> createState() => _RecoveryBodyState();
}

class _RecoveryBodyState extends State<_RecoveryBody> {
  List<WeightEntry> _weights = const [];
  double? _change;

  /// Phase the rail is showing. Null until the first build works out where
  /// today falls, so the patient lands on their own week rather than week 1.
  int? _selected;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final w = await HealthLog.weights(docId);
    final ch = await HealthLog.overnightChange(docId);
    if (!mounted) return;
    setState(() {
      _weights = w;
      _change = ch;
    });
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final c = SectionColors.of(context);
    final ext = widget.extraction is Map
        ? widget.extraction as Map
        : <dynamic, dynamic>{};

    final activity = _strings(ext['activity_restrictions']);
    final dietary = _strings(ext['dietary_restrictions']);
    final condition = '${ext['discharge_condition'] ?? ''}';

    // Parsed once into every heading-led block, then split: the week-shaped
    // ones drive the rail, and anything else ("When to expect improvement")
    // is advice about the whole recovery, so it renders as its own card
    // rather than as a stray bullet inside whichever week came last.
    final sections = parseRecoverySections(widget.trajectory);
    final phases = weekPhases(sections);
    final extras = phases.isEmpty
        ? const <RecoveryPhase>[]
        : sections.where((s) => s.weekStart == null).toList();
    // Where today actually falls, from the discharge date. The rail opens
    // there and tapping another phase overrides it for the session. Null when
    // the date is missing or unparseable - a real state, not a zero: the
    // original rendered the map without a "you are here" marker rather than
    // guessing, and so does this.
    final here = phases.isEmpty
        ? null
        : currentPhaseIndex(phases, '${ext['discharge_date'] ?? ''}');
    final shown = phases.isEmpty
        ? 0
        : (_selected ?? here ?? 0).clamp(0, phases.length - 1);

    return SectionScroll(
      children: [
        const SectionEyebrow('Recovery'),
        const SizedBox(height: 8),
        SectionHeadline(
          switch ((phases.isEmpty, here)) {
            (true, _) => 'How your recovery should go.',
            (false, final int i) => 'You are in ${phases[i].title.toLowerCase()} '
                'of ${phases.length == 1 ? 'one phase' : 'about ${phases.length} phases'}.',
            // Phases exist but the discharge date does not place the patient
            // in one. Describe the shape without claiming to know the week.
            _ => 'Your recovery runs in '
                '${phases.length == 1 ? 'one phase' : '${phases.length} phases'}.',
          },
          size: 22,
        ),
        const SizedBox(height: 14),
        _WeightCard(weights: _weights, change: _change, onLog: _logWeight),
        const SizedBox(height: 12),
        if (phases.isNotEmpty) ...[
          SectionCard(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _PhaseRail(
                  phases: phases,
                  selected: shown,
                  onSelect: (i) => setState(() => _selected = i),
                ),
                const SizedBox(height: 12),
                Divider(height: 1, color: c.lineSoft),
                const SizedBox(height: 12),
                Text(
                  phases[shown].title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: c.text,
                  ),
                ),
                const SizedBox(height: 6),
                _Bullets(bullets: phases[shown].bullets),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Advice that belongs to the recovery rather than to one week.
          for (final extra in extras) ...[
            SectionCard(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    extra.title,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: c.text,
                    ),
                  ),
                  const SizedBox(height: 6),
                  _Bullets(bullets: extra.bullets),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],
        ] else if (widget.trajectory.trim().isNotEmpty) ...[
          // Prose that did not parse into phases. Shown whole rather than
          // forced into a timeline the document never gave.
          SectionCard(
            child: PatientText(text: widget.trajectory, collapsible: true),
          ),
          const SizedBox(height: 12),
        ] else ...[
          const EmptySection(
            icon: Icons.timeline_outlined,
            title: 'No recovery timeline',
            message:
                'Your document did not describe what to expect week by week. '
                'Ask your care team how long recovery usually takes and what '
                'you can do in the meantime.',
          ),
          const SizedBox(height: 12),
        ],
        // Restrictions: the rules that apply for the whole recovery, not to
        // one phase, so they sit below the rail rather than inside it.
        if (activity.isNotEmpty)
          _RestrictionColumn(
            label: 'Activity',
            icon: Icons.directions_walk,
            items: activity,
            dark: dark,
          ),
        if (dietary.isNotEmpty) ...[
          const SizedBox(height: 10),
          _RestrictionColumn(
            label: 'Food & drink',
            icon: Icons.restaurant_outlined,
            items: dietary,
            dark: dark,
          ),
        ],
        if (condition.isNotEmpty) ...[
          const SizedBox(height: 10),
          SectionCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            color: c.accentTint,
            border: Colors.transparent,
            child: Text.rich(
              TextSpan(
                style: TextStyle(fontSize: 13, height: 1.45, color: c.text),
                children: [
                  const TextSpan(
                    text: 'Condition at discharge: ',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  TextSpan(text: condition),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }

  /// A JSON list field as clean strings; anything else as an empty list.
  List<String> _strings(dynamic raw) => raw is List
      ? raw.map((e) => '$e').where((e) => e.trim().isNotEmpty).toList()
      : const [];

  Future<void> _logWeight() async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final value = await showDialog<double>(
      context: context,
      builder: (ctx) => const _WeightDialog(),
    );
    if (value == null) return;
    await HealthLog.logWeight(docId, value);
    await _load();
    if (!mounted) return;
    final ch = _change;
    if (ch != null && ch >= 3) {
      // The paperwork's own rule: +3 lb overnight is an ER-today sign.
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.warning_amber_rounded, color: sdWarn, size: 32),
          title: const Text('That is a big jump'),
          content: Text(
            'You are up ${ch.toStringAsFixed(1)} lb since your last reading. '
            'Your discharge papers say a rise of 3 lb in a day means go to '
            'the ER today - it is fluid, not fat. Do not wait for your next '
            'appointment.',
            style: const TextStyle(height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Understood'),
            ),
          ],
        ),
      );
    }
  }
}

/// A phase or section's lines, one dot each.
///
/// Each line goes through [PatientText] rather than a bare [Text]: the agent
/// writes markdown, and rendering it raw put asterisks on screen.
class _Bullets extends StatelessWidget {
  const _Bullets({required this.bullets});

  final List<String> bullets;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final bullet in bullets)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 5,
                  height: 5,
                  margin: const EdgeInsets.only(top: 8, right: 9),
                  decoration:
                      BoxDecoration(color: c.accent, shape: BoxShape.circle),
                ),
                Expanded(child: PatientText(text: bullet, fontSize: 13.5)),
              ],
            ),
          ),
      ],
    );
  }
}

/// The week rail: every phase visible at once, the current one filled.
///
/// Bars grow left to right so the shape reads as progress rather than as a
/// chart of some quantity - there is no quantity here, only order.
class _PhaseRail extends StatelessWidget {
  const _PhaseRail({
    required this.phases,
    required this.selected,
    required this.onSelect,
  });

  final List<RecoveryPhase> phases;
  final int selected;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    // The rail carries a text label above each bar, so its height has to
    // follow the text. At 2.2x scaling a fixed 62px box clipped the week
    // labels, which are the only thing that says which phase you are on.
    final scale = MediaQuery.textScalerOf(context).scale(1.0);
    return SizedBox(
      height: 62 + (scale - 1.0) * 22,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < phases.length; i++)
            Expanded(
              child: Semantics(
                selected: i == selected,
                button: true,
                label: phases[i].title,
                child: GestureDetector(
                  onTap: () => onSelect(i),
                  behavior: HitTestBehavior.opaque,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2.5),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          phases[i].title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w600,
                            color: i == selected ? c.accent : c.textMute,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          height: 14.0 + (30.0 * (i + 1) / phases.length),
                          decoration: BoxDecoration(
                            color: i == selected
                                ? sdTeal
                                : (i < selected ? sdTealGlow : c.lineSoft),
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(7),
                              bottom: Radius.circular(3),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _RestrictionColumn extends StatelessWidget {
  const _RestrictionColumn({
    required this.label,
    required this.icon,
    required this.items,
    required this.dark,
  });
  final String label;
  final IconData icon;
  final List<String> items;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final accent = dark ? kTealGlow : kTeal;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(kRadiusField),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 17, color: accent),
              const SizedBox(width: 7),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                  color: accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 7, right: 8),
                    child: Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        color: accent,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      item,
                      style: TextStyle(
                        fontSize: 13.5,
                        height: 1.45,
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

/// Inline Agent 6 gap callout shown on Medications and Warning Signs tabs.
class _GapCallout extends StatelessWidget {
  const _GapCallout({required this.simulator, required this.keywords, required this.dark});
  final dynamic simulator;
  final List<String> keywords;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    if (simulator is! Map) return const SizedBox.shrink();
    final sim = simulator as Map;
    final concepts = sim['missed_concepts'];
    if (concepts is! List) return const SizedBox.shrink();
    final relevant = concepts.whereType<Map>().where((c) {
      if (c['answered_by_doc'] == true) return false;
      final sev = '${c['severity'] ?? ''}';
      if (sev != 'critical' && sev != 'moderate') return false;
      final text = ('${c['question'] ?? ''} ${c['gap_summary'] ?? ''}').toLowerCase();
      return keywords.any(text.contains);
    }).take(3).toList();
    if (relevant.isEmpty) return const SizedBox.shrink();

    return Container(
      // Full bleed: a short gap question must not draw a narrower
      // tinted card than the one above it.
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: dark ? const Color(0xFF78350F).withValues(alpha: 0.2) : const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border.all(color: const Color(0xFFFCD34D).withValues(alpha: dark ? 0.4 : 1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'AI Review flagged ${relevant.length} unanswered question${relevant.length == 1 ? '' : 's'} in this area',
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF78350F)),
          ),
          const SizedBox(height: 4),
          ...relevant.map(
            (c) => Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                '• ${c['question'] ?? ''}',
                style: const TextStyle(fontSize: 12, color: Color(0xFF92400E)),
              ),
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'See the Discharge Check tab for full details.',
            style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: Color(0xFFB45309)),
          ),
        ],
      ),
    );
  }
}


