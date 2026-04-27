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
      body: TabBarView(
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
            child: _RichTextSection(text: _dischargeCheckText(r)),
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

String _dischargeCheckText(Map<String, dynamic> data) {
  final sim = data['patient_simulator'];
  if (sim is! Map) {
    return 'Discharge quality check is not available for this analysis run.';
  }
  final summary = '${sim['simulator_summary'] ?? ''}';
  final missed = sim['missed_concepts'];
  final buf = StringBuffer(summary);
  if (missed is List && missed.isNotEmpty) {
    buf.writeln('\n\nGaps flagged:\n');
    for (final m in missed) {
      if (m is Map) {
        buf.writeln('• ${m['gap_summary'] ?? m['question'] ?? ''}');
      }
    }
  }
  return buf.toString();
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
