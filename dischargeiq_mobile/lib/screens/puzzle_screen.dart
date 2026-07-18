/// screens/puzzle_screen.dart
///
/// Medical matching puzzle (gamification wave 4). The patient picks a mood
/// level (easy/medium/hard), then matches items from their own discharge:
/// a medication with its schedule, a visit with its date, the condition with
/// its plain meaning. Every correct match opens a short teaching popup, so a
/// right answer IS a micro-lesson (the app's thesis, as a game).
///
/// Board design: ALL tiles - the "left" prompts and their "right" answers -
/// are mixed into ONE independently shuffled grid, so a tile is never sitting
/// next to its partner. Tap any two tiles that belong together. No timer, no
/// fail, a hint always available. Pure engagement: awards XP only, never the
/// comprehension metric.
library;

import 'dart:math' show Random;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/puzzle.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show HapticFeedback;

/// One face-up tile on the board: which pair it belongs to, whether it is the
/// prompt (left) or answer (right) side, its display text, and - for prompt
/// tiles - the domain kind driving the small icon that tells the patient
/// "this is a thing to match FROM" (answers carry no icon).
class _Tile {
  _Tile({
    required this.pairId,
    required this.isPrompt,
    required this.text,
    this.kind,
  });
  final int pairId;
  final bool isPrompt;
  final String text;
  final PuzzleKind? kind;
}

/// Icon per puzzle domain - shared by prompt tiles and the teach popup.
IconData _kindIcon(PuzzleKind kind) => switch (kind) {
      PuzzleKind.medication => Icons.medication_outlined,
      PuzzleKind.appointment => Icons.event_available_outlined,
      PuzzleKind.diagnosis => Icons.favorite_outline,
    };

class PuzzleScreen extends StatefulWidget {
  const PuzzleScreen({
    super.key,
    required this.extraction,
    required this.diagnosisExplanation,
  });

  final Map<String, dynamic> extraction;
  final String diagnosisExplanation;

  @override
  State<PuzzleScreen> createState() => _PuzzleScreenState();
}

class _PuzzleScreenState extends State<PuzzleScreen> {
  late final List<PuzzlePair> _pool = buildPuzzlePairs(
    widget.extraction,
    diagnosisExplanation: widget.diagnosisExplanation,
  );

  PuzzleLevel? _level;
  List<PuzzlePair> _round = [];
  List<_Tile> _tiles = [];
  final Set<int> _matchedPairs = {}; // pairIds fully matched
  int? _selected; // index into _tiles
  int? _wrongA, _wrongB; // tiles flashing red
  final Set<int> _hinted = {}; // tile indices glowing as a hint
  int _moves = 0;
  int? _bestMoves; // personal best for the chosen level (fewest moves)
  bool _isNewBest = false; // last finished round beat the old best
  final Map<PuzzleLevel, int> _bests = {}; // for the level picker

  @override
  void initState() {
    super.initState();
    for (final l in PuzzleLevel.values) {
      PuzzleScoreStore.best(l.name).then((b) {
        if (b != null && mounted) setState(() => _bests[l] = b);
      });
    }
  }

  /// Fewest possible moves = one correct match per pair (no misses).
  bool get _perfect => _moves == _round.length;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;
  bool get _solved =>
      _round.isNotEmpty && _matchedPairs.length == _round.length;

  void _startLevel(PuzzleLevel level) {
    // Shuffle a copy of the pool before selection so "Play again" rotates in
    // different pairs whenever the document has more than the level needs -
    // repetition is the top patient turn-off in the adherence-app evidence.
    final shuffledPool = List.of(_pool)..shuffle(Random());
    final round = pairsForLevel(shuffledPool, level);
    // Distractor answers (hard only): real right-values from OTHER pool pairs,
    // never fabricated. They have a pairId with no prompt tile, so they can
    // never be matched - they just make the board denser.
    final leftover = shuffledPool
        .where((p) => !round.contains(p))
        .map((p) => p.right)
        .toList();

    final tiles = <_Tile>[];
    for (var i = 0; i < round.length; i++) {
      tiles.add(_Tile(
          pairId: i, isPrompt: true, text: round[i].left, kind: round[i].kind));
      tiles.add(_Tile(pairId: i, isPrompt: false, text: round[i].right));
    }
    for (var d = 0; d < level.distractors && d < leftover.length; d++) {
      tiles.add(_Tile(pairId: -1 - d, isPrompt: false, text: leftover[d]));
    }
    tiles.shuffle(Random());

    setState(() {
      _level = level;
      _round = round;
      _tiles = tiles;
      _matchedPairs.clear();
      _selected = null;
      _wrongA = _wrongB = null;
      _hinted.clear();
      _moves = 0;
      _isNewBest = false;
    });
  }

  Future<void> _tap(int i) async {
    final tile = _tiles[i];
    if (_matchedPairs.contains(tile.pairId)) return; // already solved
    if (_wrongA != null) return; // mid-flash, ignore
    setState(() => _hinted.clear());

    if (_selected == null) {
      setState(() => _selected = i);
      return;
    }
    if (_selected == i) {
      setState(() => _selected = null); // tap again to deselect
      return;
    }

    final first = _tiles[_selected!];
    final second = tile;
    _moves++;
    // A match = same pairId, opposite sides, and a real (non-distractor) pair.
    if (first.pairId == second.pairId &&
        first.isPrompt != second.isPrompt &&
        first.pairId >= 0) {
      HapticFeedback.mediumImpact();
      final pairId = first.pairId;
      setState(() {
        _matchedPairs.add(pairId);
        _selected = null;
      });
      await _showTeach(_round[pairId]);
      if (_solved) await _finish();
    } else {
      HapticFeedback.selectionClick();
      final a = _selected!, b = i;
      setState(() {
        _wrongA = a;
        _wrongB = b;
        _selected = null;
      });
      await Future<void>.delayed(const Duration(milliseconds: 450));
      if (mounted) setState(() => _wrongA = _wrongB = null);
    }
  }

  void _hint() {
    // Glow one still-unmatched real pair (both its tiles).
    for (var p = 0; p < _round.length; p++) {
      if (_matchedPairs.contains(p)) continue;
      final idx = <int>[];
      for (var i = 0; i < _tiles.length; i++) {
        if (_tiles[i].pairId == p) idx.add(i);
      }
      setState(() {
        _selected = null;
        _hinted
          ..clear()
          ..addAll(idx);
      });
      return;
    }
  }

  Future<void> _showTeach(PuzzlePair pair) async {
    final icon = _kindIcon(pair.kind);
    final title = switch (pair.kind) {
      PuzzleKind.medication => 'Medicine matched',
      PuzzleKind.appointment => 'Visit matched',
      PuzzleKind.diagnosis => 'Condition matched',
    };
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: _dark ? kSurfaceDark : kBgLight,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: _dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, color: _dark ? kTealGlow : kTeal, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(title,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                      )),
                ),
              ]),
              const SizedBox(height: 12),
              // The matched pair itself, restated - seeing "name = schedule"
              // again right after the tap is the repetition that teaches.
              Container(
                width: double.infinity,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: _dark ? kTeal.withValues(alpha: 0.12) : kTealPale,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${pair.left}  =  ${pair.right}',
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: _dark ? kTealGlow : kTeal,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Text(pair.teach,
                  style: TextStyle(
                    fontSize: 14.5,
                    height: 1.5,
                    color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                  )),
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: kTeal),
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Keep going'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _finish() async {
    final stats = await GameStore.load();
    stats.xp += kXpQuizFinished;
    await GameStore.save(stats);
    // Return hook: today's finished round banks a bonus the journey card
    // pays off tomorrow (SeedStore keeps the legacy name).
    await SeedStore.plant();
    final isBest = await PuzzleScoreStore.record(_level!.name, _moves);
    final best = await PuzzleScoreStore.best(_level!.name);
    if (mounted) {
      setState(() {
        _isNewBest = isBest;
        _bestMoves = best;
        if (best != null) _bests[_level!] = best;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // Inherits the app-wide flat AppBar theme - the old solid-teal bar was
      // the only screen that broke the design system.
      appBar: AppBar(
        title: const Text('Medicine match'),
        actions: [
          if (_level != null && !_solved)
            TextButton.icon(
              onPressed: _hint,
              icon: const Icon(Icons.lightbulb_outline, size: 18),
              label: const Text('Hint'),
            ),
        ],
      ),
      body: _pool.length < 2
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: Text(
                  'This document does not have enough details to build a '
                  'puzzle yet. Try the Test yourself quiz instead.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : _level == null
              ? _levelPicker()
              : _solved
                  ? _wonView()
                  : _board(),
    );
  }

  Widget _levelPicker() {
    final icons = {
      PuzzleLevel.easy: Icons.spa_outlined,
      PuzzleLevel.medium: Icons.self_improvement_outlined,
      PuzzleLevel.hard: Icons.local_fire_department_outlined,
    };
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Pick how you feel today',
            style: TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w800,
              color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
            )),
        const SizedBox(height: 4),
        Text('Change it any time. There is no wrong choice, and you can never '
            'lose.',
            style: TextStyle(
                fontSize: 13,
                height: 1.4,
                color: _dark ? kTextSecondaryDark : kTextSecondaryLight)),
        const SizedBox(height: 18),
        for (final level in PuzzleLevel.values)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Material(
              color: _dark ? kCardDark : kSurfaceLight,
              borderRadius: BorderRadius.circular(14),
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => _startLevel(level),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color:
                              _dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(icons[level],
                            color: _dark ? kTealGlow : kTeal, size: 22),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(level.label,
                                style: TextStyle(
                                  fontSize: 15.5,
                                  fontWeight: FontWeight.w700,
                                  color: _dark ? kTealGlow : kTeal,
                                )),
                            const SizedBox(height: 2),
                            Text(level.blurb,
                                style: TextStyle(
                                  fontSize: 12.5,
                                  color: _dark
                                      ? kTextSecondaryDark
                                      : kTextSecondaryLight,
                                )),
                            if (_bests[level] != null)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Row(children: [
                                  Icon(Icons.emoji_events_outlined,
                                      size: 13,
                                      color: _dark ? kTealGlow : kTeal),
                                  const SizedBox(width: 4),
                                  Text('Your best: ${_bests[level]} moves',
                                      style: TextStyle(
                                        fontSize: 11.5,
                                        color: _dark ? kTealGlow : kTeal,
                                      )),
                                ]),
                              ),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right,
                          color: _dark ? kTealGlow : kTeal),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _board() {
    final total = _round.length;
    final done = _matchedPairs.length;
    return Column(
      children: [
        // Progress header
        Container(
          width: double.infinity,
          color: _dark ? kSurfaceDark : kTealPale,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Matched $done of $total',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                      )),
                  Text('$_moves ${_moves == 1 ? 'move' : 'moves'}',
                      style: TextStyle(
                        fontSize: 12,
                        color:
                            _dark ? kTextSecondaryDark : kTextSecondaryLight,
                      )),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: total == 0 ? 0 : done / total,
                  minHeight: 6,
                  backgroundColor:
                      _dark ? Colors.white10 : Colors.white,
                  valueColor: AlwaysStoppedAnimation<Color>(
                      _dark ? kTealGlow : kTeal),
                ),
              ),
              const SizedBox(height: 8),
              Text('Tap two tiles that go together.',
                  style: TextStyle(
                    fontSize: 12,
                    color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                  )),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(14),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              alignment: WrapAlignment.center,
              children: [
                for (var i = 0; i < _tiles.length; i++) _tileWidget(i),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _tileWidget(int i) {
    final tile = _tiles[i];
    final matched = _matchedPairs.contains(tile.pairId);
    final selected = _selected == i;
    final wrong = _wrongA == i || _wrongB == i;
    final hinted = _hinted.contains(i);

    final Color bg, fg, border;
    if (matched) {
      bg = _dark ? kTeal.withValues(alpha: 0.18) : kTealPale;
      fg = _dark ? kTextHintDark : kTextHintLight;
      border = bg;
    } else if (wrong) {
      bg = kTier1Bg;
      fg = kTier1;
      border = kTier1;
    } else if (selected) {
      bg = kTeal;
      fg = Colors.white;
      border = kTeal;
    } else if (hinted) {
      bg = _dark ? kCardDark : kCardLight;
      fg = _dark ? kTextPrimaryDark : kTextPrimaryLight;
      border = _dark ? kTealGlow : kTeal;
    } else {
      // Idle tiles are tonal chips - no hairline border (2026 revamp);
      // state borders (selected/hinted/wrong) stay as the interaction signal.
      bg = _dark ? kCardDark : kTealPale.withValues(alpha: 0.4);
      fg = _dark ? kTextPrimaryDark : kTextPrimaryLight;
      border = Colors.transparent;
    }

    return AnimatedScale(
      duration: const Duration(milliseconds: 150),
      scale: selected ? 1.05 : 1,
      child: AnimatedOpacity(
      duration: const Duration(milliseconds: 250),
      opacity: matched ? 0.5 : 1,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 260, minWidth: 90),
        child: Material(
          color: bg,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: matched ? null : () => _tap(i),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                    color: border, width: (selected || hinted || wrong) ? 2 : 0.5),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (matched) ...[
                    const Icon(Icons.check_circle, size: 15, color: kTealMid),
                    const SizedBox(width: 6),
                  ] else if (tile.isPrompt && tile.kind != null) ...[
                    // Domain icon marks "match FROM" tiles so the patient can
                    // tell prompts from answers on a mixed board.
                    Icon(_kindIcon(tile.kind!),
                        size: 15,
                        color: selected
                            ? Colors.white
                            : (_dark ? kTealGlow : kTeal)),
                    const SizedBox(width: 6),
                  ],
                  Flexible(
                    child: Text(
                      tile.text,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        color: fg,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
    );
  }

  Widget _wonView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_perfect ? Icons.workspace_premium : Icons.emoji_events_outlined,
                size: 60, color: _dark ? kTealGlow : kTeal),
            const SizedBox(height: 14),
            Text(_perfect ? 'Perfect round!' : 'You matched them all',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                )),
            const SizedBox(height: 8),
            Text(
              _perfect
                  ? 'Every match on the first try, in $_moves moves. You know '
                      'this plan well.'
                  : 'In $_moves moves - and you learned a little about each one '
                      'along the way.',
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 14,
                  height: 1.4,
                  color: _dark ? kTextSecondaryDark : kTextSecondaryLight),
            ),
            if (_isNewBest) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: _dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text('New personal best',
                    style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: _dark ? kTealGlow : kTeal,
                    )),
              ),
            ] else if (_bestMoves != null) ...[
              const SizedBox(height: 8),
              Text('Your best for this level: $_bestMoves moves',
                  style: TextStyle(
                      fontSize: 12.5,
                      color: _dark ? kTextSecondaryDark : kTextSecondaryLight)),
            ],
            const SizedBox(height: 22),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                      foregroundColor: kTeal,
                      side: const BorderSide(color: kTeal)),
                  onPressed: () => setState(() => _level = null),
                  icon: const Icon(Icons.tune, size: 18),
                  label: const Text('Change level'),
                ),
                const SizedBox(width: 10),
                FilledButton.icon(
                  style: FilledButton.styleFrom(backgroundColor: kTeal),
                  onPressed: () => _startLevel(_level!),
                  icon: const Icon(Icons.refresh, size: 18),
                  label: const Text('Play again'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
