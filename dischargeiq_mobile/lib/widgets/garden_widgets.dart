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

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/quests.dart';
import 'package:flutter/material.dart';

/// Card shown on the landing page: garden painting + quest progress rows.
class RecoveryGardenCard extends StatelessWidget {
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
  Widget build(BuildContext context) {
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
          Text(
            'YOUR RECOVERY GARDEN',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.6,
              color: dark ? kTealGlow : kTeal,
            ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: CustomPaint(
              painter: _GardenPainter(
                stars: stars,
                masteredCount: trees,
                allQuestsDone: quests.every((q) => q.complete),
                dark: dark,
              ),
              child: const SizedBox(width: double.infinity, height: 130),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '$flowers of ${kAllStarKeys.length} flowers blooming'
            '${trees > 0 ? ' · $trees tree${trees == 1 ? '' : 's'} grown' : ''}',
            style: TextStyle(
              fontSize: 11,
              color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            ),
          ),
          const SizedBox(height: 12),
          _DailyCheckin(dark: dark),
          for (final q in quests) _QuestRow(quest: q, dark: dark),
        ],
      ),
    );
  }
}

/// Once-a-day mood check-in (wave 3). Design rules: one question, three big
/// answers, kind response, done. No streaks, no guilt for missed days, and
/// a rough day gets acknowledgment plus a gentle safety pointer - never a
/// cheerful dismissal.
class _DailyCheckin extends StatefulWidget {
  const _DailyCheckin({required this.dark});

  final bool dark;

  @override
  State<_DailyCheckin> createState() => _DailyCheckinState();
}

class _DailyCheckinState extends State<_DailyCheckin> {
  bool? _doneToday; // null while loading
  String? _justAnswered;
  int _totalDays = 0;

  @override
  void initState() {
    super.initState();
    CheckinStore.doneToday().then((done) async {
      final total = (await CheckinStore.load()).length;
      if (mounted) {
        setState(() {
          _doneToday = done;
          _totalDays = total;
        });
      }
    });
  }

  Future<void> _answer(String mood) async {
    final total = await CheckinStore.record(mood);
    if (!mounted) return;
    setState(() {
      _justAnswered = mood;
      _doneToday = true;
      _totalDays = total;
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
          _ => 'Rough days are part of recovery. If something feels wrong, '
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

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: dark ? kTeal.withValues(alpha: 0.18) : const Color(0xFFF0FAF5),
          borderRadius: BorderRadius.circular(10),
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

/// Paints the garden: sky, sun, soil, 5 back-row trees, 6 front-row flowers,
/// optional butterfly. Deterministic layout - same state, same picture.
class _GardenPainter extends CustomPainter {
  _GardenPainter({
    required this.stars,
    required this.masteredCount,
    required this.allQuestsDone,
    required this.dark,
  });

  final Set<String> stars;
  final int masteredCount;
  final bool allQuestsDone;
  final bool dark;

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

    // Sky.
    final sky = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: dark
            ? const [Color(0xFF06302A), Color(0xFF0A3D2E)]
            : const [Color(0xFFEAF7F1), Color(0xFFF7FAF8)],
      ).createShader(Rect.fromLTWH(0, 0, w, h));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h), sky);

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

    // Front row: 6 flowers (stars), in kAllStarKeys order.
    for (var i = 0; i < kAllStarKeys.length; i++) {
      final x = w * (0.08 + 0.168 * i);
      _drawFlower(canvas, Offset(x, soilTop + 6), i,
          bloomed: stars.contains(kAllStarKeys[i]));
    }

    if (allQuestsDone) _drawButterfly(canvas, Offset(w * 0.32, 30));
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
      final canopy = Paint()..color = dark ? kTealMid : kTeal;
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

  @override
  bool shouldRepaint(covariant _GardenPainter old) =>
      old.stars != stars ||
      old.masteredCount != masteredCount ||
      old.allQuestsDone != allQuestsDone ||
      old.dark != dark;
}
