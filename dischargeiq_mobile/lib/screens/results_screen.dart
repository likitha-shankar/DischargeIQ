import 'dart:math' show max, min;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/section_design.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusCard, kRadiusField;
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/appointment_status.dart';
import 'package:dischargeiq_mobile/services/calendar_link.dart';
import 'package:dischargeiq_mobile/services/document_store.dart' show isUnusableRun;
import 'package:dischargeiq_mobile/services/escalation_tiers.dart';
import 'package:dischargeiq_mobile/services/case_audio_player.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/health_log.dart';
import 'package:dischargeiq_mobile/services/learning_goals.dart';
import 'package:dischargeiq_mobile/services/read_aloud.dart';
import 'package:dischargeiq_mobile/services/share_summary.dart';
import 'package:dischargeiq_mobile/services/recovery_timeline.dart';
import 'package:dischargeiq_mobile/screens/medication_reminders_screen.dart';
import 'package:dischargeiq_mobile/screens/original_document_screen.dart';
import 'package:dischargeiq_mobile/screens/quiz_screen.dart';
import 'package:dischargeiq_mobile/screens/scan_screen.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';
import 'package:dischargeiq_mobile/widgets/ai_disclaimer_dialog.dart';
import 'package:dischargeiq_mobile/services/recovery_notes.dart';
import 'package:dischargeiq_mobile/widgets/audio_explainer.dart';
import 'package:dischargeiq_mobile/widgets/chat_sheet.dart';
import 'package:dischargeiq_mobile/widgets/recovery_edit_sheet.dart';
import 'package:dischargeiq_mobile/widgets/guided_tour.dart';
import 'package:dischargeiq_mobile/widgets/learning_goal_sheet.dart';
import 'package:dischargeiq_mobile/widgets/run_state_screens.dart';
import 'package:dischargeiq_mobile/widgets/source_quote.dart';
import 'package:dischargeiq_mobile/widgets/capped_list.dart';
import 'package:dischargeiq_mobile/widgets/empty_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show MissingPluginException, PlatformException;
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

part 'results_text_widgets.dart';
part 'results_check_body.dart';
part 'results_dx_meds_body.dart';
part 'results_warnings_body.dart';
part 'results_recovery_body.dart';
part 'results_weight_card.dart';
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
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _maybeStartTour();
      // The usage disclaimer gates everything after the tour: a patient
      // should not be reading AI-written medical text before being told
      // that is what it is. Blocking, and acknowledged per document.
      await _maybeShowDisclaimer();
      // Goals are asked after the tour, and before the first star lands, so
      // the patient chooses what matters before the app starts rewarding.
      await _maybeAskLearningGoals();
      await _awardSectionStar(0);
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
    // Awaited: the tour owns the screen until it closes, and whatever comes
    // next must not open on top of it.
    await showGuidedTourOverlay(
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

  /// Ask what the patient wants to learn, once per document.
  ///
  /// Clinical review, Aug 2026: the reward layer should follow what the
  /// patient said matters, not a fixed reading order. Chosen goals reorder
  /// the quests and the coach, and the before/after self-rating is the
  /// outcome the feature is measured by.
  ///
  /// Runs after the tour so two overlays never fight for the screen, and
  /// never on a rejected document - there is nothing to set goals about.
  /// Show the AI usage disclaimer once per document.
  ///
  /// Skipped for a rejected document: there is no analysis to qualify, and
  /// that screen already says the app could not use the upload.
  Future<void> _maybeShowDisclaimer() async {
    if (!mounted) return;
    final provider = context.read<DischargeProvider>();
    if ('${provider.result?['pipeline_status']}' == 'rejected') return;
    final docId = provider.activeDocId;
    // An unsaved run has no id to remember an acknowledgement against, so it
    // shows every time rather than silently skipping the notice.
    if (docId != null && await wasDisclaimerAcknowledged(docId)) return;
    if (!mounted) return;
    await showAiDisclaimer(context, docId: docId);
  }

  Future<void> _maybeAskLearningGoals() async {
    if (!mounted) return;
    final provider = context.read<DischargeProvider>();
    if ('${provider.result?['pipeline_status']}' == 'rejected') return;
    // An unsaved run has no id, so goals would have nowhere to live.
    final docId = provider.activeDocId;
    if (docId == null) return;
    if (await LearningGoalStore.wasAsked(docId) || !mounted) return;
    await showLearningGoalSheet(context: context, docId: docId);
  }

  /// Reopen the goal picker on demand, from the flag button in the app bar.
  ///
  /// Unlike [_maybeAskLearningGoals] this ignores the "already asked" flag -
  /// the patient asked for it this time.
  Future<void> _editLearningGoals() async {
    final provider = context.read<DischargeProvider>();
    final docId = provider.activeDocId;
    if (docId == null) {
      // An unsaved run has nowhere to store goals; say so rather than opening
      // a picker whose answer would silently vanish.
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Save this analysis first, then you can choose what to '
            'focus on.'),
      ));
      return;
    }
    await showLearningGoalSheet(context: context, docId: docId);
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

  /// Jump to a tab the patient asked for by voice and read it out loud.
  ///
  /// Called by the chat sheet after it closes itself, so the content is on
  /// screen while it is spoken. A short delay lets the sheet finish
  /// dismissing and the tab settle before speech starts - otherwise the first
  /// words land while the screen is still animating.
  Future<void> _readTabAloud(Map<String, dynamic> r, int tabIndex) async {
    if (!mounted || tabIndex < 0 || tabIndex >= _tabLabels.length) return;
    await ReadAloud.stop();
    if (!mounted) return;
    _tabController.animateTo(tabIndex);
    await Future<void>.delayed(const Duration(milliseconds: 350));
    if (!mounted || _speaking) return;
    ReadAloud.onDone = () {
      if (mounted) setState(() => _speaking = false);
    };
    setState(() => _speaking = true);
    await ReadAloud.speak(_currentTabText(r));
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
      return RejectedDocumentScreen(
        reason: '${r['rejection_reason'] ?? 'This does not look like a hospital discharge document.'}',
      );
    }

    // Dead-run gate: a partial where nothing usable came back (extraction
    // failed or every section empty - typically exhausted model quota).
    // Seven hollow tabs with "Extraction failed" as a diagnosis reads as a
    // broken app; a single honest try-again screen does not.
    if (isUnusableRun(r)) {
      return const AnalysisFailedScreen();
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
          // Learning goals stay changeable: the picker only appears
          // automatically on the first open, and a patient who skipped it -
          // or whose priorities changed after reading - had no way back to it.
          // Labelled, not a bare flag. A tooltip only appears on a long
          // press on iOS, so an icon-only action in a six-action bar is
          // undiscoverable - nobody guesses that a flag means "choose what
          // you want to understand". The word is what makes it findable.
          TextButton.icon(
            onPressed: _editLearningGoals,
            icon: const Icon(Icons.flag_outlined, size: 19),
            label: const Text('Goals'),
            style: TextButton.styleFrom(
              visualDensity: VisualDensity.compact,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              foregroundColor: Theme.of(context).appBarTheme.foregroundColor ??
                  Theme.of(context).colorScheme.onSurface,
            ),
          ),
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
          // Pinned under the tabs: an explainer started on What happened can
          // be paused from Medications, which is where a patient listening
          // to it is most likely to be looking.
          const _AudioNowPlayingBar(),
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
                    // The whole result drives the per-case audio explainer:
                    // it narrates THIS document, so it needs the payload the
                    // client already holds rather than a re-fetch.
                    result: r,
                    sessionId: '${r['pdf_session_id'] ?? ''}',
                    // The closing card hands the patient the next question
                    // rather than leaving them to find the tab strip.
                    onNext: () => _tabController.animateTo(1),
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
      // Icon-only companion button: the chat does more than "Ask" now (it
      // listens, answers aloud, and opens sections), so a single verb label
      // undersold it. Tooltip and semantics keep it accessible.
      floatingActionButton: FloatingActionButton(
        key: TourKeys.chat,
        onPressed: () async {
          // The sheet returns a tab index when the patient asked for a
          // section to be read aloud. Acting AFTER the route closes means
          // the content is on screen before speech starts.
          final tabIndex = await showChatSheet(context, r);
          if (tabIndex != null) await _readTabAloud(r, tabIndex);
        },
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        tooltip: 'Ask about your summary, or have it read aloud',
        child: const Icon(Icons.forum_outlined, size: 26),
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

/// Playback control for the case explainer, visible on every tab.
///
/// Shown whenever a track is loaded, playing or paused, so a patient who
/// pauses to read something can resume without hunting for the card that
/// started it. Hidden entirely when nothing is queued.
class _AudioNowPlayingBar extends StatelessWidget {
  const _AudioNowPlayingBar();

  @override
  Widget build(BuildContext context) {
    final audio = context.watch<CaseAudioPlayer>();
    if (!audio.hasTrack) return const SizedBox.shrink();
    final dark = Theme.of(context).brightness == Brightness.dark;

    String clock(Duration d) =>
        '${d.inMinutes}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';

    return Container(
      color: dark ? kTeal.withValues(alpha: 0.22) : kTealPale,
      padding: const EdgeInsets.fromLTRB(12, 6, 6, 6),
      child: Row(
        children: [
          IconButton(
            tooltip: 'Back 15 seconds',
            visualDensity: VisualDensity.compact,
            onPressed: () => audio.skip(const Duration(seconds: -15)),
            icon: Icon(Icons.replay_10_rounded,
                size: 20, color: dark ? kTealGlow : kTeal),
          ),
          IconButton(
            tooltip: audio.isPlaying ? 'Pause' : 'Play',
            visualDensity: VisualDensity.compact,
            onPressed: () => audio.isPlaying
                ? audio.pause()
                : audio.play(audio.url!, label: audio.label),
            icon: Icon(
              audio.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: dark ? kTealGlow : kTeal,
            ),
          ),
          IconButton(
            tooltip: 'Forward 15 seconds',
            visualDensity: VisualDensity.compact,
            onPressed: () => audio.skip(const Duration(seconds: 15)),
            icon: Icon(Icons.forward_10_rounded,
                size: 20, color: dark ? kTealGlow : kTeal),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  audio.label.isEmpty ? 'Audio explainer' : audio.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                ),
                const SizedBox(height: 3),
                LinearProgressIndicator(
                  value: audio.progress,
                  minHeight: 3,
                  backgroundColor:
                      (dark ? kTealGlow : kTeal).withValues(alpha: 0.2),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          if (audio.duration > Duration.zero)
            Text(
              '${clock(audio.position)} / ${clock(audio.duration)}',
              style: TextStyle(
                fontSize: 11,
                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
              ),
            ),
          IconButton(
            tooltip: 'Stop',
            visualDensity: VisualDensity.compact,
            onPressed: audio.stop,
            icon: Icon(Icons.close,
                size: 18, color: dark ? kTextSecondaryDark : kTextSecondaryLight),
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
/// tab is FOR before reading it. Tinted with the app accent; the three
/// redesigned sections open with a SectionEyebrow instead and do not use it.
class _SectionHero extends StatelessWidget {
  const _SectionHero({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = dark ? kTealGlow : kTeal;
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
