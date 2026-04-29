import 'dart:math' show max, min;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';
import 'package:dischargeiq_mobile/widgets/guided_tour.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Six-tab discharge summary with optional first-run guided tour.
class ResultsScreen extends StatefulWidget {
  const ResultsScreen({super.key});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  static const _tabLabels = [
    'What happened',
    'Medications',
    'Appointments',
    'Warning signs',
    'Recovery',
    'Discharge Check',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabLabels.length, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeStartTour());
  }

  Future<void> _startTour() async {
    if (!mounted) return;
    showGuidedTourOverlay(
      context: context,
      tabController: _tabController,
      onFinished: () {
        SharedPreferences.getInstance().then(
          (p) => p.setBool('tour_completed', true),
        );
      },
    );
  }

  Future<void> _maybeStartTour() async {
    final prefs = await SharedPreferences.getInstance();
    final done = prefs.getBool('tour_completed') ?? false;
    if (!done && mounted) {
      await _startTour();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dp = context.watch<DischargeProvider>();
    final r = dp.result;
    if (r == null) {
      return const Scaffold(body: Center(child: Text('No result')));
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined, color: Colors.white),
            onPressed: () async {
              final res = await Navigator.push<Object?>(
                context,
                MaterialPageRoute<Object?>(builder: (_) => const SettingsScreen()),
              );
              if (res == 'start_tour' && mounted) {
                await _startTour();
              }
            },
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Container(
            key: TourKeys.tabBar,
            color: kTeal,
            child: TabBar(
              controller: _tabController,
              isScrollable: true,
              indicatorColor: Colors.white,
              labelColor: Colors.white,
              unselectedLabelColor: Colors.white70,
              tabs: [for (final t in _tabLabels) Tab(text: t)],
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          _PipelineStatusBanner(status: '${r['pipeline_status'] ?? ''}'),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                KeyedSubtree(
                  key: TourKeys.diagnosis,
                  child: _DiagnosisBody(
                    explanation: '${r['diagnosis_explanation'] ?? ''}',
                    extraction: r['extraction'],
                  ),
                ),
                KeyedSubtree(
                  key: TourKeys.medications,
                  child: _MedicationsBody(
                    rationaleText: '${r['medication_rationale'] ?? ''}',
                    extraction: r['extraction'],
                    simulator: r['patient_simulator'],
                  ),
                ),
                KeyedSubtree(
                  key: TourKeys.appointments,
                  child: _AppointmentsBody(extraction: r['extraction']),
                ),
                KeyedSubtree(
                  key: TourKeys.warnings,
                  child: _WarningsBody(
                    escalationText: '${r['escalation_guide'] ?? ''}',
                    extraction: r['extraction'],
                    simulator: r['patient_simulator'],
                  ),
                ),
                _RecoveryBody(
                  trajectory: '${r['recovery_trajectory'] ?? ''}',
                  extraction: r['extraction'],
                ),
                KeyedSubtree(
                  key: TourKeys.dischargeCheck,
                  child: _DischargeCheckBody(simulator: r['patient_simulator']),
                ),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: TourKeys.chat,
        onPressed: () => _openChat(context, r),
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.chat_bubble_outline),
        label: const Text('Ask'),
      ),
    );
  }
}

Future<void> _openChat(BuildContext context, Map<String, dynamic> result) async {
  final ctrl = TextEditingController();
  final messages = <Map<String, String>>[];
  var sending = false;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (ctx) {
      return StatefulBuilder(
        builder: (ctx, setSt) {
          Future<void> send() async {
            final q = ctrl.text.trim();
            if (q.isEmpty || sending) return;
            setSt(() {
              sending = true;
              messages.add({'role': 'you', 'text': q});
            });
            ctrl.clear();
            try {
              final data = await ApiService().chat(
                message: q,
                sessionId: DateTime.now().millisecondsSinceEpoch.toString(),
                pipelineContext: result,
              );
              setSt(() {
                messages.add({'role': 'ai', 'text': '${data['reply'] ?? ''}'});
              });
            } catch (_) {
              setSt(() {
                messages.add({'role': 'ai', 'text': 'Could not reach chat right now.'});
              });
            } finally {
              setSt(() => sending = false);
            }
          }

          return SafeArea(
            child: Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 12,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 12,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Ask about your discharge', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 260,
                    child: ListView.builder(
                      itemCount: messages.length,
                      itemBuilder: (c, i) {
                        final m = messages[i];
                        final isYou = m['role'] == 'you';
                        return Align(
                          alignment: isYou ? Alignment.centerRight : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.symmetric(vertical: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            decoration: BoxDecoration(
                              color: isYou ? kTeal.withValues(alpha: 0.12) : Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(m['text'] ?? ''),
                          ),
                        );
                      },
                    ),
                  ),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: ctrl,
                          decoration: const InputDecoration(hintText: 'Ask in plain language...'),
                          onSubmitted: (_) => send(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        onPressed: sending ? null : send,
                        style: ElevatedButton.styleFrom(backgroundColor: kTeal, foregroundColor: Colors.white),
                        child: Text(sending ? '...' : 'Send'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      );
    },
  );
}


/// Thin banner shown when the pipeline ran with warnings or partial output.
class _PipelineStatusBanner extends StatelessWidget {
  const _PipelineStatusBanner({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    if (status == 'complete') return const SizedBox.shrink();
    final isPartial = status == 'partial';
    final color = isPartial ? kTier1 : kTier2;
    final bg = isPartial ? kTier1Bg : kTier2Bg;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final label = isPartial
        ? 'Some sections could not be generated. Retry or check your API key.'
        : 'Analysis complete with warnings. Some sections may be incomplete.';
    return Container(
      color: dark ? color.withValues(alpha: 0.18) : bg,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: TextStyle(fontSize: 11, color: color),
            ),
          ),
        ],
      ),
    );
  }
}

class _RichTextSection extends StatelessWidget {
  const _RichTextSection({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 15,
          height: 1.45,
          color: dark ? kTextPrimaryDark : kTextPrimaryLight,
        ),
      ),
    );
  }
}

/// Rich Discharge Check / AI Review tab — mirrors the Streamlit web UI.
/// Shows: HITL notice, gap score bar, severity-coded missed concept cards.
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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // HITL notice
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, size: 16, color: dark ? kTealGlow : kTeal),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'AI Review — Share these gaps with your care team. '
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
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: dark ? kBorderDark : kBorderLight),
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
                        '$gapScore / 10 — $scoreLabel',
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
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: dark ? severityColor.withValues(alpha: 0.12) : severityBg,
        borderRadius: BorderRadius.circular(10),
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
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: widget.dark ? kBorderDark : kBorderLight),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  Icon(Icons.check_circle_outline, size: 16, color: kTier3),
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
                    Icon(Icons.check, size: 14, color: kTier3),
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

/// Diagnosis tab — "At a glance" badges + Agent 2 explanation text.
class _DiagnosisBody extends StatelessWidget {
  const _DiagnosisBody({required this.explanation, required this.extraction});
  final String explanation;
  final dynamic extraction;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final primaryDx = '${ext['primary_diagnosis'] ?? ''}';
    final rawSec = ext['secondary_diagnoses'];
    final secList = rawSec is List
        ? rawSec.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (primaryDx.isNotEmpty || secList.isNotEmpty) ...[
            if (primaryDx.isNotEmpty) ...[
              _DxLabel(label: 'Your main condition', dark: dark),
              const SizedBox(height: 4),
              _DxBadgeRow(text: primaryDx, dark: dark),
            ],
            if (secList.isNotEmpty) ...[
              const SizedBox(height: 10),
              _DxLabel(label: 'Other conditions treated', dark: dark),
              const SizedBox(height: 4),
              ...secList.map((dx) => _DxBadgeRow(text: dx, dark: dark)),
            ],
            const SizedBox(height: 12),
            Divider(color: dark ? kBorderDark : kBorderLight),
            const SizedBox(height: 12),
          ],
          Text(
            explanation.isEmpty ? 'No explanation available.' : explanation,
            style: TextStyle(
              fontSize: 15,
              height: 1.5,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
        ],
      ),
    );
  }
}

class _DxLabel extends StatelessWidget {
  const _DxLabel({required this.label, required this.dark});
  final String label;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Text(
      label.toUpperCase(),
      style: TextStyle(
        fontSize: 10,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
        color: dark ? kTextSecondaryDark : kTextSecondaryLight,
      ),
    );
  }
}

class _DxBadgeRow extends StatelessWidget {
  const _DxBadgeRow({required this.text, required this.dark});
  final String text;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 18,
            height: 8,
            decoration: BoxDecoration(
              color: dark ? kTealLight : kTeal,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 14,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Medications tab — per-drug cards with status badge + expandable rationale.
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
      header = header.replaceAll(RegExp(r' [—-] stopping:?$', caseSensitive: false), '').replaceAll(':', '').trim();
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
      padding: const EdgeInsets.all(16),
      children: [
        _GapCallout(
          simulator: simulator,
          keywords: const ['medication', 'medicine', 'drug', 'dose', 'pill', 'tablet', 'inhaler', 'insulin', 'prescription'],
          dark: dark,
        ),
        if (medList.isEmpty)
          Text(
            'No medications found in this document.',
            style: TextStyle(color: dark ? kTextSecondaryDark : kTextSecondaryLight),
          )
        else
          ...medList.asMap().entries.map((e) {
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
              dark: dark,
            );
          }),
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
    required this.dark,
  });
  final String name;
  final String details;
  final String status;
  final Color borderColor;
  final String badgeText;
  final String? rationale;
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
        borderRadius: BorderRadius.circular(8),
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
                      borderRadius: BorderRadius.circular(10),
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

/// Warning Signs tab — red-flag bullet list + 3-tier escalation cards with bullets.
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
      padding: const EdgeInsets.all(16),
      children: [
        // Safety notice
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: dark ? kTier1.withValues(alpha: 0.15) : kTier1Bg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: kTier1.withValues(alpha: 0.3)),
          ),
          child: Text(
            'This guide is AI-generated. Call your care team to confirm what needs emergency care for your situation.',
            style: TextStyle(fontSize: 12, color: dark ? kTier1 : const Color(0xFF7F1D1D)),
          ),
        ),

        _GapCallout(
          simulator: simulator,
          keywords: const ['symptom', 'emergency', '911', 'er ', 'warning', 'sign', 'fever', 'pain', 'breathe', 'bleeding'],
          dark: dark,
        ),

        // Red-flag bullets from extraction
        if (flags.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: dark ? kTier1.withValues(alpha: 0.12) : const Color(0xFFFCEBEB),
              borderRadius: BorderRadius.circular(8),
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

        // 3-tier escalation cards
        if (hasTiers) ...[
          if (flags.isNotEmpty) Divider(color: dark ? kBorderDark : kBorderLight),
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
          _EscalationTier(
            title: 'CALL YOUR DOCTOR',
            body: _extractTierBullets(escalationText, 'CALL YOUR DOCTOR', null),
            fg: kTier3,
            bg: kTier3Bg,
            dark: dark,
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
      ],
    );
  }
}

class _EscalationTier extends StatelessWidget {
  const _EscalationTier({
    required this.title,
    required this.body,
    required this.fg,
    required this.bg,
    required this.dark,
  });
  final String title;
  final List<String> body;
  final Color fg;
  final Color bg;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? fg.withValues(alpha: 0.18) : bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: fg.withValues(alpha: dark ? 0.45 : 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: fg)),
          const SizedBox(height: 8),
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

/// Recovery tab — activity/dietary restrictions + discharge condition + timeline.
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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (hasRestrictions) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: _RestrictionColumn(
                    label: 'Activity',
                    items: activity,
                    dark: dark,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _RestrictionColumn(
                    label: 'Diet',
                    items: dietary,
                    dark: dark,
                  ),
                ),
              ],
            ),
            if (condition.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: dark ? kTeal.withValues(alpha: 0.15) : kTealPale,
                  borderRadius: BorderRadius.circular(8),
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
          Text(
            trajectory.isEmpty ? 'No recovery timeline available.' : trajectory,
            style: TextStyle(
              fontSize: 14,
              height: 1.6,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
        ],
      ),
    );
  }
}

class _RestrictionColumn extends StatelessWidget {
  const _RestrictionColumn({required this.label, required this.items, required this.dark});
  final String label;
  final List<String> items;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: dark ? kBorderDark : kBorderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: dark ? kTealGlow : kTeal,
            ),
          ),
          const SizedBox(height: 6),
          if (items.isEmpty)
            Text(
              'None listed.',
              style: TextStyle(
                fontSize: 12,
                color: dark ? kTextHintDark : kTextHintLight,
              ),
            )
          else
            ...items.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 6, right: 6),
                      child: Container(
                        width: 5,
                        height: 5,
                        decoration: BoxDecoration(
                          color: dark ? kTealGlow : kTeal,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        item,
                        style: TextStyle(
                          fontSize: 12,
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
        borderRadius: BorderRadius.circular(8),
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

class _AppointmentsBody extends StatelessWidget {
  const _AppointmentsBody({required this.extraction});

  final dynamic extraction;

  @override
  Widget build(BuildContext context) {
    final list = (extraction is Map) ? extraction['follow_up_appointments'] as List? : null;
    if (list == null || list.isEmpty) {
      return const _RichTextSection(text: 'No follow-up appointments listed in this document.');
    }
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: list.length,
      itemBuilder: (context, i) {
        final a = list[i];
        if (a is! Map) return const SizedBox.shrink();
        return Card(
          color: dark ? kCardDark : kCardLight,
          child: ListTile(
            title: Text('${a['specialty'] ?? a['provider'] ?? 'Appointment'}'),
            subtitle: Text(
              '${a['date'] ?? 'Date TBD'}\n${a['reason'] ?? ''}',
              style: TextStyle(color: dark ? kTextSecondaryDark : kTextSecondaryLight),
            ),
            trailing: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                '${a['date'] ?? 'TBD'}',
                style: TextStyle(
                  fontSize: 11,
                  color: dark ? kTealGlow : kTeal,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
