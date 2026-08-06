/// widgets/learning_goal_sheet.dart
///
/// The "what do you want to learn?" moment (clinical review, Aug 2026).
/// Two sheets over the same store:
///
///   showLearningGoalSheet  - pick the topics that matter to you, then rate
///                            how well you understand each one right now.
///   showGoalRecheckSheet   - after reading, rate the same topics again.
///
/// The gap between those two ratings is the outcome the goals feature is
/// measured by, and it is the patient's own judgement rather than a score the
/// app assigns - see services/learning_goals.dart for the rubric.
///
/// Design rules from docs/GAMIFICATION_STRATEGY.md apply: skipping is a valid
/// answer, nothing is required, and no wording implies failure.
library;

import 'package:flutter/material.dart';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/learning_goals.dart';

/// Ask the patient which topics they want to focus on, then rate each.
///
/// Returns the chosen goal ids (empty when they skip). Persists both the
/// goals and the "already asked" flag, so callers can show this exactly once
/// per document without tracking that themselves.
///
/// Args:
///   context: Build context for the modal sheet.
///   docId:   Saved-document id these goals belong to.
Future<List<String>> showLearningGoalSheet({
  required BuildContext context,
  required String docId,
}) async {
  final chosen = await showModalBottomSheet<List<String>>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) => _GoalPicker(docId: docId),
  );
  // A dismissed sheet is still an answer - record it so the patient is not
  // asked again every time they open the document.
  if (chosen == null) {
    await LearningGoalStore.save(docId, const []);
    return const [];
  }
  return chosen;
}

/// Re-rate goals after reading. Returns true when anything was rated.
///
/// Shown from the journey card rather than automatically: asking "do you get
/// it now?" unprompted, straight after someone reads a section, would read as
/// a test rather than an offer.
Future<bool> showGoalRecheckSheet({
  required BuildContext context,
  required String docId,
  required List<String> goalIds,
}) async {
  if (goalIds.isEmpty) return false;
  final rated = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) => _GoalRatingSheet(
      docId: docId,
      goalIds: goalIds,
      phase: 'post',
      title: 'How well do you know these now?',
      intro: 'Same question as before. Be honest - saying "not yet" is how '
          'you find out what to go over again.',
    ),
  );
  return rated ?? false;
}

/// Step one: choose topics.
class _GoalPicker extends StatefulWidget {
  const _GoalPicker({required this.docId});

  final String docId;

  @override
  State<_GoalPicker> createState() => _GoalPickerState();
}

class _GoalPickerState extends State<_GoalPicker> {
  final Set<String> _selected = {};

  @override
  void initState() {
    super.initState();
    // Reopened from the app bar: start from what they already chose, so
    // "change my goals" is an edit rather than starting over.
    LearningGoalStore.load(widget.docId).then((existing) {
      if (mounted && existing.isNotEmpty) {
        setState(() => _selected.addAll(existing));
      }
    });
  }

  Future<void> _continue() async {
    final ids = [
      for (final g in kLearningGoals)
        if (_selected.contains(g.id)) g.id,
    ];
    await LearningGoalStore.save(widget.docId, ids);
    if (!mounted) return;
    // Straight into the starting self-rating: asking "how well do you know
    // this?" is only meaningful before they have read the answer.
    final navigator = Navigator.of(context);
    if (ids.isNotEmpty) {
      await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (ctx) => _GoalRatingSheet(
          docId: widget.docId,
          goalIds: ids,
          phase: 'pre',
          title: 'Where are you with these right now?',
          intro: 'Before you read anything. There is no wrong answer, and '
              'nobody else sees this.',
        ),
      );
    }
    navigator.pop(ids);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'What do you most want to understand?',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Pick as many as you like. Your journey will start with these. '
              'You can still read everything else.',
              style: TextStyle(
                fontSize: 13,
                height: 1.35,
                color: dark ? kTextHintDark : kTextHintLight,
              ),
            ),
            const SizedBox(height: 14),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final goal in kLearningGoals)
                    _GoalTile(
                      goal: goal,
                      selected: _selected.contains(goal.id),
                      dark: dark,
                      onTap: () => setState(() {
                        if (!_selected.remove(goal.id)) _selected.add(goal.id);
                      }),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: kTeal,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                onPressed: _selected.isEmpty ? null : _continue,
                child: Text(
                  _selected.isEmpty
                      ? 'Choose at least one'
                      : 'Start with ${_selected.length == 1 ? 'this' : 'these'}',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w700),
                ),
              ),
            ),
            // Skipping must stay as easy as choosing. Someone who wants to
            // read the whole thing in order is not doing it wrong.
            TextButton(
              onPressed: () => Navigator.pop(context, const <String>[]),
              child: Text(
                'Show me everything instead',
                style: TextStyle(
                  fontSize: 13,
                  color: dark ? kTextHintDark : kTextHintLight,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One selectable topic row.
class _GoalTile extends StatelessWidget {
  const _GoalTile({
    required this.goal,
    required this.selected,
    required this.dark,
    required this.onTap,
  });

  final LearningGoal goal;
  final bool selected;
  final bool dark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = dark ? kTealGlow : kTeal;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: selected ? accent : (dark ? kCardDark : kBorderLight),
              width: selected ? 1.6 : 1,
            ),
            color: selected
                ? accent.withValues(alpha: dark ? 0.14 : 0.07)
                : Colors.transparent,
          ),
          child: Row(
            children: [
              Icon(
                selected
                    ? Icons.check_circle_rounded
                    : Icons.radio_button_unchecked,
                size: 22,
                color: selected ? accent : (dark ? kTextHintDark : kTextHintLight),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      goal.label,
                      style: TextStyle(
                        fontSize: 14.5,
                        fontWeight: FontWeight.w700,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      goal.prompt,
                      style: TextStyle(
                        fontSize: 12.5,
                        height: 1.3,
                        color: dark ? kTextHintDark : kTextHintLight,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Step two (and the later re-check): rate each chosen goal on the rubric.
class _GoalRatingSheet extends StatefulWidget {
  const _GoalRatingSheet({
    required this.docId,
    required this.goalIds,
    required this.phase,
    required this.title,
    required this.intro,
  });

  final String docId;
  final List<String> goalIds;

  /// 'pre' at goal-setting, 'post' at the re-check.
  final String phase;
  final String title;
  final String intro;

  @override
  State<_GoalRatingSheet> createState() => _GoalRatingSheetState();
}

class _GoalRatingSheetState extends State<_GoalRatingSheet> {
  final Map<String, int> _levels = {};

  @override
  void initState() {
    super.initState();
    // Pre-fill from whatever is already stored for this phase so a re-opened
    // sheet shows the patient's last answer instead of an empty form.
    LearningGoalStore.ratings(widget.docId, widget.phase).then((stored) {
      if (mounted && stored.isNotEmpty) setState(() => _levels.addAll(stored));
    });
  }

  Future<void> _save() async {
    for (final entry in _levels.entries) {
      await LearningGoalStore.rate(
          widget.docId, entry.key, widget.phase, entry.value);
    }
    if (mounted) Navigator.pop(context, _levels.isNotEmpty);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final goals = [
      for (final id in widget.goalIds)
        if (goalById(id) != null) goalById(id)!,
    ];
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.title,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              widget.intro,
              style: TextStyle(
                fontSize: 13,
                height: 1.35,
                color: dark ? kTextHintDark : kTextHintLight,
              ),
            ),
            const SizedBox(height: 14),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final goal in goals)
                    _RubricRow(
                      goal: goal,
                      level: _levels[goal.id],
                      dark: dark,
                      onPick: (v) => setState(() => _levels[goal.id] = v),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: kTeal,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                onPressed: _levels.isEmpty ? null : _save,
                child: const Text('Save',
                    style:
                        TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One goal's rubric row: the four levels as tappable chips.
class _RubricRow extends StatelessWidget {
  const _RubricRow({
    required this.goal,
    required this.level,
    required this.dark,
    required this.onPick,
  });

  final LearningGoal goal;
  final int? level;
  final bool dark;
  final ValueChanged<int> onPick;

  @override
  Widget build(BuildContext context) {
    final accent = dark ? kTealGlow : kTeal;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            goal.label,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final rung in kUnderstandingLevels)
                InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => onPick(rung.value),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 7),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: level == rung.value
                            ? accent
                            : (dark ? kCardDark : kBorderLight),
                        width: level == rung.value ? 1.6 : 1,
                      ),
                      color: level == rung.value
                          ? accent.withValues(alpha: dark ? 0.16 : 0.08)
                          : Colors.transparent,
                    ),
                    child: Text(
                      rung.label,
                      style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: level == rung.value
                            ? FontWeight.w700
                            : FontWeight.w500,
                        color: level == rung.value
                            ? accent
                            : (dark ? kTextPrimaryDark : kTextPrimaryLight),
                      ),
                    ),
                  ),
                ),
            ],
          ),
          if (level != null) ...[
            const SizedBox(height: 4),
            Text(
              kUnderstandingLevels[level!].blurb,
              style: TextStyle(
                fontSize: 12,
                fontStyle: FontStyle.italic,
                color: dark ? kTextHintDark : kTextHintLight,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
