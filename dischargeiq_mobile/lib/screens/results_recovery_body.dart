// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _RecoveryBody extends StatelessWidget {
  const _RecoveryBody({required this.trajectory, required this.extraction});
  final String trajectory;
  final dynamic extraction;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final rawActivity = ext['activity_restrictions'];
    final rawDietary = ext['dietary_restrictions'];
    final condition = '${ext['discharge_condition'] ?? ''}';
    final activity = rawActivity is List
        ? rawActivity.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];
    final dietary = rawDietary is List
        ? rawDietary.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];

    final hasRestrictions = activity.isNotEmpty || dietary.isNotEmpty || condition.isNotEmpty;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (hasRestrictions) ...[
            // Full-width, stacked: long instructions in half-width columns
            // were unreadable (patient feedback July 2026).
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
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: dark ? kTeal.withValues(alpha: 0.15) : kTealPale,
                  borderRadius: BorderRadius.circular(kRadiusField),
                ),
                child: RichText(
                  text: TextSpan(
                    style: TextStyle(
                      fontSize: 13,
                      color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                    ),
                    children: [
                      const TextSpan(text: 'Condition at discharge: ', style: TextStyle(fontWeight: FontWeight.w600)),
                      TextSpan(text: condition),
                    ],
                  ),
                ),
              ),
            ],
            Divider(color: dark ? kBorderDark : kBorderLight, height: 28),
          ],
          Text(
            'Your recovery timeline',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 10),
          Builder(builder: (context) {
            if (trajectory.isEmpty) {
              return Text(
                'No recovery timeline available.',
                style: TextStyle(
                  fontSize: 14,
                  height: 1.6,
                  color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                ),
              );
            }
            // Journey map (wave 3): visual path when the text parses into
            // week phases; conservative fallback to plain text otherwise.
            final phases = parseRecoveryPhases(trajectory);
            if (phases.isEmpty) {
              return PatientText(text: trajectory, fontSize: 14, collapsible: true);
            }
            final ext = extraction is Map ? extraction as Map : const {};
            final here = currentPhaseIndex(
                phases, '${ext['discharge_date'] ?? ''}');
            return _JourneyPath(phases: phases, here: here, dark: dark);
          }),
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
        border: Border.all(color: dark ? kBorderDark : kBorderLight),
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

List<String> _extractTierBullets(String text, String start, String? next) {
  final up = text.toUpperCase();
  final s = up.indexOf(start.toUpperCase());
  if (s < 0) return [];
  final end = next == null ? text.length : up.indexOf(next.toUpperCase(), s + start.length);
  final raw = end < 0
      ? text.substring(s + start.length).trim()
      : text.substring(s + start.length, end).trim();
  if (raw.isEmpty) return [];
  return raw
      .split('\n')
      .map((l) => l.replaceFirst(RegExp(r'^[•\-\*]\s*'), '').trim())
      .where((l) => l.isNotEmpty)
      .toList();
}

/// Recovery journey, one CARD per phase. The current week ("You are here",
/// pinned by the discharge date) opens expanded; every other week collapses
/// to its title + step count so the tab reads as a short list of weeks, not
/// a wall of bullets (patient feedback July 2026). Past weeks tint green -
/// progress framing, never a countdown.
class _JourneyPath extends StatefulWidget {
  const _JourneyPath({required this.phases, required this.here, required this.dark});

  final List<RecoveryPhase> phases;
  final int? here;
  final bool dark;

  @override
  State<_JourneyPath> createState() => _JourneyPathState();
}

class _JourneyPathState extends State<_JourneyPath> {
  late final Set<int> _open = {widget.here ?? 0};

  @override
  Widget build(BuildContext context) {
    final dark = widget.dark;
    final here = widget.here;
    final accent = dark ? kTealGlow : kTeal;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < widget.phases.length; i++)
          Builder(builder: (context) {
            final phase = widget.phases[i];
            final isHere = i == here;
            final isPast = here != null && i < here;
            final open = _open.contains(i);
            return Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 10),
              decoration: BoxDecoration(
                color: isHere
                    ? (dark ? kTeal.withValues(alpha: 0.18) : kTealPale)
                    : (dark ? kCardDark : kCardLight),
                borderRadius: BorderRadius.circular(kRadiusField),
                border: Border.all(
                  color: isHere ? accent : (dark ? kBorderDark : kBorderLight),
                  width: isHere ? 1.2 : 1,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  InkWell(
                    borderRadius: BorderRadius.circular(kRadiusField),
                    onTap: () => setState(() {
                      open ? _open.remove(i) : _open.add(i);
                    }),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                      child: Row(
                        children: [
                          // Week status marker: check = behind you, filled
                          // ring = now, open ring = ahead.
                          Icon(
                            isPast
                                ? Icons.check_circle_rounded
                                : (isHere
                                    ? Icons.radio_button_checked
                                    : Icons.radio_button_unchecked),
                            size: 20,
                            color: isPast || isHere
                                ? accent
                                : (dark ? kTextHintDark : kTextHintLight),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              phase.title,
                              style: TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w700,
                                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                              ),
                            ),
                          ),
                          if (isHere)
                            Container(
                              margin: const EdgeInsets.only(right: 8),
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: accent,
                                borderRadius: BorderRadius.circular(kRadiusField),
                              ),
                              child: Text(
                                'You are here',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                  color: dark ? kBgDark : Colors.white,
                                ),
                              ),
                            )
                          else
                            Padding(
                              padding: const EdgeInsets.only(right: 6),
                              child: Text(
                                '${phase.bullets.length} steps',
                                style: TextStyle(
                                  fontSize: 11.5,
                                  color: dark
                                      ? kTextSecondaryDark
                                      : kTextSecondaryLight,
                                ),
                              ),
                            ),
                          Icon(
                            open ? Icons.expand_less : Icons.expand_more,
                            size: 20,
                            color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (open)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 14, 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (final b in phase.bullets)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 5),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Padding(
                                    padding: const EdgeInsets.only(top: 7),
                                    child: Container(
                                      width: 5,
                                      height: 5,
                                      decoration: BoxDecoration(
                                        color: accent.withValues(alpha: 0.7),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 9),
                                  Expanded(
                                    child: Text(
                                      // Stray markdown emphasis markers never
                                      // reach the patient (same rule as
                                      // PatientText).
                                      b.replaceAll('*', '').trim(),
                                      style: TextStyle(
                                        fontSize: 13.5,
                                        height: 1.45,
                                        color: dark
                                            ? kTextPrimaryDark
                                            : kTextPrimaryLight,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            );
          }),
      ],
    );
  }
}

