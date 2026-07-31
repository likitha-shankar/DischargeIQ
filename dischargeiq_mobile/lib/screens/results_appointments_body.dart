// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

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
