import 'dart:math' show max, min;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/calendar_link.dart';
import 'package:dischargeiq_mobile/services/document_store.dart' show isUnusableRun;
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/read_aloud.dart';
import 'package:dischargeiq_mobile/screens/original_document_screen.dart';
import 'package:dischargeiq_mobile/screens/quiz_screen.dart';
import 'package:dischargeiq_mobile/screens/scan_screen.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';
import 'package:dischargeiq_mobile/widgets/audio_explainer.dart';
import 'package:dischargeiq_mobile/widgets/chat_sheet.dart';
import 'package:dischargeiq_mobile/widgets/guided_tour.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

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
    'Test yourself',
    'Discharge Check',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabLabels.length, vsync: this);
    // Discharge-process stars (Task 2.2): viewing a content tab earns its
    // star once, ever. Listener fires on settled tab changes; the initial
    // tab (What happened) is awarded after the first frame.
    _tabController.addListener(_onTabSettled);
    _loadReadAloudPref();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _maybeStartTour();
      _awardSectionStar(0);
    });
  }

  void _onTabSettled() {
    if (!_tabController.indexIsChanging) {
      // Stop speech when the tab changes - reading the OLD tab's text over
      // the new tab's content would be disorienting.
      if (_speaking) {
        ReadAloud.stop();
        setState(() => _speaking = false);
      }
      _awardSectionStar(_tabController.index);
    }
  }

  Future<void> _awardSectionStar(int tabIndex) async {
    // Only the five content sections carry stars; quiz and AI review do not.
    if (tabIndex < 0 || tabIndex >= kSectionStarKeys.length || !mounted) return;
    // No stars on a rejected document - there is nothing to read.
    if ('${context.read<DischargeProvider>().result?['pipeline_status']}' ==
        'rejected') {
      return;
    }
    final key = kSectionStarKeys[tabIndex];
    final isNew = await SectionStarStore.award(key);
    if (!isNew || !mounted) return;
    final earned = (await SectionStarStore.load()).length;
    if (!mounted) return;
    // Quiet, once-per-star feedback - a snackbar, never confetti
    // (calm-celebration rule in docs/GAMIFICATION_STRATEGY.md).
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
        content: Text(
          '⭐ Star earned: ${kSectionStarLabels[key]} read '
          '($earned of ${kAllStarKeys.length})',
        ),
      ),
    );
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
    // No tour on a rejected document - the tab bar it points at isn't there.
    if (!mounted ||
        '${context.read<DischargeProvider>().result?['pipeline_status']}' ==
            'rejected') {
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    final done = prefs.getBool('tour_completed') ?? false;
    if (!done && mounted) {
      await _startTour();
    }
  }

  // Read-aloud (accessibility): speaker button reads the CURRENT tab.
  bool _speaking = false;
  bool _readAloudEnabled = true;

  Future<void> _loadReadAloudPref() async {
    final enabled = await ReadAloud.enabled();
    if (mounted) setState(() => _readAloudEnabled = enabled);
  }

  /// Plain text of the currently visible tab, for text-to-speech.
  String _currentTabText(Map<String, dynamic> r) {
    final ex = r['extraction'];
    switch (_tabController.index) {
      case 0:
        return 'What happened. ${r['diagnosis_explanation'] ?? ''}';
      case 1:
        return 'Your medications. ${r['medication_rationale'] ?? ''}';
      case 2:
        final appts = (ex is Map) ? ex['follow_up_appointments'] as List? : null;
        if (appts == null || appts.isEmpty) {
          return 'No follow-up appointments were listed in this document.';
        }
        return 'Your appointments. ${[
          for (final a in appts.whereType<Map>())
            '${a['specialty'] ?? a['provider'] ?? 'Appointment'}, '
                '${a['date'] ?? 'date to be decided'}. ${a['reason'] ?? ''}'
        ].join(' Next: ')}';
      case 3:
        return 'Warning signs. ${r['escalation_guide'] ?? ''}';
      case 4:
        return 'Your recovery. ${r['recovery_trajectory'] ?? ''}';
      default:
        return 'This tab is interactive. Please use the screen for it.';
    }
  }

  Future<void> _toggleReadAloud(Map<String, dynamic> r) async {
    if (_speaking) {
      await ReadAloud.stop();
      if (mounted) setState(() => _speaking = false);
      return;
    }
    ReadAloud.onDone = () {
      if (mounted) setState(() => _speaking = false);
    };
    setState(() => _speaking = true);
    await ReadAloud.speak(_currentTabText(r));
  }

  @override
  void dispose() {
    ReadAloud.onDone = null;
    ReadAloud.stop();
    _tabController.removeListener(_onTabSettled);
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

    // Router gate: not a discharge document → dedicated screen. Rendering the
    // tabs would show seven empty sections plus an ungrounded chat and quiz.
    if ('${r['pipeline_status']}' == 'rejected') {
      return _RejectedDocumentScreen(
        reason: '${r['rejection_reason'] ?? 'This does not look like a hospital discharge document.'}',
      );
    }

    // Dead-run gate: a partial where nothing usable came back (extraction
    // failed or every section empty - typically exhausted model quota).
    // Seven hollow tabs with "Extraction failed" as a diagnosis reads as a
    // broken app; a single honest try-again screen does not.
    if (isUnusableRun(r)) {
      return const _AnalysisFailedScreen();
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
        // Home: back to the landing page. Safe - the analysis is already in
        // the on-device library, so nothing is lost.
        leading: IconButton(
          tooltip: 'Home',
          icon: const Icon(Icons.home_outlined, color: Colors.white),
          onPressed: () => context.read<DischargeProvider>().clear(),
        ),
        actions: [
          // "View original": the exact document this analysis was built
          // from - PDF bytes or scanned page photos. Hidden when neither
          // survives (e.g. a scan session reopened from the library).
          Builder(builder: (context) {
            final dp2 = context.watch<DischargeProvider>();
            final hasPhotos =
                dp2.isScanSession && dp2.scanPages.isNotEmpty;
            final hasPdf = dp2.lastPdfBytes != null;
            if (!hasPhotos && !hasPdf) return const SizedBox.shrink();
            return IconButton(
              tooltip: 'View your original document',
              icon: const Icon(Icons.article_outlined, color: Colors.white),
              onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute<void>(
                  builder: (_) => hasPhotos
                      ? OriginalPhotosScreen(
                          imagePaths: [
                            for (final p in dp2.scanPages) p.imagePath
                          ],
                        )
                      : OriginalPdfScreen(
                          pdfBytes: dp2.lastPdfBytes!,
                          fileName: dp2.lastFileName,
                        ),
                ),
              ),
            );
          }),
          if (_readAloudEnabled)
            IconButton(
              tooltip: _speaking ? 'Stop reading' : 'Read this section aloud',
              icon: Icon(
                _speaking ? Icons.stop_circle_outlined : Icons.volume_up_outlined,
                color: Colors.white,
              ),
              onPressed: () => _toggleReadAloud(r),
            ),
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
              // Settings may have flipped the read-aloud toggle.
              _loadReadAloudPref();
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
          // Scan sessions: patients often photograph only page 1 of a
          // multi-page packet. One tap returns to the scan screen with all
          // captured pages intact to add the rest and re-analyze.
          if (dp.isScanSession) _AddPagesRow(pageCount: dp.scanPages.length),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                KeyedSubtree(
                  key: TourKeys.diagnosis,
                  child: _DiagnosisBody(
                    explanation: '${r['diagnosis_explanation'] ?? ''}',
                    extraction: r['extraction'],
                    documentType: '${r['document_type'] ?? ''}',
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
                // Teach-back quiz (Sprint 3) - the comprehension-lift loop.
                // Session id reuses the backend's pdf_session_id so quiz
                // scores join up with the analyze session in Neon.
                QuizBody(
                  result: r,
                  sessionId: '${r['pdf_session_id'] ?? DateTime.now().millisecondsSinceEpoch}',
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
        onPressed: () => showChatSheet(context, r),
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.chat_bubble_outline),
        label: const Text('Ask'),
      ),
    );
  }
}

/// Full-screen notice for a run where analysis could not produce anything
/// usable. Honest, jargon-free, one action. Never mentions API keys.
class _AnalysisFailedScreen extends StatelessWidget {
  const _AnalysisFailedScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.cloud_off_outlined, size: 60, color: kTier2),
                const SizedBox(height: 16),
                Text(
                  "We couldn't read your document right now",
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                Text(
                  'Our reading service is very busy at the moment. Nothing is '
                  'wrong with your document, and nothing was lost.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5),
                ),
                const SizedBox(height: 10),
                Text(
                  'Please try again in a few minutes. If it keeps happening, '
                  'try later today - your paper document always has the '
                  'complete instructions.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      height: 1.5,
                      color: Theme.of(context).textTheme.bodySmall?.color),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: kTeal,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 26, vertical: 14)),
                  onPressed: () =>
                      context.read<DischargeProvider>().clear(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


/// Full-screen notice for a document the router rejected (bill, EOB, random
/// PDF). One action: go back and try another document.
class _RejectedDocumentScreen extends StatelessWidget {
  const _RejectedDocumentScreen({required this.reason});

  final String reason;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.description_outlined, size: 60, color: kTier2),
                const SizedBox(height: 16),
                Text(
                  "This doesn't look like a discharge document",
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                Text(reason,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5)),
                const SizedBox(height: 10),
                Text(
                  'DischargeIQ works with the discharge summary your hospital '
                  'gave you when you went home - it usually lists your '
                  'diagnosis, medications, and follow-up appointments.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(height: 1.5, color: Theme.of(context).textTheme.bodySmall?.color),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: kTeal,
                      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 14)),
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.upload_file_outlined),
                  label: const Text('Try another document'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// One-tap path back to the scan screen for multi-page documents. Shown only
/// on camera-scan sessions; the provider keeps the captured pages alive, so
/// nothing has to be re-photographed.
class _AddPagesRow extends StatelessWidget {
  const _AddPagesRow({required this.pageCount});

  final int pageCount;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Material(
      color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
      child: InkWell(
        onTap: () => Navigator.push<void>(
          context,
          MaterialPageRoute<void>(builder: (_) => const ScanScreen()),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          child: Row(
            children: [
              Icon(Icons.add_a_photo_outlined,
                  size: 16, color: dark ? kTealGlow : kTeal),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  pageCount > 0
                      ? 'Built from $pageCount scanned page${pageCount == 1 ? '' : 's'}. '
                          'Missing some? Add the rest.'
                      : 'Did your document have more pages? Add the rest.',
                  style: TextStyle(
                      fontSize: 12, color: dark ? kTealGlow : kTeal),
                ),
              ),
              Icon(Icons.chevron_right,
                  size: 16, color: dark ? kTealGlow : kTeal),
            ],
          ),
        ),
      ),
    );
  }
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
        ? 'Some sections are missing - our reading service was busy. '
            'Upload again in a few minutes to fill them in.'
        : 'Ready, with a note: a few details were not found in your document.';
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
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: PatientText(text: text),
    );
  }
}

/// Renders agent text the way a patient should see it, not the way the model
/// wrote it: `**bold**` becomes bold, `- ` / `* ` lines become real bullets,
/// raw markdown symbols never reach the screen. Deliberately tiny - the
/// agents only ever emit bold and bullets, so a markdown package would be
/// dead weight.
class PatientText extends StatelessWidget {
  const PatientText({super.key, required this.text, this.fontSize = 15});

  final String text;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final base = TextStyle(
      fontSize: fontSize,
      height: 1.5,
      color: dark ? kTextPrimaryDark : kTextPrimaryLight,
    );
    final children = <Widget>[];
    for (final rawLine in text.split('\n')) {
      final line = rawLine.trimRight();
      if (line.trim().isEmpty) {
        children.add(const SizedBox(height: 8));
        continue;
      }
      final bullet = RegExp(r'^\s*[-*•]\s+').firstMatch(line);
      if (bullet != null) {
        children.add(Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 5),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: EdgeInsets.only(top: fontSize * 0.42),
                child: Container(
                  width: 5.5,
                  height: 5.5,
                  decoration: BoxDecoration(
                    color: dark ? kTealGlow : kTeal,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Text.rich(
                  TextSpan(children: _boldSpans(line.substring(bullet.end), base)),
                ),
              ),
            ],
          ),
        ));
      } else {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text.rich(TextSpan(children: _boldSpans(line, base))),
        ));
      }
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  /// Split `a **b** c` into styled spans; unmatched `**` renders literally.
  static List<InlineSpan> _boldSpans(String line, TextStyle base) {
    final spans = <InlineSpan>[];
    final parts = line.split('**');
    if (parts.length.isEven) {
      // Unbalanced markers - show the line untouched rather than guessing.
      return [TextSpan(text: line, style: base)];
    }
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].isEmpty) continue;
      spans.add(TextSpan(
        text: parts[i],
        style: i.isOdd
            ? base.copyWith(fontWeight: FontWeight.w700)
            : base,
      ));
    }
    return spans;
  }
}

/// Rich Discharge Check / AI Review tab - mirrors the Streamlit web UI.
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

/// Diagnosis tab - "At a glance" badges + Agent 2 explanation text.
class _DiagnosisBody extends StatelessWidget {
  const _DiagnosisBody({
    required this.explanation,
    required this.extraction,
    this.documentType = '',
  });
  final String explanation;
  final dynamic extraction;

  /// Router classification - drives the per-diagnosis audio explainer.
  final String documentType;

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
          if (documentType.isNotEmpty && documentType != 'unknown')
            AudioExplainerCard(documentType: documentType),
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

/// Warning Signs tab - red-flag bullet list + 3-tier escalation cards with bullets.
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

/// Recovery tab - activity/dietary restrictions + discharge condition + timeline.
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
          trajectory.isEmpty
              ? Text(
                  'No recovery timeline available.',
                  style: TextStyle(
                    fontSize: 14,
                    height: 1.6,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                )
              : PatientText(text: trajectory, fontSize: 14),
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

  /// Task 2.2 calendar action: open the Google Calendar event template for
  /// this appointment, then award the one-time calendar star. The star is
  /// earned for taking the action; whether the patient saves the event in
  /// Google Calendar afterwards is unknowable from here.
  Future<void> _addToCalendar(BuildContext context, Map appointment) async {
    final url = buildCalendarLink(
      provider: appointment['provider'] as String?,
      specialty: appointment['specialty'] as String?,
      reason: appointment['reason'] as String?,
      dateText: appointment['date'] as String?,
    );
    final opened = await launchUrl(url, mode: LaunchMode.externalApplication);
    if (!opened || !context.mounted) return;
    final isNew = await SectionStarStore.award(kCalendarStarKey);
    if (!isNew || !context.mounted) return;
    final earned = (await SectionStarStore.load()).length;
    if (!context.mounted) return;
    // Same quiet once-per-star feedback as the reading stars
    // (calm-celebration rule in docs/GAMIFICATION_STRATEGY.md).
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
        content: Text(
          '⭐ Star earned: ${kSectionStarLabels[kCalendarStarKey]} '
          '($earned of ${kAllStarKeys.length})',
        ),
      ),
    );
  }

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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ListTile(
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
              Padding(
                padding: const EdgeInsets.only(left: 8, right: 8, bottom: 6),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => _addToCalendar(context, a),
                    icon: const Icon(Icons.calendar_month_outlined, size: 18),
                    label: const Text('Add to calendar'),
                    style: TextButton.styleFrom(
                      foregroundColor: dark ? kTealGlow : kTeal,
                      // 48dp touch target, same rule as the audio play button.
                      minimumSize: const Size(48, 48),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
