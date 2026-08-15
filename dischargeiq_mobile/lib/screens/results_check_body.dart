// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _DischargeCheckBody extends StatelessWidget {
  const _DischargeCheckBody({required this.simulator});

  final dynamic simulator;

  static int _clampScore(dynamic raw) {
    try {
      final v = raw is int ? raw : int.parse('${raw ?? 0}');
      return max(0, min(10, v));
    } catch (_) {
      return 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;

    if (simulator is! Map) {
      return const _RichTextSection(
        text: 'Discharge quality check is not available for this analysis run.',
      );
    }

    final sim = simulator as Map<String, dynamic>;
    final gapScore = _clampScore(sim['overall_gap_score']);
    final summary = '${sim['simulator_summary'] ?? ''}';
    final missed = sim['missed_concepts'];
    final List<Map<dynamic, dynamic>> missedList =
        (missed is List) ? missed.whereType<Map<dynamic, dynamic>>().toList() : [];

    final Color scoreColor;
    final String scoreLabel;
    if (gapScore <= 3) {
      scoreColor = kTier3;
      scoreLabel = 'Low gap';
    } else if (gapScore <= 6) {
      scoreColor = kTier2;
      scoreLabel = 'Moderate gap';
    } else {
      scoreColor = kTier1;
      scoreLabel = 'High gap';
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHero(
            icon: Icons.fact_check_outlined,
            title: 'Discharge check',
            subtitle: 'What your paperwork may have missed',
          ),
          // HITL notice
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
              borderRadius: BorderRadius.circular(kRadiusField),
              border: Border.all(color: dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, size: 16, color: dark ? kTealGlow : kTeal),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'AI Review - Share these gaps with your care team. '
                    'This is not a diagnosis.',
                    style: TextStyle(
                      fontSize: 12,
                      height: 1.4,
                      color: dark ? kTealGlow : kTeal,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Gap score card
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: dark ? kCardDark : kCardLight,
              borderRadius: BorderRadius.circular(kRadiusField),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Gap Score',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(
                        color: scoreColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: scoreColor.withValues(alpha: 0.4)),
                      ),
                      child: Text(
                        '$gapScore / 10 - $scoreLabel',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: scoreColor,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: gapScore / 10,
                    minHeight: 8,
                    backgroundColor: scoreColor.withValues(alpha: dark ? 0.15 : 0.1),
                    valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
                  ),
                ),
                if (summary.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    summary,
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.4,
                      color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                    ),
                  ),
                ],
              ],
            ),
          ),

          // Missed concept cards
          if (missedList.isNotEmpty) ...[
            const SizedBox(height: 20),
            Text(
              'Gaps Flagged',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
            const SizedBox(height: 8),
            ...missedList
                .where((c) => c['answered_by_doc'] != true)
                .map((c) => _ConceptCard(concept: c, dark: dark)),
          ],

          // Answered concepts (collapsed by default)
          if (missedList.any((c) => c['answered_by_doc'] == true)) ...[
            const SizedBox(height: 12),
            _AnsweredConceptsExpander(
              concepts: missedList.where((c) => c['answered_by_doc'] == true).toList(),
              dark: dark,
            ),
          ],
        ],
      ),
    );
  }
}

class _ConceptCard extends StatelessWidget {
  const _ConceptCard({required this.concept, required this.dark});

  final Map<dynamic, dynamic> concept;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final severity = '${concept['severity'] ?? 'minor'}';
    final Color severityColor;
    final Color severityBg;
    final String severityLabel;
    switch (severity) {
      case 'critical':
        severityColor = kTier1;
        severityBg = kTier1Bg;
        severityLabel = 'Critical gap';
      case 'moderate':
        severityColor = kTier2;
        severityBg = kTier2Bg;
        severityLabel = 'Moderate gap';
      default:
        severityColor = kTier3;
        severityBg = kTier3Bg;
        severityLabel = 'Minor gap';
    }

    return Container(
      // Full bleed regardless of how short the question is. Without this the
      // card shrink-wraps its text, so a one-line question drew a narrower
      // tinted box than the one above it and the column looked ragged.
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: dark ? severityColor.withValues(alpha: 0.12) : severityBg,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border.all(color: severityColor.withValues(alpha: dark ? 0.35 : 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: severityColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              severityLabel,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w600,
                color: severityColor,
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${concept['question'] ?? ''}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          if ('${concept['gap_summary'] ?? ''}'.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '${concept['gap_summary']}',
              style: TextStyle(
                fontSize: 11,
                height: 1.4,
                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _AnsweredConceptsExpander extends StatefulWidget {
  const _AnsweredConceptsExpander({required this.concepts, required this.dark});

  final List<Map<dynamic, dynamic>> concepts;
  final bool dark;

  @override
  State<_AnsweredConceptsExpander> createState() => _AnsweredConceptsExpanderState();
}

class _AnsweredConceptsExpanderState extends State<_AnsweredConceptsExpander> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: widget.dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(kRadiusField),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(kRadiusField),
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_outline, size: 16, color: kTier3),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${widget.concepts.length} question${widget.concepts.length == 1 ? '' : 's'} answered by the document',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: widget.dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                  ),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded) ...[
            const Divider(height: 1),
            ...widget.concepts.map(
              (c) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check, size: 14, color: kTier3),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${c['question'] ?? ''}',
                        style: TextStyle(
                          fontSize: 12,
                          color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Diagnosis tab - "At a glance" badges + Agent 2 explanation text.
