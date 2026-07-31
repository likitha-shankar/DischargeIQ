import 'dart:math' show max, min;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusCard, kRadiusField;
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/calendar_link.dart';
import 'package:dischargeiq_mobile/services/document_store.dart' show isUnusableRun;
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/read_aloud.dart';
import 'package:dischargeiq_mobile/services/share_summary.dart';
import 'package:dischargeiq_mobile/services/recovery_timeline.dart';
import 'package:dischargeiq_mobile/screens/medication_reminders_screen.dart';
import 'package:dischargeiq_mobile/screens/original_document_screen.dart';
import 'package:dischargeiq_mobile/screens/quiz_screen.dart';
import 'package:dischargeiq_mobile/screens/scan_screen.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';
import 'package:dischargeiq_mobile/widgets/audio_explainer.dart';
import 'package:dischargeiq_mobile/widgets/chat_sheet.dart';
import 'package:dischargeiq_mobile/widgets/guided_tour.dart';
import 'package:dischargeiq_mobile/widgets/source_quote.dart';
import 'package:dischargeiq_mobile/widgets/empty_section.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

part 'results_text_widgets.dart';
part 'results_check_body.dart';
part 'results_dx_meds_body.dart';
part 'results_warnings_body.dart';
part 'results_recovery_body.dart';
part 'results_appointments_body.dart';


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
    final provider = context.read<DischargeProvider>();
    // No stars on a rejected document - there is nothing to read.
    if ('${provider.result?['pipeline_status']}' == 'rejected') return;
    // Stars are per-document; an unsaved run (dead/unusable) has no id and
    // earns nothing - there is no journey entry it could ever light up.
    final docId = provider.activeDocId;
    if (docId == null) return;
    final key = kSectionStarKeys[tabIndex];
    final isNew = await SectionStarStore.award(docId, key);
    if (!isNew || !mounted) return;
    final earned = (await SectionStarStore.load(docId)).length;
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
      // Flat themed app bar (2026 revamp): the pill tab capsules need the
      // light surface behind them, not the old solid-teal band.
      appBar: AppBar(
        title: const Text('DischargeIQ'),
        // Home: back to the landing page. Safe - the analysis is already in
        // the on-device library, so nothing is lost.
        leading: IconButton(
          tooltip: 'Home',
          icon: const Icon(Icons.home_outlined),
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
              icon: const Icon(Icons.article_outlined),
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
              ),
              onPressed: () => _toggleReadAloud(r),
            ),
          // Caregiver share (P-1): the patient composes and chooses the
          // recipient in the native share sheet - nothing auto-sends.
          IconButton(
            tooltip: 'Share with a family member',
            icon: const Icon(Icons.ios_share),
            onPressed: () => Share.share(buildCaregiverSummary(r)),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
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
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            key: TourKeys.tabBar,
            padding: const EdgeInsets.fromLTRB(12, 2, 12, 8),
            // Pill capsule tabs from the app theme (2026 revamp) - the
            // active section is a filled teal pill, no underline, no band.
            child: TabBar(
              controller: _tabController,
              isScrollable: true,
              tabAlignment: TabAlignment.start,
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
                  child: _AppointmentsBody(
                    extraction: r['extraction'],
                    simulator: r['patient_simulator'],
                  ),
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

/// "Bring these questions to your visit" - Agent 6's unanswered concepts,
/// severity-ranked, shareable. The AI found the gaps; the patient's care
/// team answers them (HITL framing, never a diagnosis).
class _VisitPrepCard extends StatelessWidget {
  const _VisitPrepCard({required this.questions, required this.dark});

  final List<String> questions;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kSurfaceLight,
        borderRadius: BorderRadius.circular(kRadiusCard),
        border: Border.all(color: dark ? kBorderDark : kBorderLight, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.help_outline, size: 18, color: dark ? kTealGlow : kTeal),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Good questions for your next visit',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Share these questions',
                visualDensity: VisualDensity.compact,
                icon: Icon(Icons.ios_share, size: 17, color: dark ? kTealGlow : kTeal),
                onPressed: () => Share.share(
                  'Questions for my next appointment:\n'
                  '${[for (final q in questions) '- $q'].join('\n')}\n\n'
                  '(From DischargeIQ - things my discharge papers did not cover.)',
                ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Text(
            'Your discharge papers did not answer these. Your care team can.',
            style: TextStyle(
              fontSize: 11.5,
              color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            ),
          ),
          const SizedBox(height: 8),
          for (final q in questions)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.chat_bubble_outline,
                      size: 14, color: dark ? kTealGlow : kTeal),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      q,
                      style: TextStyle(
                        fontSize: 13.5,
                        height: 1.4,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
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


/// Shared tab hero (2026 revamp): every section opens with an icon squircle,
/// a big title, and a one-line purpose - the patient always knows what the
/// tab is FOR before reading it. Tinted with the section's accent color;
/// safety tabs pass their own semantic tint (never decorative).
class _SectionHero extends StatelessWidget {
  const _SectionHero({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.tint,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  /// Accent for the icon chip; defaults to the app teal.
  final Color? tint;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = tint ?? (dark ? kTealGlow : kTeal);
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: dark ? 0.22 : 0.14),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(icon, size: 27, color: accent),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 12.5,
                    height: 1.3,
                    color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
