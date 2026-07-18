/// widgets/journey_widgets.dart
///
/// Recovery Journey (gamification, journey theme): a custom-painted milestone
/// trail that fills in as the patient works through their discharge
/// instructions. Pure presentation over existing persisted state - no new
/// tracking:
///   - 6 path milestones = the 6 discharge stars (5 reading + calendar)
///   - 5 ridge flags     = the 5 mastered comprehension domains
///   - summit star       = appears when all three quests are complete
/// Replaces the earlier garden theme with an unisex, age-neutral visual;
/// every mechanic (stars, quests, seed return hook, mood check-in) and every
/// persisted key is unchanged - this file only changes what the patient sees.
/// Unearned slots render as faint outlines: progress ahead, never loss.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/journey_coach.dart';
import 'package:dischargeiq_mobile/services/quests.dart';
import 'package:dischargeiq_mobile/services/reminder_service.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusField;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

/// Calendar season for the scene's subtle sky shift (the picture lives in
/// real time, so returning feels alive). Pure so it is testable.
/// ponytail: northern-hemisphere months; add a hemisphere setting if a
/// southern-hemisphere deployment ever happens.
String seasonOf(DateTime now) => switch (now.month) {
      3 || 4 || 5 => 'spring',
      6 || 7 || 8 => 'summer',
      9 || 10 || 11 => 'autumn',
      _ => 'winter',
    };

/// Card shown on the landing page: journey painting + quest progress rows.
class RecoveryJourneyCard extends StatefulWidget {
  const RecoveryJourneyCard({
    super.key,
    required this.stars,
    required this.stats,
    required this.dark,
    this.docPicker,
  });

  /// Earned stars for the document this card is showing (per-document).
  final Set<String> stars;
  final GameStats stats;
  final bool dark;

  /// Optional document selector rendered under the title - supplied by the
  /// landing page when more than one saved analysis exists, so the patient
  /// always knows WHICH document's journey they are looking at.
  final Widget? docPicker;

  @override
  State<RecoveryJourneyCard> createState() => _RecoveryJourneyCardState();
}

class _RecoveryJourneyCardState extends State<RecoveryJourneyCard> {
  /// Wraps the painting so "share your journey" can render it to a PNG.
  final GlobalKey _paintKey = GlobalKey();

  /// Render the journey painting to a PNG and hand it to the native share
  /// sheet. Patient-initiated, composed on-device, no server involved -
  /// same rules as the caregiver text share (services/share_summary.dart).
  Future<void> _shareJourney() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final boundary = _paintKey.currentContext?.findRenderObject()
          as RenderRepaintBoundary?;
      if (boundary == null) return;
      final image = await boundary.toImage(pixelRatio: 3);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      if (bytes == null) return;
      await Share.shareXFiles(
        [
          XFile.fromData(
            bytes.buffer.asUint8List(),
            mimeType: 'image/png',
            name: 'my_recovery_journey.png',
          ),
        ],
        text: 'Tracking my recovery, one milestone at a time. '
            '(from DischargeIQ)',
      );
    } catch (e) {
      // Sharing is a nicety - never let it surface as a failure state.
      debugPrint('journey share failed: $e');
      messenger.showSnackBar(
        const SnackBar(
            content: Text('Could not share your journey right now.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final stars = widget.stars;
    final stats = widget.stats;
    final dark = widget.dark;
    final quests = buildQuests(stars: stars, stats: stats);
    final milestones = kAllStarKeys.where(stars.contains).length;
    final mastered = stats.masteredDomains.length.clamp(0, 5);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kSurfaceLight,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'YOUR RECOVERY JOURNEY',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.6,
                    color: dark ? kTealGlow : kTeal,
                  ),
                ),
              ),
              Tooltip(
                message: 'Share a picture of your progress',
                child: InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: _shareJourney,
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Icon(
                      Icons.ios_share_outlined,
                      size: 18,
                      color:
                          dark ? kTextSecondaryDark : kTextSecondaryLight,
                    ),
                  ),
                ),
              ),
              _JourneyReminderBell(dark: dark),
            ],
          ),
          if (widget.docPicker != null) ...[
            const SizedBox(height: 4),
            widget.docPicker!,
          ],
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: RepaintBoundary(
              key: _paintKey,
              child: CustomPaint(
                painter: _JourneyPainter(
                  stars: stars,
                  masteredCount: mastered,
                  allQuestsDone: quests.every((q) => q.complete),
                  dark: dark,
                  season: seasonOf(DateTime.now()),
                ),
                child: const SizedBox(width: double.infinity, height: 130),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '$milestones of ${kAllStarKeys.length} milestones reached'
            '${mastered > 0 ? ' · $mastered topic${mastered == 1 ? '' : 's'} mastered' : ''}',
            style: TextStyle(
              fontSize: 11,
              color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            ),
          ),
          _BonusRow(dark: dark),
          const SizedBox(height: 12),
          _DailyCheckin(dark: dark, stats: stats, stars: stars),
          for (final q in quests) _QuestRow(quest: q, dark: dark),
        ],
      ),
    );
  }
}

/// Small bell toggle in the card header: opt in/out of ONE gentle daily
/// notification (10:00). Off by default - the nudge is invited, never pushed.
/// Denying the OS permission simply leaves the bell off, with a short
/// explainer snackbar; no error state, no re-prompting loop.
class _JourneyReminderBell extends StatefulWidget {
  const _JourneyReminderBell({required this.dark});

  final bool dark;

  @override
  State<_JourneyReminderBell> createState() => _JourneyReminderBellState();
}

class _JourneyReminderBellState extends State<_JourneyReminderBell> {
  bool _on = false;

  @override
  void initState() {
    super.initState();
    ReminderService.gardenReminderEnabled().then((on) {
      if (mounted) setState(() => _on = on);
    });
  }

  Future<void> _toggle() async {
    final messenger = ScaffoldMessenger.of(context);
    if (_on) {
      await ReminderService.disableGardenReminder();
      if (mounted) setState(() => _on = false);
      return;
    }
    final granted = await ReminderService.enableGardenReminder();
    if (!mounted) return;
    setState(() => _on = granted);
    messenger.showSnackBar(SnackBar(
      content: Text(granted
          ? 'One gentle reminder a day, around 10 in the morning.'
          : 'Notifications are off for this app. You can allow them in '
              'your phone settings any time.'),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: _on ? 'Daily reminder is on' : 'Get one gentle daily reminder',
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: _toggle,
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Icon(
            _on
                ? Icons.notifications_active_outlined
                : Icons.notifications_none_outlined,
            size: 18,
            color: _on
                ? (widget.dark ? kTealGlow : kTeal)
                : (widget.dark ? kTextSecondaryDark : kTextSecondaryLight),
          ),
        ),
      ),
    );
  }
}

/// The "bonus that unlocks tomorrow" line (appointment mechanic, was the
/// seed-blooms-tomorrow hook - same SeedStore state and keys, new copy).
/// Finishing a quiz or puzzle banks today's effort; this row shows it waiting
/// today and pays it off on the next visit. A payoff is acknowledged
/// automatically once seen - no action needed, and an unvisited bonus just
/// waits (never expires).
class _BonusRow extends StatefulWidget {
  const _BonusRow({required this.dark});

  final bool dark;

  @override
  State<_BonusRow> createState() => _BonusRowState();
}

class _BonusRowState extends State<_BonusRow> {
  SeedState _state = SeedState.none;
  int _collected = 0;

  @override
  void initState() {
    super.initState();
    SeedStore.state().then((s) async {
      var collected = 0;
      if (s == SeedState.bloomed) {
        // Count it the moment it is seen; the line stays up for this build
        // of the card and is simply gone next time.
        collected = await SeedStore.acknowledgeBloom();
      }
      if (mounted) {
        setState(() {
          _state = s;
          _collected = collected;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_state == SeedState.none) return const SizedBox.shrink();
    final accent = widget.dark ? kTealGlow : kTeal;
    final text = _state == SeedState.planted
        ? 'Today\'s effort is banked - a bonus unlocks tomorrow.'
        : 'Bonus unlocked! $_collected earned from your effort so far.';
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        children: [
          Icon(Icons.workspace_premium_outlined, size: 15, color: accent),
          const SizedBox(width: 5),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: accent,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Once-a-day mood check-in. Design rules: one question, three big answers,
/// kind response, done. No streaks, no guilt for missed days, and a rough
/// day gets acknowledgment plus a gentle safety pointer - never a cheerful
/// dismissal.
///
/// Once today's mood is known, a mood-sized coach suggestion
/// (services/journey_coach.dart) renders below the response - one gentle
/// next step, guidance only, never a task.
class _DailyCheckin extends StatefulWidget {
  const _DailyCheckin(
      {required this.dark, required this.stats, required this.stars});

  final bool dark;
  final GameStats stats;
  final Set<String> stars;

  @override
  State<_DailyCheckin> createState() => _DailyCheckinState();
}

class _DailyCheckinState extends State<_DailyCheckin> {
  bool? _doneToday; // null while loading
  String? _justAnswered;
  int _totalDays = 0;

  String? _todayMood;

  @override
  void initState() {
    super.initState();
    CheckinStore.load().then((entries) {
      final now = DateTime.now();
      final today = '${now.year.toString().padLeft(4, '0')}-'
          '${now.month.toString().padLeft(2, '0')}-'
          '${now.day.toString().padLeft(2, '0')}';
      String? mood;
      for (final e in entries) {
        if (e.$1 == today) mood = e.$2;
      }
      if (mounted) {
        setState(() {
          _doneToday = mood != null;
          _todayMood = mood;
          _totalDays = entries.length;
        });
      }
    });
  }

  int _roughRun = 0;

  Future<void> _answer(String mood) async {
    final total = await CheckinStore.record(mood);
    // Escalation check (B3): an unbroken run of rough days deserves more
    // than a platitude - but the app still only ever suggests a call.
    final run = mood == 'rough'
        ? consecutiveRoughDays(await CheckinStore.load())
        : 0;
    if (!mounted) return;
    setState(() {
      _justAnswered = mood;
      _doneToday = true;
      _todayMood = mood;
      _totalDays = total;
      _roughRun = run;
    });
  }

  @override
  Widget build(BuildContext context) {
    final dark = widget.dark;
    if (_doneToday == null) return const SizedBox.shrink();

    final sub = TextStyle(
      fontSize: 12,
      height: 1.4,
      color: dark ? kTextSecondaryDark : kTextSecondaryLight,
    );

    Widget content;
    if (_doneToday! && _justAnswered == null) {
      // Already checked in earlier today - one quiet line, no repeat ask.
      content = Text(
        'Checked in today · $_totalDays day${_totalDays == 1 ? '' : 's'} of '
        'looking after yourself',
        style: sub,
      );
    } else if (_justAnswered != null) {
      content = Text(
        switch (_justAnswered) {
          'good' => 'Glad today feels good. Another step forward.',
          'okay' => 'Okay is enough. One small step today is plenty.',
          _ => _roughRun >= 3
              ? 'That is $_roughRun rough days in a row. That is worth a '
                  'phone call - your care team wants to know how recovery '
                  'is going, and the number is on your discharge papers. '
                  'If any warning sign on your Warning signs tab is '
                  'happening, act on it now.'
              : 'Rough days are part of recovery. If something feels wrong, '
                  'check your Warning signs tab or call your doctor - that is '
                  'what they are there for.',
        },
        style: sub,
      );
    } else {
      content = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'How are you feeling today?',
            style: TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              for (final (mood, label) in const [
                ('good', '🙂 Good'),
                ('okay', '😐 Okay'),
                ('rough', '😕 Rough'),
              ]) ...[
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: dark ? kTealGlow : kTeal,
                      side: BorderSide(
                          color: (dark ? kTealGlow : kTeal)
                              .withValues(alpha: 0.5)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: () => _answer(mood),
                    child: Text(label, style: const TextStyle(fontSize: 13)),
                  ),
                ),
                if (mood != 'rough') const SizedBox(width: 8),
              ],
            ],
          ),
        ],
      );
    }

    // Mood-adaptive coach line: one gentle next step sized to how today
    // feels. Guidance only - it is not a button and asks for nothing.
    final coach = suggestNextStep(
      todayMood: _todayMood,
      stats: widget.stats,
      stars: widget.stars,
    );
    if (coach != null) {
      final coachIcon = switch (coach.kind) {
        CoachKind.rest => Icons.self_improvement_outlined,
        CoachKind.read => Icons.menu_book_outlined,
        CoachKind.puzzle => Icons.extension_outlined,
        CoachKind.quiz => Icons.school_outlined,
        CoachKind.celebrate => Icons.emoji_events_outlined,
      };
      content = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          content,
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(coachIcon, size: 15, color: dark ? kTealGlow : kTeal),
              const SizedBox(width: 6),
              Expanded(child: Text(coach.text, style: sub)),
            ],
          ),
        ],
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: dark ? kTeal.withValues(alpha: 0.18) : const Color(0xFFF0FAF5),
          borderRadius: BorderRadius.circular(kRadiusField),
        ),
        child: content,
      ),
    );
  }
}

class _QuestRow extends StatelessWidget {
  const _QuestRow({required this.quest, required this.dark});

  final Quest quest;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final accent = dark ? kTealGlow : kTeal;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            quest.complete
                ? Icons.check_circle_rounded
                : Icons.radio_button_unchecked,
            size: 18,
            color: quest.complete
                ? accent
                : (dark ? kTextHintDark : kTextHintLight),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      quest.title,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '${quest.done}/${quest.total}',
                      style: TextStyle(fontSize: 11.5, color: accent),
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: quest.progress,
                    minHeight: 5,
                    backgroundColor:
                        dark ? Colors.white10 : const Color(0xFFE5EFE9),
                    valueColor: AlwaysStoppedAnimation<Color>(accent),
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  quest.subtitle,
                  style: TextStyle(
                    fontSize: 11,
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

/// Paints the journey: seasonal sky, a distant ridge carrying 5 flags
/// (mastered domains), a winding trail carrying 6 milestone markers (the
/// discharge stars), and a summit star once all quests are complete.
/// Deterministic layout - same state, same picture.
class _JourneyPainter extends CustomPainter {
  _JourneyPainter({
    required this.stars,
    required this.masteredCount,
    required this.allQuestsDone,
    required this.dark,
    this.season = 'spring',
  });

  final Set<String> stars;
  final int masteredCount;
  final bool allQuestsDone;
  final bool dark;

  /// 'spring' | 'summer' | 'autumn' | 'winter' (see [seasonOf]). Shifts the
  /// sky tone subtly; the scene has no bad-weather state.
  final String season;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Sky - tinted by season, always friendly (winter is crisp, not grey).
    final skyColors = dark
        ? switch (season) {
            'summer' => const [Color(0xFF0A3A2A), Color(0xFF0E4530)],
            'autumn' => const [Color(0xFF2E2A16), Color(0xFF0A3D2E)],
            'winter' => const [Color(0xFF102A38), Color(0xFF0A3D2E)],
            _ => const [Color(0xFF06302A), Color(0xFF0A3D2E)],
          }
        : switch (season) {
            'summer' => const [Color(0xFFE0F5E8), Color(0xFFFDF9EC)],
            'autumn' => const [Color(0xFFFBF2E0), Color(0xFFF7FAF8)],
            'winter' => const [Color(0xFFE8F2FA), Color(0xFFF7FAF8)],
            _ => const [Color(0xFFEAF7F1), Color(0xFFF7FAF8)],
          };
    final sky = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: skyColors,
      ).createShader(Rect.fromLTWH(0, 0, w, h));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h), sky);

    // Distant ridge - a soft rolling silhouette behind the trail.
    final ridgeTop = h * 0.42;
    final ridge = Path()
      ..moveTo(0, ridgeTop + 10)
      ..quadraticBezierTo(w * 0.2, ridgeTop - 12, w * 0.42, ridgeTop + 4)
      ..quadraticBezierTo(w * 0.62, ridgeTop + 16, w * 0.8, ridgeTop - 2)
      ..quadraticBezierTo(w * 0.92, ridgeTop - 12, w, ridgeTop - 4)
      ..lineTo(w, h)
      ..lineTo(0, h)
      ..close();
    canvas.drawPath(
      ridge,
      Paint()
        ..color = (dark ? const Color(0xFF0B2B20) : const Color(0xFFDBEDE2)),
    );

    // 5 ridge flags - one per mastered comprehension domain.
    for (var i = 0; i < 5; i++) {
      final x = w * (0.14 + 0.18 * i);
      final y = _ridgeYAt(x / w, ridgeTop);
      _drawFlag(canvas, Offset(x, y), raised: i < masteredCount);
    }

    // The trail: a winding stroke from bottom-left toward the ridge's end.
    final trail = Path()
      ..moveTo(w * 0.02, h * 0.94)
      ..cubicTo(w * 0.3, h * 1.02, w * 0.42, h * 0.62, w * 0.62, h * 0.68)
      ..cubicTo(w * 0.78, h * 0.72, w * 0.88, h * 0.56, w * 0.96, h * 0.52);
    canvas.drawPath(
      trail,
      Paint()
        ..color = dark ? const Color(0xFF11402F) : const Color(0xFFCBE4D4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 11
        ..strokeCap = StrokeCap.round,
    );
    canvas.drawPath(
      trail,
      Paint()
        ..color = dark
            ? kTealGlow.withValues(alpha: 0.35)
            : kTeal.withValues(alpha: 0.35)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round,
    );

    // 6 milestone markers spaced along the trail, in kAllStarKeys order.
    final metrics = trail.computeMetrics().first;
    for (var i = 0; i < kAllStarKeys.length; i++) {
      final t = (i + 0.5) / kAllStarKeys.length;
      final pos = metrics.getTangentForOffset(metrics.length * t)!.position;
      _drawMilestone(canvas, pos,
          reached: stars.contains(kAllStarKeys[i]));
    }

    // Summit star - appears once every quest is complete.
    if (allQuestsDone) {
      final end = metrics.getTangentForOffset(metrics.length)!.position;
      _drawSummitStar(canvas, end.translate(0, -16));
    }
  }

  /// Approximate ridge height at a horizontal fraction, mirroring the
  /// quadratic segments above closely enough to sit flags on the line.
  double _ridgeYAt(double fx, double ridgeTop) {
    if (fx < 0.42) {
      final t = fx / 0.42;
      return _quad(ridgeTop + 10, ridgeTop - 12, ridgeTop + 4, t);
    }
    if (fx < 0.8) {
      final t = (fx - 0.42) / 0.38;
      return _quad(ridgeTop + 4, ridgeTop + 16, ridgeTop - 2, t);
    }
    final t = (fx - 0.8) / 0.2;
    return _quad(ridgeTop - 2, ridgeTop - 12, ridgeTop - 4, t);
  }

  double _quad(double p0, double p1, double p2, double t) =>
      (1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p1 + t * t * p2;

  /// A milestone marker on the trail: reached = filled teal disc with a
  /// white check; unreached = faint outlined disc (ahead, not missing).
  void _drawMilestone(Canvas canvas, Offset at, {required bool reached}) {
    if (reached) {
      canvas.drawCircle(
          at, 8, Paint()..color = dark ? kTealGlow : kTeal);
      final check = Paint()
        ..color = dark ? const Color(0xFF06302A) : Colors.white
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke;
      canvas.drawLine(at.translate(-3.2, 0.2), at.translate(-0.8, 2.6), check);
      canvas.drawLine(at.translate(-0.8, 2.6), at.translate(3.4, -2.4), check);
    } else {
      canvas.drawCircle(
        at,
        6.5,
        Paint()
          ..color = (dark ? kTealGlow : kTeal).withValues(alpha: 0.3)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
    }
  }

  /// A ridge flag: raised = teal pennant on a pole (a mastered topic);
  /// not yet = a faint bare pole (a topic still ahead).
  void _drawFlag(Canvas canvas, Offset base, {required bool raised}) {
    if (raised) {
      final pole = Paint()
        ..color = dark ? kTealLight : const Color(0xFF3E6E5A)
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(base, base.translate(0, -20), pole);
      final pennant = Path()
        ..moveTo(base.dx, base.dy - 20)
        ..lineTo(base.dx + 11, base.dy - 16.5)
        ..lineTo(base.dx, base.dy - 13)
        ..close();
      canvas.drawPath(pennant, Paint()..color = dark ? kTealGlow : kTeal);
    } else {
      final faint = Paint()
        ..color = (dark ? kTealGlow : kTeal).withValues(alpha: 0.25)
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(base, base.translate(0, -12), faint);
    }
  }

  /// Gold star at the trail's end once all quests are done - the one
  /// celebratory flourish, same reward color as the earned stars.
  void _drawSummitStar(Canvas canvas, Offset at) {
    const gold = Color(0xFFF5B300);
    final star = Path();
    for (var i = 0; i < 5; i++) {
      final outer = i * 2 * math.pi / 5 - math.pi / 2;
      final inner = outer + math.pi / 5;
      final po = at + Offset(math.cos(outer) * 9, math.sin(outer) * 9);
      final pi_ = at + Offset(math.cos(inner) * 3.8, math.sin(inner) * 3.8);
      if (i == 0) {
        star.moveTo(po.dx, po.dy);
      } else {
        star.lineTo(po.dx, po.dy);
      }
      star.lineTo(pi_.dx, pi_.dy);
    }
    star.close();
    canvas.drawPath(star, Paint()..color = gold);
  }

  @override
  bool shouldRepaint(covariant _JourneyPainter old) =>
      old.stars != stars ||
      old.masteredCount != masteredCount ||
      old.allQuestsDone != allQuestsDone ||
      old.dark != dark ||
      old.season != season;
}
