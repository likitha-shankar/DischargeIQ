/// widgets/garden_widgets.dart
///
/// Recovery Garden (gamification wave 2): a custom-painted garden that grows
/// as the patient works through their discharge instructions. Pure
/// presentation over existing persisted state - no new tracking:
///   - 6 front-row flowers  = the 6 discharge stars (5 reading + calendar)
///   - 5 back-row trees     = the 5 mastered comprehension domains
///   - sun                  = always out (no weather, no punishment states)
///   - butterfly            = appears when all three quests are complete
/// Evidence basis: garden metaphors ranked first for health-data visuals
/// (Sprout, CHI 2026) - familiar, non-judgmental, growth-framed.
/// Unearned slots render as faint sprouts/saplings: growth ahead, never loss.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/garden_coach.dart';
import 'package:dischargeiq_mobile/services/quests.dart';
import 'package:dischargeiq_mobile/services/reminder_service.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusField;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

/// Calendar season for the garden's subtle visual shift (idea: the garden
/// lives in real time, so returning feels alive). Pure so it is testable.
/// ponytail: northern-hemisphere months; add a hemisphere setting if a
/// southern-hemisphere deployment ever happens.
String seasonOf(DateTime now) => switch (now.month) {
      3 || 4 || 5 => 'spring',
      6 || 7 || 8 => 'summer',
      9 || 10 || 11 => 'autumn',
      _ => 'winter',
    };

/// Card shown on the landing page: garden painting + quest progress rows.
class RecoveryGardenCard extends StatefulWidget {
  const RecoveryGardenCard({
    super.key,
    required this.stars,
    required this.stats,
    required this.dark,
  });

  final Set<String> stars;
  final GameStats stats;
  final bool dark;

  @override
  State<RecoveryGardenCard> createState() => _RecoveryGardenCardState();
}

class _RecoveryGardenCardState extends State<RecoveryGardenCard> {
  /// Wraps the painting so "show your garden" can render it to a PNG.
  final GlobalKey _paintKey = GlobalKey();

  /// Companion kind + whether the companion is cheering (a seed exists -
  /// today's effort was noticed, or a bloom was just seen). Loaded together
  /// so the painting appears in one frame.
  Future<(String, bool)> _companionState() async {
    final kind = await CompanionStore.kind();
    final seed = await SeedStore.state();
    return (kind, seed != SeedState.none);
  }

  /// Render the garden painting to a PNG and hand it to the native share
  /// sheet. Patient-initiated, composed on-device, no server involved -
  /// same rules as the caregiver text share (services/share_summary.dart).
  Future<void> _shareGarden() async {
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
            name: 'my_recovery_garden.png',
          ),
        ],
        text: 'My recovery garden is growing 🌱 (from DischargeIQ)',
      );
    } catch (e) {
      // Sharing is a nicety - never let it surface as a failure state.
      debugPrint('garden share failed: $e');
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not share the garden right now.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final stars = widget.stars;
    final stats = widget.stats;
    final dark = widget.dark;
    final quests = buildQuests(stars: stars, stats: stats);
    final flowers = kAllStarKeys.where(stars.contains).length;
    final trees = stats.masteredDomains.length.clamp(0, 5);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kSurfaceLight,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: dark ? kBorderDark : kBorderLight,
          width: 0.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'YOUR RECOVERY GARDEN',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.6,
                    color: dark ? kTealGlow : kTeal,
                  ),
                ),
              ),
              Tooltip(
                message: 'Share a picture of your garden',
                child: InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: _shareGarden,
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
              _GardenReminderBell(dark: dark),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: FutureBuilder<(String, bool)>(
              future: _companionState(),
              builder: (context, snap) => RepaintBoundary(
                key: _paintKey,
                child: CustomPaint(
                  painter: _GardenPainter(
                    stars: stars,
                    masteredCount: trees,
                    allQuestsDone: quests.every((q) => q.complete),
                    dark: dark,
                    companionKind: snap.data?.$1 ?? 'butterfly',
                    companionCheering: snap.data?.$2 ?? false,
                    season: seasonOf(DateTime.now()),
                  ),
                  child:
                      const SizedBox(width: double.infinity, height: 130),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: Text(
                  '$flowers of ${kAllStarKeys.length} flowers blooming'
                  '${trees > 0 ? ' · $trees tree${trees == 1 ? '' : 's'} grown' : ''}',
                  style: TextStyle(
                    fontSize: 11,
                    color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ),
              _CompanionName(
                  dark: dark, butterflyHome: quests.every((q) => q.complete)),
            ],
          ),
          _SeedRow(dark: dark),
          const SizedBox(height: 12),
          _DailyCheckin(dark: dark, stats: stats, stars: stars),
          for (final q in quests) _QuestRow(quest: q, dark: dark),
        ],
      ),
    );
  }
}

/// Small bell toggle in the garden header: opt in/out of ONE gentle daily
/// notification (10:00). Off by default - the nudge is invited, never pushed.
/// Denying the OS permission simply leaves the bell off, with a short
/// explainer snackbar; no error state, no re-prompting loop.
class _GardenReminderBell extends StatefulWidget {
  const _GardenReminderBell({required this.dark});

  final bool dark;

  @override
  State<_GardenReminderBell> createState() => _GardenReminderBellState();
}

class _GardenReminderBellState extends State<_GardenReminderBell> {
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

/// The named garden companion (wave 5, Finch-style emotional ownership).
/// Unnamed: a quiet "name your butterfly" invitation. Named: shows the name;
/// tapping either opens the naming dialog. Renaming while the daily nudge is
/// on reschedules it so the notification copy carries the new name.
class _CompanionName extends StatefulWidget {
  const _CompanionName({required this.dark, required this.butterflyHome});

  final bool dark;

  /// True once all quests are complete and the butterfly is painted.
  final bool butterflyHome;

  @override
  State<_CompanionName> createState() => _CompanionNameState();
}

class _CompanionNameState extends State<_CompanionName> {
  String _name = '';
  String _kind = 'butterfly';

  @override
  void initState() {
    super.initState();
    CompanionStore.name().then((n) async {
      final k = await CompanionStore.kind();
      if (mounted) {
        setState(() {
          _name = n;
          _kind = k;
        });
      }
    });
  }

  Future<void> _rename() async {
    final controller = TextEditingController(text: _name);
    var pickedKind = _kind;
    final saved = await showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text(
              _name.isEmpty ? 'Your garden friend' : 'Your garden friend'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Kind picker: self-selected so the garden never assumes a
              // taste - the resident can be a butterfly, bird, turtle, or frog.
              Wrap(
                spacing: 8,
                children: [
                  for (final k in CompanionStore.kinds)
                    ChoiceChip(
                      label: Text(
                          '${CompanionStore.kindEmoji[k]} ${k[0].toUpperCase()}${k.substring(1)}'),
                      selected: pickedKind == k,
                      onSelected: (_) =>
                          setDialogState(() => pickedKind = k),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                autofocus: true,
                maxLength: 20,
                decoration: const InputDecoration(
                  hintText: 'Give them a name',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Not now'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, controller.text.trim()),
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (saved == null || saved.isEmpty || !mounted) return;
    await CompanionStore.setName(saved);
    await CompanionStore.setKind(pickedKind);
    // The daily nudge copy carries the name - refresh the scheduled
    // notification so it doesn't keep the old one.
    if (await ReminderService.gardenReminderEnabled()) {
      await ReminderService.enableGardenReminder();
    }
    if (mounted) {
      setState(() {
        _name = saved;
        _kind = pickedKind;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final accent = widget.dark ? kTealGlow : kTeal;
    final emoji = CompanionStore.kindEmoji[_kind] ?? '🦋';
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: _rename,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
        child: Text(
          _name.isEmpty
              ? 'Name your garden friend'
              : '$emoji $_name${widget.butterflyHome ? '' : ' is on the way'}',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: accent,
          ),
        ),
      ),
    );
  }
}

/// The "seed that blooms tomorrow" line (wave 5 appointment mechanic).
/// Finishing a quiz or puzzle plants a seed (SeedStore.plant); this row shows
/// it waiting today and blooming on the next visit. A bloom is acknowledged
/// automatically once seen - no action needed, and an unvisited seed just
/// waits (never wilts).
class _SeedRow extends StatefulWidget {
  const _SeedRow({required this.dark});

  final bool dark;

  @override
  State<_SeedRow> createState() => _SeedRowState();
}

class _SeedRowState extends State<_SeedRow> {
  SeedState _state = SeedState.none;
  int _blooms = 0;

  @override
  void initState() {
    super.initState();
    SeedStore.state().then((s) async {
      var blooms = 0;
      if (s == SeedState.bloomed) {
        // Count it the moment it is seen; the line stays up for this build
        // of the card and is simply gone next time.
        blooms = await SeedStore.acknowledgeBloom();
      }
      if (mounted) {
        setState(() {
          _state = s;
          _blooms = blooms;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_state == SeedState.none) return const SizedBox.shrink();
    final text = _state == SeedState.planted
        ? '🌱 Today\'s effort planted a seed - it blooms tomorrow.'
        : '🌼 Your seed bloomed! $_blooms flower${_blooms == 1 ? '' : 's'} '
            'grown from your effort.';
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
          color: widget.dark ? kTealGlow : kTeal,
        ),
      ),
    );
  }
}

/// Once-a-day mood check-in (wave 3). Design rules: one question, three big
/// answers, kind response, done. No streaks, no guilt for missed days, and
/// a rough day gets acknowledgment plus a gentle safety pointer - never a
/// cheerful dismissal.
///
/// Wave 5: once today's mood is known, a mood-sized coach suggestion
/// (services/garden_coach.dart) renders below the response - one gentle
/// next step, guidance only, never a task.
class _DailyCheckin extends StatefulWidget {
  const _DailyCheckin({required this.dark, required this.stats, required this.stars});

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
          'good' => 'Glad today feels good. Your garden noticed too.',
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

    // Mood-adaptive coach line (wave 5): one gentle next step sized to how
    // today feels. Guidance only - it is not a button and asks for nothing.
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
        CoachKind.celebrate => Icons.local_florist_outlined,
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

/// Paints the garden: sky, sun, soil, 5 back-row trees, a mixed front row of
/// 6 plants (flowers, berry shrubs, grasses - a garden, not a flowerbed),
/// and the patient's chosen companion once all quests are done.
/// Deterministic layout - same state, same picture.
class _GardenPainter extends CustomPainter {
  _GardenPainter({
    required this.stars,
    required this.masteredCount,
    required this.allQuestsDone,
    required this.dark,
    this.companionKind = 'butterfly',
    this.companionCheering = false,
    this.season = 'spring',
  });

  final Set<String> stars;
  final int masteredCount;
  final bool allQuestsDone;
  final bool dark;
  final String companionKind;

  /// True when today's effort planted a seed (or a bloom was just seen) -
  /// the companion shows a small heart. Delight only, never a state to lose.
  final bool companionCheering;

  /// 'spring' | 'summer' | 'autumn' | 'winter' (see [seasonOf]). Shifts sky
  /// and canopy tones subtly; the sun is always out in every season.
  final String season;

  // Bloom palette - petals cycle through warm + teal tones on the app palette.
  static const _petalColors = [
    Color(0xFFF5B300), // star gold
    Color(0xFF5DCAA5), // teal light
    Color(0xFFE58FB1), // soft pink
    Color(0xFF9FE1CB), // teal glow
    Color(0xFFF5B300),
    Color(0xFFE58FB1),
  ];

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

    _drawSeasonAccents(canvas, w, h);

    // Sun - always out; the garden has no bad-weather state.
    final sunCenter = Offset(w - 26, 24);
    canvas.drawCircle(
        sunCenter, 12, Paint()..color = const Color(0xFFF5B300).withValues(alpha: dark ? 0.85 : 1));
    final rayPaint = Paint()
      ..color = const Color(0xFFF5B300).withValues(alpha: dark ? 0.5 : 0.7)
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 8; i++) {
      final a = i * math.pi / 4;
      canvas.drawLine(
        sunCenter + Offset(math.cos(a) * 16, math.sin(a) * 16),
        sunCenter + Offset(math.cos(a) * 21, math.sin(a) * 21),
        rayPaint,
      );
    }

    // Soil strip.
    final soilTop = h - 26;
    canvas.drawRRect(
      RRect.fromRectAndCorners(Rect.fromLTWH(0, soilTop, w, 26)),
      Paint()..color = dark ? const Color(0xFF0B2B20) : const Color(0xFFD8EBDD),
    );

    // Back row: 5 trees (mastered domains), left-aligned spread.
    for (var i = 0; i < 5; i++) {
      final x = w * (0.12 + 0.19 * i);
      _drawTree(canvas, Offset(x, soilTop), grown: i < masteredCount);
    }

    // Front row: 6 plants (stars), in kAllStarKeys order. Types cycle
    // flower / berry shrub / grass tuft so the bed reads as a garden.
    for (var i = 0; i < kAllStarKeys.length; i++) {
      final x = w * (0.08 + 0.168 * i);
      final pos = Offset(x, soilTop + 6);
      final grown = stars.contains(kAllStarKeys[i]);
      switch (i % 3) {
        case 0:
          _drawFlower(canvas, pos, i, bloomed: grown);
        case 1:
          _drawShrub(canvas, pos, grown: grown);
        case 2:
          _drawGrass(canvas, pos, grown: grown);
      }
    }

    if (allQuestsDone) _drawCompanion(canvas, Offset(w * 0.32, 30), soilTop);
  }

  /// A few fixed drifting dots per season: pink petals in spring, gold
  /// leaves in autumn, soft snow in winter. Summer keeps a clear sky.
  /// Deterministic positions - same season, same picture.
  void _drawSeasonAccents(Canvas canvas, double w, double h) {
    final dotColor = switch (season) {
      'spring' => const Color(0xFFE58FB1).withValues(alpha: 0.55),
      'autumn' => const Color(0xFFE0A93E).withValues(alpha: 0.6),
      'winter' => Colors.white.withValues(alpha: dark ? 0.5 : 0.9),
      _ => null,
    };
    if (dotColor == null) return;
    final paint = Paint()..color = dotColor;
    const spots = [(0.15, 0.25), (0.45, 0.15), (0.62, 0.35), (0.82, 0.55)];
    for (final (fx, fy) in spots) {
      canvas.drawCircle(Offset(w * fx, h * fy), 2, paint);
    }
  }

  void _drawTree(Canvas canvas, Offset base, {required bool grown}) {
    if (grown) {
      final trunk = Paint()..color = const Color(0xFF7A5C3E);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: base.translate(0, -14), width: 5, height: 30),
          const Radius.circular(2),
        ),
        trunk,
      );
      // Autumn turns the canopies warm; every other season keeps the teal.
      final canopy = Paint()
        ..color = season == 'autumn'
            ? (dark ? const Color(0xFF8A6D2E) : const Color(0xFFC98F3B))
            : (dark ? kTealMid : kTeal);
      canvas.drawCircle(base.translate(0, -36), 13, canopy);
      canvas.drawCircle(base.translate(-9, -28), 10, canopy);
      canvas.drawCircle(base.translate(9, -28), 10, canopy);
    } else {
      // Sapling silhouette - growth ahead, not absence.
      final faint = Paint()
        ..color = (dark ? kTealGlow : kTeal).withValues(alpha: 0.22)
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(base, base.translate(0, -12), faint);
      canvas.drawCircle(base.translate(0, -16), 4.5, faint..style = PaintingStyle.stroke);
    }
  }

  void _drawFlower(Canvas canvas, Offset base, int index, {required bool bloomed}) {
    final stemColor = bloomed
        ? (dark ? kTealLight : const Color(0xFF3B6D11))
        : (dark ? kTealGlow : kTeal).withValues(alpha: 0.25);
    final stem = Paint()
      ..color = stemColor
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(base, base.translate(0, -18), stem);
    // Leaf.
    canvas.drawArc(
      Rect.fromCenter(center: base.translate(4, -9), width: 9, height: 5),
      math.pi, math.pi, false, stem,
    );

    final head = base.translate(0, -22);
    if (bloomed) {
      final petal = Paint()..color = _petalColors[index % _petalColors.length];
      for (var p = 0; p < 5; p++) {
        final a = p * 2 * math.pi / 5 - math.pi / 2;
        canvas.drawCircle(head + Offset(math.cos(a) * 4.5, math.sin(a) * 4.5), 3.4, petal);
      }
      canvas.drawCircle(head, 3.2, Paint()..color = const Color(0xFF8A5A00));
    } else {
      // Closed bud.
      canvas.drawCircle(
        head, 3,
        Paint()
          ..color = stemColor
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6,
      );
    }
  }

  /// Unbloomed berry shrub / grass share the sapling's faint outline style.
  Paint get _faintOutline => Paint()
    ..color = (dark ? kTealGlow : kTeal).withValues(alpha: 0.22)
    ..strokeWidth = 2
    ..strokeCap = StrokeCap.round;

  void _drawShrub(Canvas canvas, Offset base, {required bool grown}) {
    if (grown) {
      final bush = Paint()..color = dark ? kTealMid : const Color(0xFF3E8E5A);
      canvas.drawOval(
          Rect.fromCenter(center: base.translate(0, -8), width: 20, height: 15),
          bush);
      // Gold berries - the earned-star color, same reward language as petals.
      final berry = Paint()..color = const Color(0xFFF5B300);
      canvas.drawCircle(base.translate(-4, -9), 1.8, berry);
      canvas.drawCircle(base.translate(3, -6), 1.8, berry);
      canvas.drawCircle(base.translate(1, -12), 1.8, berry);
    } else {
      canvas.drawOval(
        Rect.fromCenter(center: base.translate(0, -6), width: 14, height: 10),
        _faintOutline..style = PaintingStyle.stroke,
      );
    }
  }

  void _drawGrass(Canvas canvas, Offset base, {required bool grown}) {
    final blade = grown
        ? (Paint()
          ..color = dark ? kTealLight : const Color(0xFF4E8E2F)
          ..strokeWidth = 2
          ..strokeCap = StrokeCap.round)
        : _faintOutline;
    // Three arcing blades; grown ones get a wheat-gold tip on the tall blade.
    canvas.drawLine(base, base.translate(-4, -14), blade);
    canvas.drawLine(base, base.translate(0, -18), blade);
    canvas.drawLine(base, base.translate(4, -13), blade);
    if (grown) {
      canvas.drawCircle(
          base.translate(0, -19), 2.2, Paint()..color = const Color(0xFFF5B300));
    }
  }

  /// The patient's chosen resident. Flying kinds hover in the sky; walking
  /// kinds sit on the soil line.
  void _drawCompanion(Canvas canvas, Offset sky, double soilTop) {
    final ground = Offset(sky.dx, soilTop - 4);
    // Flying kinds hover in the sky; every other kind sits on the soil line.
    const groundKinds = {'turtle', 'frog', 'ladybug', 'cat', 'bunny'};
    final flying = !groundKinds.contains(companionKind);
    switch (companionKind) {
      case 'bird':
        _drawBird(canvas, sky);
      case 'turtle':
        _drawTurtle(canvas, ground);
      case 'frog':
        _drawFrog(canvas, ground);
      case 'bee':
        _drawBee(canvas, sky);
      case 'ladybug':
        _drawLadybug(canvas, ground);
      case 'cat':
        _drawCat(canvas, ground);
      case 'bunny':
        _drawBunny(canvas, ground);
      default:
        _drawButterfly(canvas, sky);
    }
    if (companionCheering) {
      _drawHeart(canvas, (flying ? sky : ground).translate(9, -14));
    }
  }

  /// Small heart above the companion when it is cheering (today's effort
  /// planted a seed). Two circles + a triangle - readable at 6px.
  void _drawHeart(Canvas canvas, Offset at) {
    final paint = Paint()..color = const Color(0xFFE58FB1);
    canvas.drawCircle(at.translate(-1.7, -1), 2, paint);
    canvas.drawCircle(at.translate(1.7, -1), 2, paint);
    final point = Path()
      ..moveTo(at.dx - 3.5, at.dy - 0.4)
      ..lineTo(at.dx, at.dy + 3.6)
      ..lineTo(at.dx + 3.5, at.dy - 0.4)
      ..close();
    canvas.drawPath(point, paint);
  }

  void _drawButterfly(Canvas canvas, Offset at) {
    final wing = Paint()..color = const Color(0xFFE58FB1).withValues(alpha: 0.9);
    canvas.drawOval(Rect.fromCenter(center: at.translate(-4, 0), width: 8, height: 11), wing);
    canvas.drawOval(Rect.fromCenter(center: at.translate(4, 0), width: 8, height: 11), wing);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: at, width: 2.4, height: 12),
        const Radius.circular(2),
      ),
      Paint()..color = const Color(0xFF5A4632),
    );
  }

  void _drawBird(Canvas canvas, Offset at) {
    final body = Paint()..color = dark ? kTealGlow : kTeal;
    canvas.drawOval(
        Rect.fromCenter(center: at, width: 13, height: 10), body);
    canvas.drawCircle(at.translate(7, -4), 3.6, body);
    // Beak and wing.
    final beak = Path()
      ..moveTo(at.dx + 10, at.dy - 4.5)
      ..lineTo(at.dx + 14, at.dy - 3.5)
      ..lineTo(at.dx + 10, at.dy - 2.5)
      ..close();
    canvas.drawPath(beak, Paint()..color = const Color(0xFFF5B300));
    canvas.drawOval(
      Rect.fromCenter(center: at.translate(-1, -1), width: 7, height: 5),
      Paint()..color = (dark ? kTeal : kTealMid),
    );
  }

  void _drawTurtle(Canvas canvas, Offset at) {
    final shell = Paint()..color = dark ? kTealMid : const Color(0xFF3E8E5A);
    canvas.drawArc(
      Rect.fromCenter(center: at, width: 16, height: 13),
      math.pi, math.pi, true, shell,
    );
    final skin = Paint()..color = dark ? kTealLight : const Color(0xFF6DAF4B);
    canvas.drawCircle(at.translate(9, -2), 2.8, skin); // head
    canvas.drawCircle(at.translate(-6, 1), 1.8, skin); // back leg
    canvas.drawCircle(at.translate(5, 1), 1.8, skin); // front leg
  }

  void _drawFrog(Canvas canvas, Offset at) {
    final body = Paint()..color = dark ? kTealLight : const Color(0xFF5C9E3D);
    canvas.drawOval(
        Rect.fromCenter(center: at, width: 14, height: 9), body);
    canvas.drawCircle(at.translate(-4, -5), 3, body);
    canvas.drawCircle(at.translate(4, -5), 3, body);
    final eye = Paint()..color = const Color(0xFF1B2B1A);
    canvas.drawCircle(at.translate(-4, -5.5), 1.1, eye);
    canvas.drawCircle(at.translate(4, -5.5), 1.1, eye);
  }

  void _drawBee(Canvas canvas, Offset at) {
    // Round striped body with two small wings above.
    final wing = Paint()..color = Colors.white.withValues(alpha: 0.75);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(-3, -6), width: 7, height: 5), wing);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(3, -6), width: 7, height: 5), wing);
    canvas.drawOval(
      Rect.fromCenter(center: at, width: 13, height: 9),
      Paint()..color = const Color(0xFFF5B300),
    );
    final stripe = Paint()
      ..color = const Color(0xFF3A2E1A)
      ..strokeWidth = 2;
    canvas.drawLine(at.translate(-2, -4.5), at.translate(-2, 4.5), stripe);
    canvas.drawLine(at.translate(2.5, -4), at.translate(2.5, 4), stripe);
  }

  void _drawLadybug(Canvas canvas, Offset at) {
    // Red dome shell with spots and a small dark head.
    canvas.drawArc(
      Rect.fromCenter(center: at, width: 14, height: 12),
      math.pi, math.pi, true,
      Paint()..color = const Color(0xFFD8493F),
    );
    canvas.drawCircle(at.translate(8, -1), 2.6,
        Paint()..color = const Color(0xFF2B2B2B));
    final spot = Paint()..color = const Color(0xFF2B2B2B);
    canvas.drawCircle(at.translate(-3, -3), 1.1, spot);
    canvas.drawCircle(at.translate(1, -4.5), 1.1, spot);
    canvas.drawCircle(at.translate(3, -2), 1.1, spot);
  }

  void _drawCat(Canvas canvas, Offset at) {
    // Sitting silhouette: body oval, round head with triangle ears, tail curl.
    final fur = Paint()..color = dark ? kTealMid : const Color(0xFF8A7256);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(0, 1), width: 11, height: 9), fur);
    canvas.drawCircle(at.translate(5, -6), 4, fur);
    final ear = Path()
      ..moveTo(at.dx + 2.2, at.dy - 8.5)
      ..lineTo(at.dx + 3.2, at.dy - 12)
      ..lineTo(at.dx + 4.8, at.dy - 9)
      ..close()
      ..moveTo(at.dx + 5.5, at.dy - 9.2)
      ..lineTo(at.dx + 7, at.dy - 12)
      ..lineTo(at.dx + 8, at.dy - 8.8)
      ..close();
    canvas.drawPath(ear, fur);
    canvas.drawArc(
      Rect.fromCenter(center: at.translate(-7, -1), width: 6, height: 8),
      math.pi / 2, math.pi, false,
      Paint()
        ..color = fur.color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
  }

  void _drawBunny(Canvas canvas, Offset at) {
    // Round body, head, two upright ears, white tail dot.
    final fur = Paint()..color = dark ? kTealLight : const Color(0xFFB9AFA3);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(0, 1), width: 11, height: 9), fur);
    canvas.drawCircle(at.translate(5, -5), 3.6, fur);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(3.5, -11), width: 2.6, height: 8), fur);
    canvas.drawOval(
        Rect.fromCenter(center: at.translate(6.5, -11), width: 2.6, height: 8), fur);
    canvas.drawCircle(
        at.translate(-5.5, 1), 1.6, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant _GardenPainter old) =>
      old.stars != stars ||
      old.masteredCount != masteredCount ||
      old.allQuestsDone != allQuestsDone ||
      old.dark != dark ||
      old.companionKind != companionKind ||
      old.companionCheering != companionCheering ||
      old.season != season;
}
