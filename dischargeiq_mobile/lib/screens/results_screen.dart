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
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
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
          // Caregiver share (P-1): the patient composes and chooses the
          // recipient in the native share sheet - nothing auto-sends.
          IconButton(
            tooltip: 'Share with a family member',
            icon: const Icon(Icons.ios_share, color: Colors.white),
            onPressed: () => Share.share(buildCaregiverSummary(r)),
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

class _RichTextSection extends StatelessWidget {
  const _RichTextSection({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 110),
      child: PatientText(text: text),
    );
  }
}

/// Renders agent text the way a patient should see it, not the way the model
/// wrote it: `# / ##` lines become styled section headings, `**bold**`
/// becomes bold, `- ` / `* ` lines become real bullets, and stray markdown
/// symbols never reach the screen. Deliberately tiny - the agents only ever
/// emit headings, bold, and bullets, so a markdown package would be dead
/// weight.
class PatientText extends StatelessWidget {
  const PatientText({
    super.key,
    required this.text,
    this.fontSize = 14.5,
    this.collapsible = false,
  });

  final String text;
  final double fontSize;

  /// When true and the text has 2+ headed sections, only the first section
  /// shows expanded; the rest collapse behind their headings (progressive
  /// disclosure for tired patients). NEVER set on safety-critical text -
  /// the escalation guide must stay fully visible.
  final bool collapsible;

  /// One parsed line: a heading (with level) or a body/bullet line.
  static ({int? headingLevel, String text, bool isBullet}) _parseLine(String rawLine) {
    final line = rawLine.trimRight();
    final heading = RegExp(r'^\s*(#{1,6})\s+(.*)$').firstMatch(line);
    if (heading != null) {
      return (
        headingLevel: heading.group(1)!.length,
        text: heading.group(2)!.replaceAll('*', '').trim(),
        isBullet: false,
      );
    }
    // Heading-intent lines the model wrapped in stray asterisks instead
    // ("*When to expect improvement:**") - treated as a level-2 heading.
    final stray = RegExp(r'^\s*\*{1,2}([^*]+?):?\*{1,2}\s*$').firstMatch(line);
    if (stray != null) {
      return (headingLevel: 2, text: stray.group(1)!.trim(), isBullet: false);
    }
    final bullet = RegExp(r'^\s*[-*•]\s+').firstMatch(line);
    if (bullet != null) {
      return (headingLevel: null, text: line.substring(bullet.end), isBullet: true);
    }
    return (headingLevel: null, text: line, isBullet: false);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final base = TextStyle(
      fontSize: fontSize,
      height: 1.5,
      color: dark ? kTextPrimaryDark : kTextPrimaryLight,
    );

    // Group lines into sections at heading boundaries so sections can
    // collapse. Section 0 is any preamble before the first heading.
    final sections = <({String? title, bool isTop, List<String> lines})>[];
    var current = (title: null as String?, isTop: false, lines: <String>[]);
    for (final rawLine in text.split('\n')) {
      final parsed = _parseLine(rawLine);
      if (parsed.headingLevel != null) {
        if (current.title != null || current.lines.any((l) => l.trim().isNotEmpty)) {
          sections.add(current);
        }
        current = (
          title: parsed.text,
          isTop: parsed.headingLevel! <= 1,
          lines: <String>[],
        );
      } else {
        current.lines.add(rawLine);
      }
    }
    if (current.title != null || current.lines.any((l) => l.trim().isNotEmpty)) {
      sections.add(current);
    }

    final headedCount = sections.where((s) => s.title != null && !s.isTop).length;
    final useCollapse = collapsible && headedCount >= 2;

    final children = <Widget>[];
    var expandedShown = false;
    for (final section in sections) {
      if (section.title != null) {
        if (useCollapse && !section.isTop) {
          if (expandedShown) {
            children.add(_CollapsibleSection(
              title: section.title!,
              dark: dark,
              fontSize: fontSize,
              child: _linesColumn(section.lines, base, dark),
            ));
            continue;
          }
          expandedShown = true;
        }
        children.add(Padding(
          padding: EdgeInsets.only(
              top: children.isEmpty ? 0 : (section.isTop ? 18 : 14), bottom: 6),
          child: Text(
            section.title!,
            style: TextStyle(
              fontSize: fontSize + (section.isTop ? 3.5 : 1.5),
              height: 1.3,
              fontWeight: FontWeight.w700,
              color: section.isTop
                  ? (dark ? kTextPrimaryDark : kTextPrimaryLight)
                  : (dark ? kTealGlow : kTeal),
            ),
          ),
        ));
      }
      children.add(_linesColumn(section.lines, base, dark));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  /// Render a section's body lines. Long runs (4+) of consecutive
  /// "Call your doctor..." bullets collapse into one expandable row so a
  /// tired reader sees the section, not a wall of near-identical lines.
  Widget _linesColumn(List<String> lines, TextStyle base, bool dark) {
    final children = <Widget>[];
    final pendingDoctorBullets = <String>[];

    void flushDoctorRun() {
      if (pendingDoctorBullets.length >= 4) {
        children.add(_CollapsibleSection(
          title: 'When to call your doctor (${pendingDoctorBullets.length})',
          dark: dark,
          fontSize: fontSize,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final b in pendingDoctorBullets) _bulletRow(b, base, dark),
            ],
          ),
        ));
      } else {
        for (final b in pendingDoctorBullets) {
          children.add(_bulletRow(b, base, dark));
        }
      }
      pendingDoctorBullets.clear();
    }

    for (final rawLine in lines) {
      final parsed = _parseLine(rawLine);
      if (parsed.text.trim().isEmpty) {
        flushDoctorRun();
        children.add(const SizedBox(height: 8));
        continue;
      }
      if (parsed.isBullet &&
          parsed.text.toLowerCase().startsWith('call your doctor')) {
        pendingDoctorBullets.add(parsed.text);
        continue;
      }
      flushDoctorRun();
      if (parsed.isBullet) {
        children.add(_bulletRow(parsed.text, base, dark));
      } else {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text.rich(TextSpan(children: _boldSpans(parsed.text, base))),
        ));
      }
    }
    flushDoctorRun();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  Widget _bulletRow(String text, TextStyle base, bool dark) {
    return Padding(
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
            child: Text.rich(TextSpan(children: _boldSpans(text, base))),
          ),
        ],
      ),
    );
  }

  /// Split `a **b** c` into styled spans; unmatched `**` markers are
  /// stripped - a patient should never see raw asterisks, and dropping a
  /// stray marker is safer than guessing what it meant to emphasise.
  static List<InlineSpan> _boldSpans(String line, TextStyle base) {
    final spans = <InlineSpan>[];
    final parts = line.split('**');
    if (parts.length.isEven) {
      return [TextSpan(text: line.replaceAll('**', ''), style: base)];
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

/// One collapsed content section: heading row with a chevron, body revealed
/// on tap. Styled to match PatientText subheadings so collapsed and expanded
/// sections read as the same document.
class _CollapsibleSection extends StatefulWidget {
  const _CollapsibleSection({
    required this.title,
    required this.dark,
    required this.fontSize,
    required this.child,
  });

  final String title;
  final bool dark;
  final double fontSize;
  final Widget child;

  @override
  State<_CollapsibleSection> createState() => _CollapsibleSectionState();
}

class _CollapsibleSectionState extends State<_CollapsibleSection> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final accent = widget.dark ? kTealGlow : kTeal;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () => setState(() => _open = !_open),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.title,
                    style: TextStyle(
                      fontSize: widget.fontSize + 1.5,
                      height: 1.3,
                      fontWeight: FontWeight.w700,
                      color: accent,
                    ),
                  ),
                ),
                Icon(
                  _open ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: accent,
                ),
              ],
            ),
          ),
        ),
        if (_open)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: widget.child,
          ),
      ],
    );
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
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
        border: Border.all(color: widget.dark ? kBorderDark : kBorderLight),
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
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
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
              // Provenance (trust feature): the exact document passage
              // Agent 1 extracted this diagnosis from.
              SourceQuote(source: ext['primary_diagnosis_source']),
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
          explanation.isEmpty
              ? Text(
                  'No explanation available.',
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                )
              : PatientText(text: explanation, collapsible: true),
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
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      children: [
        if (medList.isNotEmpty) ...[
          // Medication reminders (competitor-gap B1): patient-confirmed
          // daily nudges, scheduled locally on the phone only.
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            child: Material(
              color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
              borderRadius: BorderRadius.circular(kRadiusField),
              child: InkWell(
                borderRadius: BorderRadius.circular(kRadiusField),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => MedicationRemindersScreen(
                      extraction: extraction is Map
                          ? (extraction as Map).cast<String, dynamic>()
                          : <String, dynamic>{},
                    ),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                  child: Row(
                    children: [
                      Icon(Icons.notifications_active_outlined,
                          size: 19, color: dark ? kTealGlow : kTeal),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          'Never miss a dose - set up daily reminders',
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: dark ? kTealGlow : kTeal,
                          ),
                        ),
                      ),
                      Icon(Icons.chevron_right,
                          size: 18, color: dark ? kTealGlow : kTeal),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
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
              source: med['source'],
              dark: dark,
            );
          }),
        // AI-review questions BELOW the medication list - same rule as the
        // warning tab: the patient's actual content first, meta last.
        _GapCallout(
          simulator: simulator,
          keywords: const ['medication', 'medicine', 'drug', 'dose', 'pill', 'tablet', 'inhaler', 'insulin', 'prescription'],
          dark: dark,
        ),
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
    this.source,
    required this.dark,
  });
  final String name;
  final String details;
  final String status;
  final Color borderColor;
  final String badgeText;
  final String? rationale;
  final dynamic source; // SourceSpan map - provenance for this medication
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
        borderRadius: BorderRadius.circular(kRadiusField),
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
                      SourceQuote(source: widget.source),
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
                      borderRadius: BorderRadius.circular(kRadiusField),
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
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      children: [
        // Safety notice
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: dark ? kTier1.withValues(alpha: 0.15) : kTier1Bg,
            borderRadius: BorderRadius.circular(kRadiusField),
            border: Border.all(color: kTier1.withValues(alpha: 0.3)),
          ),
          child: Text(
            'This guide is AI-generated. Call your care team to confirm what needs emergency care for your situation.',
            style: TextStyle(fontSize: 12, color: dark ? kTier1 : const Color(0xFF7F1D1D)),
          ),
        ),

        // Red-flag bullets from extraction - FALLBACK ONLY. When Agent 5's
        // three-tier guide exists it restates these same symptoms with
        // explanations, so showing both is pure duplication (patient
        // feedback July 2026: overwhelming).
        if (flags.isNotEmpty && !hasTiers) ...[
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: dark ? kTier1.withValues(alpha: 0.12) : const Color(0xFFFCEBEB),
              borderRadius: BorderRadius.circular(kRadiusField),
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
        // AI-review questions render BELOW all escalation content: a patient
        // opening this tab in a crisis must hit the 911 list first, not
        // meta-commentary about their document.
        _GapCallout(
          simulator: simulator,
          keywords: const ['symptom', 'emergency', '911', 'er ', 'warning', 'sign', 'fever', 'pain', 'breathe', 'bleeding'],
          dark: dark,
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
        borderRadius: BorderRadius.circular(kRadiusField),
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

class _AppointmentsBody extends StatelessWidget {
  const _AppointmentsBody({required this.extraction, this.simulator});

  final dynamic extraction;

  /// Agent 6 output - its unanswered questions become the visit-prep list.
  final dynamic simulator;

  /// Visit-prep (competitor-gap B4): the questions the AI Review found the
  /// document does NOT answer are exactly what the patient should ask at
  /// the follow-up. Grounded in Agent 6 output only - nothing generated here.
  List<String> get _visitQuestions {
    if (simulator is! Map) return const [];
    final concepts = (simulator as Map)['missed_concepts'];
    if (concepts is! List) return const [];
    final ranked = concepts.whereType<Map>().toList()
      ..sort((a, b) {
        int rank(m) => switch ('${m['severity']}') {
              'critical' => 0, 'moderate' => 1, _ => 2 };
        return rank(a).compareTo(rank(b));
      });
    return [
      for (final c in ranked.take(5))
        if ('${c['question'] ?? ''}'.isNotEmpty) '${c['question']}'
    ];
  }

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
    final questions = _visitQuestions;
    if (list == null || list.isEmpty) {
      if (questions.isEmpty) {
        return const _RichTextSection(text: 'No follow-up appointments listed in this document.');
      }
      final dark0 = Theme.of(context).brightness == Brightness.dark;
      return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 110), children: [
        const _RichTextSection(text: 'No follow-up appointments listed in this document.'),
        _VisitPrepCard(questions: questions, dark: dark0),
      ]);
    }
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      itemCount: list.length + (questions.isEmpty ? 0 : 1),
      itemBuilder: (context, i) {
        // Visit-prep card renders after the appointment list.
        if (i == list.length) {
          return _VisitPrepCard(questions: questions, dark: dark);
        }
        final a = list[i];
        if (a is! Map) return const SizedBox.shrink();
        return Card(
          color: dark ? kCardDark : kCardLight,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ListTile(
                title: Text('${a['specialty'] ?? a['provider'] ?? 'Appointment'}'),
                // Date lives ONLY in the trailing chip (it rendered twice
                // before). Subtitle carries who + why.
                subtitle: Text(
                  [
                    if (a['specialty'] != null && a['provider'] != null)
                      '${a['provider']}',
                    if ('${a['reason'] ?? ''}'.isNotEmpty) '${a['reason']}',
                  ].join('\n'),
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
                padding: const EdgeInsets.only(left: 16, right: 16),
                child: SourceQuote(source: a['source']),
              ),
              Padding(
                padding: const EdgeInsets.only(left: 8, right: 8, bottom: 6),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => _addToCalendar(context, a),
                    icon: const Icon(Icons.calendar_month_outlined, size: 18),
                    label: const Text('Add to calendar'),
                    // Color comes from the theme; only the 48dp touch target
                    // (same rule as the audio play button) stays local.
                    style: TextButton.styleFrom(
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
