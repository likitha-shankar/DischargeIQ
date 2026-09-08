// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _AppointmentsBody extends StatefulWidget {
  const _AppointmentsBody({required this.extraction, this.simulator});

  final dynamic extraction;

  /// Agent 6 output - its unanswered questions become the visit-prep list.
  final dynamic simulator;

  @override
  State<_AppointmentsBody> createState() => _AppointmentsBodyState();
}

class _AppointmentsBodyState extends State<_AppointmentsBody> {
  /// Appointment keys the patient has ticked off, for the active document.
  /// Empty until the async load returns; the tab renders fine meanwhile.
  Set<String> _done = const {};

  /// Corrections, indexed by the ORIGINAL appointment key. Both this and
  /// [_done] are keyed off the document's values, so an edited date cannot
  /// detach either one - see appointment_edits.dart.
  Map<String, AppointmentEdit> _edits = const {};

  dynamic get extraction => widget.extraction;
  dynamic get simulator => widget.simulator;

  @override
  void initState() {
    super.initState();
    _loadDone();
  }

  Future<void> _loadDone() async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final done = await AppointmentStatusStore.load(docId);
    final edits = await AppointmentEditsStore.load(docId);
    if (mounted) {
      setState(() {
        _done = done;
        _edits = edits;
      });
    }
  }

  /// Correct one appointment. [original] is the document's version - the
  /// sheet shows those values as the reference, and the store keys the edit
  /// by them.
  Future<void> _editAppointment(Map original) async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final key = appointmentKey(original);
    final changes = await showModalBottomSheet<Map<String, String>>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => AppointmentEditSheet(
        appointment: original,
        existing: _edits[key],
      ),
    );
    if (changes == null || changes.isEmpty) return;
    final updated = await AppointmentEditsStore.save(
      docId: docId,
      original: original,
      changes: changes,
    );
    if (mounted) setState(() => _edits = updated);
  }

  /// Put the document's own details back.
  Future<void> _revertAppointment(String originalKey) async {
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final updated = await AppointmentEditsStore.remove(docId, originalKey);
    if (mounted) setState(() => _edits = updated);
  }

  /// Toggle one appointment between done and not done.
  ///
  /// Reversible on purpose: a patient who taps the wrong row must be able to
  /// put it back, and an irreversible tick makes people avoid the control.
  /// An unsaved run has no document id and simply does not persist.
  Future<void> _toggleDone(Map appointment, bool done) async {
    final key = appointmentKey(appointment);
    if (key.isEmpty) return;
    final updated = {..._done};
    if (done) {
      updated.add(key);
    } else {
      updated.remove(key);
    }
    // Optimistic: the tick responds immediately and the write follows. A
    // failed write loses a cosmetic mark, never a tap the patient can see.
    setState(() => _done = updated);
    final docId = context.mounted
        ? context.read<DischargeProvider>().activeDocId
        : null;
    if (docId == null) return;
    if (done) {
      await AppointmentStatusStore.markDone(docId, appointment);
    } else {
      await AppointmentStatusStore.markNotDone(docId, appointment);
    }
  }

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
    // Per-document star; an unsaved run has no id and earns nothing.
    final docId = context.read<DischargeProvider>().activeDocId;
    if (docId == null) return;
    final isNew = await SectionStarStore.award(docId, kCalendarStarKey);
    if (!isNew || !context.mounted) return;
    final earned = (await SectionStarStore.load(docId)).length;
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
    const hero = _SectionHero(
      icon: Icons.event_available_outlined,
      title: 'Your appointments',
      subtitle: 'Follow-ups from your paperwork, soonest first',
    );
    if (list == null || list.isEmpty) {
      final dark0 = Theme.of(context).brightness == Brightness.dark;
      return ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 110), children: [
        hero,
        const EmptySection(
          icon: Icons.event_available_outlined,
          title: 'No appointments listed',
          message:
              'Your document did not name a follow-up visit. Most people still '
              'need one. Call your doctor to ask whether you should book a '
              'check-up, and how soon.',
        ),
        if (questions.isNotEmpty) _VisitPrepCard(questions: questions, dark: dark0),
      ]);
    }
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      itemCount: 1 + list.length + (questions.isEmpty ? 0 : 1),
      itemBuilder: (context, i) {
        if (i == 0) return hero;
        // Visit-prep card renders after the appointment list.
        if (i == list.length + 1) {
          return _VisitPrepCard(questions: questions, dark: dark);
        }
        final a = list[i - 1];
        if (a is! Map) return const SizedBox.shrink();
        // Key and tick come from the DOCUMENT's values; the card shows the
        // merged version. Keying off the merged map would move the key the
        // moment a date was corrected.
        final key = appointmentKey(a);
        final edit = _edits[key];
        final shown = applyAppointmentEdit(a, edit);
        return _AppointmentCard(
          appointment: shown,
          dark: dark,
          // Past-ness follows the CORRECTED date - a visit moved to next week
          // is not history just because the document's date has passed.
          isPast: isAppointmentPast(shown),
          isDone: key.isNotEmpty && _done.contains(key),
          canMark: key.isNotEmpty,
          edit: edit,
          onAddToCalendar: () => _addToCalendar(context, shown),
          onToggleDone: (v) => _toggleDone(a, v),
          onEdit: key.isEmpty ? null : () => _editAppointment(a),
          onRevert: edit == null ? null : () => _revertAppointment(key),
        );
      },
    );
  }
}

/// One follow-up visit, laid out so the three things a patient actually needs
/// - WHEN, WHO, WHY - are each labelled and separable at a glance.
///
/// The previous card put the date in a small trailing chip that read "TBD"
/// when the document gave no date, merged provider and reason into one
/// unlabelled block, and left the reader to work out which line was which.
class _AppointmentCard extends StatelessWidget {
  const _AppointmentCard({
    required this.appointment,
    required this.dark,
    required this.isPast,
    required this.isDone,
    required this.canMark,
    required this.onAddToCalendar,
    required this.onToggleDone,
    this.edit,
    this.onEdit,
    this.onRevert,
  });

  final Map appointment;
  final bool dark;

  /// The date has elapsed. Unparseable and missing dates are never past.
  final bool isPast;

  /// The patient has ticked this one off.
  final bool isDone;

  /// False when the appointment has nothing identifying to key on, in which
  /// case no tick is offered rather than sharing one key across blanks.
  final bool canMark;

  final VoidCallback onAddToCalendar;
  final ValueChanged<bool> onToggleDone;

  /// The patient's correction, or null when the document's values stand.
  final AppointmentEdit? edit;

  /// Null when the appointment has nothing to key on, matching [canMark]:
  /// an edit that cannot be stored should not be offered.
  final VoidCallback? onEdit;
  final VoidCallback? onRevert;

  /// Field name as the patient sees it in the edit sheet.
  static String _fieldLabel(String field) => switch (field) {
        'date' => 'When',
        'provider' => 'Who',
        'specialty' => 'Department',
        'reason' => 'What for',
        _ => field,
      };

  static const _monthNames = [
    'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
    'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
  ];

  String? _text(String key) {
    final v = '${appointment[key] ?? ''}'.trim();
    return v.isEmpty || v == 'null' ? null : v;
  }

  @override
  Widget build(BuildContext context) {
    final accent = dark ? kTealGlow : kTeal;
    final specialty = _text('specialty');
    final provider = _text('provider');
    final reason = _text('reason');
    final rawDate = _text('date');
    final parsed = parseAppointmentDate(rawDate);

    // Heading is the kind of visit; the person comes underneath. When only one
    // is known it becomes the heading rather than leaving a generic title.
    final heading = specialty ?? provider ?? 'Follow-up visit';
    final subheading = specialty != null ? provider : null;

    return Card(
      color: dark ? kCardDark : kCardLight,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _dateBlock(parsed, rawDate, accent),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        heading,
                        style: TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w700,
                          color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                        ),
                      ),
                      if (subheading != null) ...[
                        const SizedBox(height: 2),
                        Text(
                          'with $subheading',
                          style: TextStyle(
                            fontSize: 13,
                            color: dark
                                ? kTextSecondaryDark
                                : kTextSecondaryLight,
                          ),
                        ),
                      ],
                      // An unparseable or missing date is stated in words
                      // rather than shown as "TBD", which patients read as an
                      // app error rather than as missing paperwork.
                      if (parsed == null) ...[
                        const SizedBox(height: 6),
                        Text(
                          rawDate == null
                              ? 'No date given - call to book this'
                              : 'Date as written: $rawDate',
                          style: const TextStyle(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                            color: kMedChanged,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            if (reason != null) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: dark ? 0.10 : 0.07),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'WHY',
                      style: TextStyle(
                        fontSize: 9.5,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.6,
                        color: accent,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      reason,
                      style: TextStyle(
                        fontSize: 13.5,
                        height: 1.35,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            SourceQuote(source: appointment['source']),
            // Actions. A past appointment led with "Add to calendar", which is
            // the one action that no longer makes sense for it - raised at the
            // LOF review on 26 Aug 2026. Past visits now lead with the tick,
            // and calendar stays available underneath because a date can be
            // wrong, rescheduled, or worth logging after the fact.
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (canMark && (isPast || isDone))
                  TextButton.icon(
                    onPressed: () => onToggleDone(!isDone),
                    icon: Icon(
                      isDone
                          ? Icons.check_circle
                          : Icons.check_circle_outline,
                      size: 18,
                      color: isDone ? kMedChanged : null,
                    ),
                    label: Text(isDone ? 'Done' : 'Mark as done'),
                    // 48dp touch target, same rule as the audio play button.
                    style: TextButton.styleFrom(
                      minimumSize: const Size(48, 48),
                      foregroundColor: isDone ? kMedChanged : null,
                    ),
                  ),
                TextButton.icon(
                  onPressed: onAddToCalendar,
                  icon: const Icon(Icons.calendar_month_outlined, size: 18),
                  label: Text(isPast ? 'Add anyway' : 'Add to calendar'),
                  style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
                ),
                if (onEdit != null)
                  TextButton.icon(
                    onPressed: onEdit,
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    // "Update" rather than "Edit": the patient is recording
                    // what the clinic told them, not correcting a typo.
                    label: const Text('Update'),
                    style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
                  ),
              ],
            ),
            // Provenance. A changed appointment must never look like what the
            // hospital wrote - same rule as the recovery timeline.
            if (edit != null) ...[
              const SizedBox(height: 2),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: sdWarnTint,
                  borderRadius: BorderRadius.circular(kRadiusField),
                  border: Border.all(color: sdWarnLine),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      edit!.summary,
                      style: const TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w700,
                          color: sdWarnInk),
                    ),
                    const SizedBox(height: 3),
                    for (final field in edit!.changes.keys)
                      Text(
                        '${_fieldLabel(field)}: '
                        '${(edit!.originals[field] ?? '').isEmpty ? 'not in your document' : edit!.originals[field]}'
                        ' → ${edit!.changes[field]}',
                        style: const TextStyle(
                            fontSize: 11.5, height: 1.35, color: sdWarnInk),
                      ),
                    if (onRevert != null)
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton(
                          onPressed: onRevert,
                          style: TextButton.styleFrom(
                            minimumSize: const Size(48, 40),
                            padding: EdgeInsets.zero,
                            foregroundColor: sdWarnInk,
                          ),
                          child: const Text('Undo',
                              style: TextStyle(
                                  fontSize: 11.5, fontWeight: FontWeight.w700)),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Calendar-style date block: month above day, the way a patient scans a
  /// diary. Falls back to a neutral icon when no date could be parsed, so the
  /// card never displays a fake one.
  Widget _dateBlock(DateTime? parsed, String? rawDate, Color accent) {
    final hasDate = parsed != null;
    return Container(
      width: 54,
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: hasDate
            ? accent.withValues(alpha: dark ? 0.20 : 0.12)
            : (dark ? kCardDark : kBgLight),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasDate
              ? accent.withValues(alpha: 0.5)
              : (dark ? kTextHintDark : kTextHintLight).withValues(alpha: 0.35),
        ),
      ),
      child: hasDate
          ? Column(
              children: [
                Text(
                  _monthNames[parsed.month - 1],
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5,
                    color: accent,
                  ),
                ),
                Text(
                  '${parsed.day}',
                  style: TextStyle(
                    fontSize: 21,
                    height: 1.1,
                    fontWeight: FontWeight.w800,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                ),
                Text(
                  '${parsed.year}',
                  style: TextStyle(
                    fontSize: 10,
                    color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ],
            )
          : Icon(
              Icons.event_busy_outlined,
              size: 24,
              color: dark ? kTextHintDark : kTextHintLight,
            ),
    );
  }
}
