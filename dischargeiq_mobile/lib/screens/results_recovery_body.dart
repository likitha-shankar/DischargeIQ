// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

/// Recovery.
///
/// The redesign (Aug 2026) answers the two questions a patient actually has -
/// "where am I in this?" and "is my weight going the wrong way?" - with a
/// phase rail and a real weight trend, in place of the custom-painted journey
/// trail with its ridge flags and summit star.
///
/// What the original showed is still here: activity and food restrictions,
/// the condition at discharge, and phase text rendered through [PatientText]
/// so the agent's markdown does not leak as asterisks. Phases come from the
/// shared [parseRecoveryPhases] service, so this screen and the journey card
/// on the home page always agree on what week it is.
///
/// The weight series is local-only ([HealthLog]); no backend change.
class _RecoveryBody extends StatefulWidget {
  const _RecoveryBody({required this.trajectory, required this.extraction});

  final String trajectory;
  final dynamic extraction;

  @override
  State<_RecoveryBody> createState() => _RecoveryBodyState();
}

class _RecoveryBodyState extends State<_RecoveryBody> {
  List<WeightEntry> _weights = const [];
  double? _change;

  /// Patient notes and instruction overrides for this document.
  RecoveryEdits _edits = RecoveryEdits.empty;

  /// Which date the timeline is measured from, and where it came from.
  /// Unknown until the async load returns, and unknown for the 67% of real
  /// documents that carry no discharge date at all.
  EffectiveDischargeDate _discharge =
      const EffectiveDischargeDate(source: DischargeDateSource.unknown);

  /// Phase the rail is showing. Null until the first build works out where
  /// today falls, so the patient lands on their own week rather than week 1.
  int? _selected;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final w = await HealthLog.weights(docId);
    final ch = await HealthLog.overnightChange(docId);
    final edits = await RecoveryNotesStore.load(docId);
    final ext = widget.extraction is Map ? widget.extraction as Map : {};
    final discharge = await DischargeDateStore.resolve(
      docId: docId,
      documentValue: '${ext['discharge_date'] ?? ''}',
    );
    if (!mounted) return;
    setState(() {
      _weights = w;
      _change = ch;
      _edits = edits;
      _discharge = discharge;
    });
  }

  /// Ask the patient when they left hospital.
  ///
  /// Bounded to the past year and never the future: recovery is measured
  /// forward from discharge, so a date that has not happened yet produces a
  /// negative elapsed time the timeline discards.
  Future<void> _setDischargeDate() async {
    final docId = _docId;
    if (docId == null) return;
    final today = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _discharge.date ?? today,
      firstDate: DateTime(today.year - 1),
      lastDate: today,
      helpText: 'When did you leave hospital?',
    );
    if (picked == null) return;
    await DischargeDateStore.save(docId, picked);
    await _load();
  }

  /// Put the document's own date back.
  Future<void> _clearDischargeDate() async {
    final docId = _docId;
    if (docId == null) return;
    await DischargeDateStore.clear(docId);
    await _load();
  }

  /// Active document id, or null for a run that was never saved.
  String? get _docId => context.read<DischargeProvider>().activeDocId;

  /// Attach a free-standing note to a phase. Additive: the hospital's text is
  /// untouched, which is why this is the low-friction path.
  Future<void> _addNote(String phase) async {
    final docId = _docId;
    if (docId == null) return;
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => const _NoteDialog(),
    );
    if (text == null || text.trim().isEmpty) return;
    final updated = await RecoveryNotesStore.add(
      docId,
      RecoveryEdit(
        kind: RecoveryEditKind.note,
        phase: phase,
        text: text.trim(),
        createdAt: DateTime.now(),
      ),
    );
    if (mounted) setState(() => _edits = updated);
  }

  /// Override one instruction, as the patient or as a clinician sitting with
  /// them. The original is passed through and stored, never discarded.
  Future<void> _editBullet(String phase, int index, String original) async {
    final docId = _docId;
    if (docId == null) return;
    final result = await showModalBottomSheet<RecoveryEdit>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => RecoveryEditSheet(
        phase: phase,
        bulletIndex: index,
        original: original,
        existing: _edits.overrideFor(phase, index),
      ),
    );
    if (result == null) return;
    final updated = await RecoveryNotesStore.add(docId, result);
    if (mounted) setState(() => _edits = updated);
  }

  /// Put the hospital's wording back by removing the override.
  Future<void> _revertBullet(RecoveryEdit edit) async {
    final docId = _docId;
    if (docId == null) return;
    final updated = await RecoveryNotesStore.remove(docId, edit);
    if (mounted) setState(() => _edits = updated);
  }

  Future<void> _deleteNote(RecoveryEdit note) async {
    final docId = _docId;
    if (docId == null) return;
    final updated = await RecoveryNotesStore.remove(docId, note);
    if (mounted) setState(() => _edits = updated);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final c = SectionColors.of(context);
    final ext = widget.extraction is Map
        ? widget.extraction as Map
        : <dynamic, dynamic>{};

    final activity = _strings(ext['activity_restrictions']);
    final dietary = _strings(ext['dietary_restrictions']);
    final condition = '${ext['discharge_condition'] ?? ''}';

    // Parsed once into every heading-led block, then split: the week-shaped
    // ones drive the rail, and anything else ("When to expect improvement")
    // is advice about the whole recovery, so it renders as its own card
    // rather than as a stray bullet inside whichever week came last.
    final sections = parseRecoverySections(widget.trajectory);
    final phases = weekPhases(sections);
    final extras = phases.isEmpty
        ? const <RecoveryPhase>[]
        : sections.where((s) => s.weekStart == null).toList();
    // Where today actually falls, from the discharge date. The rail opens
    // there and tapping another phase overrides it for the session. Null when
    // the date is missing or unparseable - a real state, not a zero: the
    // original rendered the map without a "you are here" marker rather than
    // guessing, and so does this.
    // Anchored on the RESOLVED date - the patient's correction when they
    // have given one, the document's otherwise. Never the upload date: a
    // summary uploaded two weeks late should place the patient in week
    // three, not restart their recovery.
    final here = phases.isEmpty || !_discharge.isKnown
        ? null
        : currentPhaseIndex(phases, _discharge.isoText);
    final shown = phases.isEmpty
        ? 0
        : (_selected ?? here ?? 0).clamp(0, phases.length - 1);

    return SectionScroll(
      children: [
        const SectionEyebrow('Recovery'),
        const SizedBox(height: 8),
        SectionHeadline(
          switch ((phases.isEmpty, here)) {
            (true, _) => 'How your recovery should go.',
            (false, final int i) => 'You are in ${phases[i].title.toLowerCase()} '
                'of ${phases.length == 1 ? 'one phase' : 'about ${phases.length} phases'}.',
            // Phases exist but the discharge date does not place the patient
            // in one. Describe the shape without claiming to know the week.
            _ => 'Your recovery runs in '
                '${phases.length == 1 ? 'one phase' : '${phases.length} phases'}.',
          },
          size: 22,
        ),
        const SizedBox(height: 14),
        // Above the rail, because without a date the rail cannot place the
        // patient at all - and that is the case for two thirds of real
        // documents, not an edge case.
        if (phases.isNotEmpty) ...[
          _DischargeDateCard(
            discharge: _discharge,
            onSet: _setDischargeDate,
            onClear: _clearDischargeDate,
          ),
          const SizedBox(height: 12),
        ],
        _WeightCard(weights: _weights, change: _change, onLog: _logWeight),
        const SizedBox(height: 12),
        if (phases.isNotEmpty) ...[
          SectionCard(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _PhaseRail(
                  phases: phases,
                  selected: shown,
                  here: here,
                  onSelect: (i) => setState(() => _selected = i),
                ),
                const SizedBox(height: 12),
                Divider(height: 1, color: c.lineSoft),
                const SizedBox(height: 12),
                // Looking at a week that is not the current one is easy to do
                // by accident and easy to forget. Say so in words, and offer
                // the way back, rather than relying on the rail alone.
                if (here != null && shown != here) ...[
                  _PreviewBanner(
                    label: phases[here].title,
                    ahead: shown > here,
                    onBack: () => setState(() => _selected = here),
                  ),
                  const SizedBox(height: 10),
                ],
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        phases[shown].title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: c.text,
                        ),
                      ),
                    ),
                    // Adding a note is the safe, additive action, so it is
                    // the one on the surface. Changing the hospital's own
                    // wording lives behind a long-press on the line itself.
                    TextButton.icon(
                      onPressed: () => _addNote(phases[shown].title),
                      icon: const Icon(Icons.add_comment_outlined, size: 17),
                      label: const Text('Add note'),
                      style: TextButton.styleFrom(
                        foregroundColor: c.accent,
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                _Bullets(
                  bullets: phases[shown].bullets,
                  phase: phases[shown].title,
                  edits: _edits,
                  onEdit: _editBullet,
                  onRevert: _revertBullet,
                ),
                _PhaseNotes(
                  notes: _edits.notesFor(phases[shown].title),
                  onDelete: _deleteNote,
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Advice that belongs to the recovery rather than to one week.
          for (final extra in extras) ...[
            SectionCard(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    extra.title,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: c.text,
                    ),
                  ),
                  const SizedBox(height: 6),
                  _Bullets(bullets: extra.bullets),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],
        ] else if (widget.trajectory.trim().isNotEmpty) ...[
          // Prose that did not parse into phases. Shown whole rather than
          // forced into a timeline the document never gave.
          SectionCard(
            child: PatientText(text: widget.trajectory, collapsible: true),
          ),
          const SizedBox(height: 12),
        ] else ...[
          const EmptySection(
            icon: Icons.timeline_outlined,
            title: 'No recovery timeline',
            message:
                'Your document did not describe what to expect week by week. '
                'Ask your care team how long recovery usually takes and what '
                'you can do in the meantime.',
          ),
          const SizedBox(height: 12),
        ],
        // Restrictions: the rules that apply for the whole recovery, not to
        // one phase, so they sit below the rail rather than inside it.
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
          SectionCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            color: c.accentTint,
            border: Colors.transparent,
            child: Text.rich(
              TextSpan(
                style: TextStyle(fontSize: 13, height: 1.45, color: c.text),
                children: [
                  const TextSpan(
                    text: 'Condition at discharge: ',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  TextSpan(text: condition),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }

  /// A JSON list field as clean strings; anything else as an empty list.
  List<String> _strings(dynamic raw) => raw is List
      ? raw.map((e) => '$e').where((e) => e.trim().isNotEmpty).toList()
      : const [];

  Future<void> _logWeight() async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final value = await showDialog<double>(
      context: context,
      builder: (ctx) => const _WeightDialog(),
    );
    if (value == null) return;
    await HealthLog.logWeight(docId, value);
    await _load();
    if (!mounted) return;
    final ch = _change;
    if (ch != null && ch >= 3) {
      // The paperwork's own rule: +3 lb overnight is an ER-today sign.
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.warning_amber_rounded, color: sdWarn, size: 32),
          title: const Text('That is a big jump'),
          content: Text(
            'You are up ${ch.toStringAsFixed(1)} lb since your last reading. '
            'Your discharge papers say a rise of 3 lb in a day means go to '
            'the ER today - it is fluid, not fat. Do not wait for your next '
            'appointment.',
            style: const TextStyle(height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Understood'),
            ),
          ],
        ),
      );
    }
  }
}

/// Asks for, or reports, the date the recovery timeline is measured from.
///
/// Three states, and the first is the common one: measured on the corpus,
/// **only 35 of 106 documents (33%) carry a discharge date**. Without one the
/// rail draws the shape of a recovery with the patient nowhere in it - no
/// "you are here", no week position, and the looking-ahead banner can never
/// fire. Asking for it is the difference between the feature working for a
/// third of patients and working for all of them.
class _DischargeDateCard extends StatelessWidget {
  const _DischargeDateCard({
    required this.discharge,
    required this.onSet,
    required this.onClear,
  });

  final EffectiveDischargeDate discharge;
  final VoidCallback onSet;
  final VoidCallback onClear;

  static const _months = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  String _pretty(DateTime d) => '${_months[d.month]} ${d.day}, ${d.year}';

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);

    if (!discharge.isKnown) {
      // The prompt. Framed as the app not knowing rather than the document
      // being deficient - a patient did not write their own paperwork and
      // should not read a gap in it as their failure.
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: sdWarnTint,
          borderRadius: BorderRadius.circular(kRadiusField),
          border: Border.all(color: sdWarnLine),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'When did you leave hospital?',
              style: TextStyle(
                  fontSize: 14.5, fontWeight: FontWeight.w700, color: sdWarnInk),
            ),
            const SizedBox(height: 4),
            const Text(
              'Your paperwork did not give a date. Tell us, and we can show '
              'you which week of your recovery you are in.',
              style: TextStyle(fontSize: 13, height: 1.4, color: sdWarnInk),
            ),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                onPressed: onSet,
                icon: const Icon(Icons.event_outlined, size: 18),
                label: const Text('Set the date'),
              ),
            ),
          ],
        ),
      );
    }

    final byPatient = discharge.source == DischargeDateSource.patient;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: byPatient ? sdWarnTint : c.accentTint,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border.all(color: byPatient ? sdWarnLine : Colors.transparent),
      ),
      child: Row(
        children: [
          Icon(Icons.event_available_outlined,
              size: 17, color: byPatient ? sdWarnInk : c.accent),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'You left hospital on ${_pretty(discharge.date!)}',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.35,
                    fontWeight: FontWeight.w600,
                    color: byPatient ? sdWarnInk : c.text,
                  ),
                ),
                if (byPatient)
                  Text(
                    discharge.correctsTheDocument
                        ? 'You changed this. Your document said '
                            '${discharge.documentValue}'
                        : 'You told us this',
                    style: const TextStyle(fontSize: 11.5, color: sdWarnInk),
                  ),
              ],
            ),
          ),
          TextButton(
            onPressed: byPatient ? onClear : onSet,
            style: TextButton.styleFrom(
              visualDensity: VisualDensity.compact,
              foregroundColor: byPatient ? sdWarnInk : c.accent,
            ),
            child: Text(byPatient ? 'Undo' : 'Change'),
          ),
        ],
      ),
    );
  }
}

/// A phase or section's lines, one dot each.
///
/// Each line goes through [PatientText] rather than a bare [Text]: the agent
/// writes markdown, and rendering it raw put asterisks on screen.
class _Bullets extends StatelessWidget {
  const _Bullets({
    required this.bullets,
    this.phase = '',
    this.edits = RecoveryEdits.empty,
    this.onEdit,
    this.onRevert,
  });

  final List<String> bullets;

  /// Phase these lines belong to; '' for the read-only extras cards.
  final String phase;
  final RecoveryEdits edits;

  /// (phase, index, original) -> open the edit sheet. Null makes the list
  /// read-only, which is what the whole-recovery advice cards want.
  final void Function(String phase, int index, String original)? onEdit;
  final void Function(RecoveryEdit edit)? onRevert;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    final editable = onEdit != null && phase.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < bullets.length; i++)
          Builder(builder: (context) {
            final override = editable ? edits.overrideFor(phase, i) : null;
            final shown = override?.text ?? bullets[i];
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: GestureDetector(
                // Long-press, not a visible pencil on every line: changing
                // clinical wording should take intent, and a row of edit
                // icons invites it as casually as ticking a box.
                onLongPress: editable
                    ? () => onEdit!(phase, i, bullets[i])
                    : null,
                behavior: HitTestBehavior.opaque,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 5,
                          height: 5,
                          margin: const EdgeInsets.only(top: 8, right: 9),
                          decoration: BoxDecoration(
                            // A changed line is marked at the bullet too, so
                            // it reads as different at a glance and not only
                            // once the label underneath is read.
                            color: override == null ? c.accent : sdWarn,
                            shape: BoxShape.circle,
                          ),
                        ),
                        Expanded(
                            child: PatientText(text: shown, fontSize: 13.5)),
                      ],
                    ),
                    // The provenance line. This is the safety requirement:
                    // altered text must never sit on the page looking like
                    // what the hospital wrote.
                    if (override != null)
                      Padding(
                        padding: const EdgeInsets.only(left: 14, top: 2),
                        child: Wrap(
                          crossAxisAlignment: WrapCrossAlignment.center,
                          spacing: 8,
                          children: [
                            Text(
                              override.attribution,
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: sdWarnInk,
                              ),
                            ),
                            _TinyAction(
                              label: 'See original',
                              onTap: () => _showOriginal(context, override),
                            ),
                            if (onRevert != null)
                              _TinyAction(
                                label: 'Undo',
                                onTap: () => onRevert!(override),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  /// Show what the discharge document actually said, verbatim.
  void _showOriginal(BuildContext context, RecoveryEdit edit) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('What your document says'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(edit.original ?? '',
                style: const TextStyle(height: 1.5, fontSize: 14)),
            const SizedBox(height: 14),
            Text(edit.attribution,
                style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: sdWarnInk)),
            const SizedBox(height: 4),
            Text(edit.text,
                style: const TextStyle(height: 1.5, fontSize: 14)),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

/// A small inline text action, sized for a caption row rather than a button.
class _TinyAction extends StatelessWidget {
  const _TinyAction({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: SectionColors.of(context).accent,
          decoration: TextDecoration.underline,
        ),
      ),
    );
  }
}

/// "You are in week 2 - this is week 5" plus the way back.
class _PreviewBanner extends StatelessWidget {
  const _PreviewBanner({
    required this.label,
    required this.ahead,
    required this.onBack,
  });

  final String label;

  /// Looking forward rather than back. Worth distinguishing: reading ahead is
  /// a patient checking what is coming, reading back is usually a mis-tap.
  final bool ahead;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: sdWarnTint,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border.all(color: sdWarnLine),
      ),
      child: Row(
        children: [
          const Icon(Icons.visibility_outlined, size: 15, color: sdWarnInk),
          const SizedBox(width: 7),
          Expanded(
            child: Text(
              ahead
                  ? 'Looking ahead. You are in $label right now.'
                  : 'Looking back. You are in $label right now.',
              style: const TextStyle(fontSize: 12, color: sdWarnInk),
            ),
          ),
          TextButton(
            onPressed: onBack,
            style: TextButton.styleFrom(
              foregroundColor: sdWarnInk,
              visualDensity: VisualDensity.compact,
            ),
            child: const Text('Go back'),
          ),
        ],
      ),
    );
  }
}

/// The patient's own notes on a phase, kept visually apart from the
/// document's instructions so the two are never confused.
class _PhaseNotes extends StatelessWidget {
  const _PhaseNotes({required this.notes, required this.onDelete});

  final List<RecoveryEdit> notes;
  final void Function(RecoveryEdit) onDelete;

  @override
  Widget build(BuildContext context) {
    if (notes.isEmpty) return const SizedBox.shrink();
    final c = SectionColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: c.accentTint,
          borderRadius: BorderRadius.circular(kRadiusField),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'YOUR NOTES',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.8,
                color: c.accent,
              ),
            ),
            const SizedBox(height: 6),
            for (final note in notes)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        note.text,
                        style: TextStyle(
                            fontSize: 13, height: 1.4, color: c.text),
                      ),
                    ),
                    GestureDetector(
                      onTap: () => onDelete(note),
                      child: Padding(
                        padding: const EdgeInsets.only(left: 8, top: 2),
                        child: Icon(Icons.close,
                            size: 15, color: c.textMute),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Plain single-field dialog for adding a note.
class _NoteDialog extends StatefulWidget {
  const _NoteDialog();

  @override
  State<_NoteDialog> createState() => _NoteDialogState();
}

class _NoteDialogState extends State<_NoteDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add a note'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        maxLines: 3,
        textCapitalization: TextCapitalization.sentences,
        decoration: const InputDecoration(
          hintText: 'Something you want to remember for this week',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _controller.text),
          child: const Text('Save'),
        ),
      ],
    );
  }
}

/// The week rail: every phase visible at once, the current one filled.
///
/// Bars grow left to right so the shape reads as progress rather than as a
/// chart of some quantity - there is no quantity here, only order.
class _PhaseRail extends StatelessWidget {
  const _PhaseRail({
    required this.phases,
    required this.selected,
    required this.here,
    required this.onSelect,
  });

  final List<RecoveryPhase> phases;
  final int selected;

  /// Where TODAY falls, independent of what the patient has tapped. Null when
  /// the discharge date is missing or unparseable.
  ///
  /// The rail used to colour everything off [selected] alone, so tapping
  /// ahead to see what week 6 holds made week 6 look like the current week
  /// and erased any marker of the real one. Time and selection are now two
  /// different visual channels: fill says WHEN, outline says WHAT YOU TAPPED.
  final int? here;

  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    // The rail carries a text label above each bar, so its height has to
    // follow the text. At 2.2x scaling a fixed 62px box clipped the week
    // labels, which are the only thing that says which phase you are on.
    final scale = MediaQuery.textScalerOf(context).scale(1.0);
    return SizedBox(
      // 62 for the label + bar, plus 11 for the "NOW" marker row that sits
      // above every column so the bars stay aligned across the rail.
      height: 73 + (scale - 1.0) * 22,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < phases.length; i++)
            Expanded(
              child: Semantics(
                selected: i == selected,
                button: true,
                // Screen readers get the same two facts the colours carry.
                // "Week 3, this week" is the whole point of the rail, and it
                // was previously available only to sighted users.
                label: switch ((i == here, i == selected)) {
                  (true, true) => '${phases[i].title}, this week',
                  (true, false) => '${phases[i].title}, this week, not shown',
                  (false, true) => '${phases[i].title}, showing',
                  _ => phases[i].title,
                },
                child: GestureDetector(
                  onTap: () => onSelect(i),
                  behavior: HitTestBehavior.opaque,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2.5),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        // "Now" rides above the current week's bar so the
                        // marker survives tapping to any other phase.
                        SizedBox(
                          height: 11,
                          child: i == here
                              ? Text(
                                  'NOW',
                                  style: TextStyle(
                                    fontSize: 8,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: 0.5,
                                    color: c.accent,
                                  ),
                                )
                              : null,
                        ),
                        Text(
                          phases[i].title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 9.5,
                            fontWeight:
                                i == here ? FontWeight.w800 : FontWeight.w600,
                            color: (i == here || i == selected)
                                ? c.accent
                                : c.textMute,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          height: 14.0 + (30.0 * (i + 1) / phases.length),
                          decoration: BoxDecoration(
                            // Fill = time. Weeks already lived are solid but
                            // muted, the current week is the strongest colour
                            // on the rail, and weeks ahead stay empty.
                            // Colour never moves when the patient taps.
                            color: switch (here) {
                              final int h when i == h => sdTeal,
                              final int h when i < h => sdTealGlow,
                              // No known current week: fall back to showing
                              // shape only, rather than implying a position
                              // the discharge date never gave us.
                              null => c.lineSoft,
                              _ => c.lineSoft,
                            },
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(7),
                              bottom: Radius.circular(3),
                            ),
                            // Outline = selection. A separate channel from
                            // fill, so "what I tapped" can never overwrite
                            // "where I am".
                            border: i == selected
                                ? Border.all(color: c.accent, width: 2)
                                : null,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
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
      // Full bleed: a short gap question must not draw a narrower
      // tinted card than the one above it.
      width: double.infinity,
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


