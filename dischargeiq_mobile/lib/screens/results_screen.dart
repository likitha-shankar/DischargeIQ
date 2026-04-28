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
                  child: _RichTextSection(text: '${r['diagnosis_explanation'] ?? ''}'),
                ),
                KeyedSubtree(
                  key: TourKeys.medications,
                  child: _MedicationsBody(text: '${r['medication_rationale'] ?? ''}'),
                ),
                KeyedSubtree(
                  key: TourKeys.appointments,
                  child: _AppointmentsBody(extraction: r['extraction']),
                ),
                KeyedSubtree(
                  key: TourKeys.warnings,
                  child: _WarningsBody(text: '${r['escalation_guide'] ?? ''}'),
                ),
                _RichTextSection(text: '${r['recovery_trajectory'] ?? ''}'),
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

class _MedicationsBody extends StatelessWidget {
  const _MedicationsBody({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final chunks = text
        .split(RegExp(r'\n\s*\n'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: chunks.length,
      itemBuilder: (context, i) {
        final lines = chunks[i].split('\n');
        final title = lines.isNotEmpty ? lines.first.replaceAll(':', '').trim() : 'Medication';
        final body = lines.length > 1 ? lines.sublist(1).join('\n').trim() : chunks[i];
        return Card(
          color: dark ? kCardDark : kCardLight,
          margin: const EdgeInsets.only(bottom: 10),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(body, style: TextStyle(color: dark ? kTextSecondaryDark : kTextSecondaryLight)),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _WarningsBody extends StatelessWidget {
  const _WarningsBody({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final src = text.toUpperCase();
    final t1 = _extractTier(text, 'CALL 911 IMMEDIATELY', 'GO TO THE ER TODAY');
    final t2 = _extractTier(text, 'GO TO THE ER TODAY', 'CALL YOUR DOCTOR');
    final t3 = _extractTier(text, 'CALL YOUR DOCTOR', null);

    Widget tier(String title, String body, Color fg, Color bg) {
      return Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: dark ? fg.withValues(alpha: 0.18) : bg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: fg.withValues(alpha: dark ? 0.45 : 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: fg)),
            const SizedBox(height: 6),
            Text(body.trim(), style: TextStyle(color: dark ? kTextPrimaryDark : kTextPrimaryLight)),
          ],
        ),
      );
    }

    if (!src.contains('CALL 911') && !src.contains('ER') && !src.contains('CALL YOUR DOCTOR')) {
      return _RichTextSection(text: text);
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        tier('CALL 911 IMMEDIATELY', t1, kTier1, kTier1Bg),
        tier('GO TO THE ER TODAY', t2, kTier2, kTier2Bg),
        tier('CALL YOUR DOCTOR', t3, kTier3, kTier3Bg),
      ],
    );
  }
}

String _extractTier(String text, String start, String? next) {
  final up = text.toUpperCase();
  final s = up.indexOf(start.toUpperCase());
  if (s < 0) return '';
  final end = next == null ? text.length : up.indexOf(next.toUpperCase(), s + start.length);
  if (end < 0) return text.substring(s + start.length).trim();
  return text.substring(s + start.length, end).trim();
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
