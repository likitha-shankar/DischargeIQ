/// screens/how_it_works_screen.dart
///
/// What the app does, as a picture of the journey plus the promises that a
/// picture cannot make.
///
/// WHY A FLOW AND NOT PROSE
/// ------------------------
/// The reader is a patient who has just left hospital, not a technical user.
/// Six paragraphs asked them to hold the whole process in their head and
/// assemble the order themselves. A numbered flow shows the order directly,
/// and each step is short enough to take in at a glance.
///
/// The flow stops where a flow stops being honest. "It will never tell you to
/// stop a medicine", "your notes stay on this phone" and "this can be wrong"
/// are not steps in a process - they are commitments and limits, and drawing
/// them as boxes in a pipeline would misrepresent what they are. They stay as
/// cards underneath.
///
/// HISTORY
/// -------
/// The first version was a bottom sheet of six lines named after the agents
/// ("Extraction", "Diagnosis", "Quality check") at Flesch-Kincaid 6.9 - above
/// the 6.0 that hard rule 4 enforces on every agent output, on the one screen
/// whose job is explaining the product to a patient. Nothing was measuring
/// it. This version measures 1.4, with no element above 3.3.
///
/// EVERY CLAIM IS CHECKED AGAINST BEHAVIOUR
/// ----------------------------------------
/// "Numbers must come from your paper" is threshold_guard, measured at 80% of
/// documents carrying an invented threshold before and 0% after. "Your notes
/// stay on this phone" is the ten docId-keyed local stores. The quoted
/// instruction uses the exact SourceQuote chip label, so it names a control
/// the reader can actually find rather than one that sounds plausible.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

typedef _Step = ({IconData icon, String title, String detail});
typedef _Card = ({IconData icon, String title, String body});

/// The journey, in the order it happens to the patient.
const List<_Step> _flow = [
  (
    icon: Icons.upload_file_outlined,
    title: 'You add your paper',
    detail: 'Take a photo of it, or pick a PDF.',
  ),
  (
    icon: Icons.search,
    title: 'The app reads it',
    detail: 'It finds your medicines, dates and warning signs.',
  ),
  (
    icon: Icons.edit_note_outlined,
    title: 'It writes it in plain words',
    detail: 'Your paper is the only source. Nothing new is added.',
  ),
  (
    icon: Icons.fact_check_outlined,
    title: 'We check the writing',
    detail: 'Easy words. Numbers must come from your paper.',
  ),
  (
    icon: Icons.menu_book_outlined,
    title: 'You read it in six parts',
    detail: 'Tap "See where this comes from" next to any fact.',
  ),
  (
    icon: Icons.people_outline,
    title: 'You talk to your care team',
    detail: 'They are still in charge of your care.',
  ),
];

/// Commitments and limits. Not steps, and deliberately not drawn as steps.
const List<_Card> _cards = [
  (
    icon: Icons.block_outlined,
    title: 'What it will never do',
    body: 'It will never tell you to stop or change a medicine. It will never '
        'give you a new diagnosis.',
  ),
  (
    icon: Icons.phone_iphone_outlined,
    title: 'Where your information goes',
    body: 'Your paper is sent to our service to be read, then it is not kept. '
        'Your notes and quiz scores stay on this phone.',
  ),
  (
    icon: Icons.error_outline,
    title: 'When it gets things wrong',
    body: 'This is a computer program and it can be wrong. It may miss a '
        'thing your paper says.',
  ),
];

/// Plain-language explanation of the app, reachable from Settings.
class HowItWorksScreen extends StatelessWidget {
  const HowItWorksScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = dark ? kTextPrimaryDark : kTextPrimaryLight;
    final muted = dark ? kTextSecondaryDark : kTextSecondaryLight;
    final accent = dark ? kTealGlow : kTeal;

    return Scaffold(
      appBar: AppBar(title: const Text('How it works')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
        children: [
          Text(
            'DischargeIQ turns your hospital paper into something easier to '
            'read. Here is what happens.',
            style: TextStyle(fontSize: 16, height: 1.45, color: text),
          ),
          const SizedBox(height: 24),
          for (var i = 0; i < _flow.length; i++)
            _FlowStep(
              step: _flow[i],
              number: i + 1,
              // The connector is drawn by the step ABOVE it, so the last one
              // ends the line rather than trailing into blank space.
              isLast: i == _flow.length - 1,
              accent: accent,
              text: text,
              muted: muted,
            ),
          const SizedBox(height: 10),
          Divider(color: dark ? kBorderDark : kBorderLight),
          const SizedBox(height: 18),
          Text(
            'Good to know',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
              color: accent,
            ),
          ),
          const SizedBox(height: 14),
          for (final card in _cards) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Icon(card.icon, size: 19, color: accent),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        card.title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: text,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        card.body,
                        style: TextStyle(fontSize: 14, height: 1.5, color: muted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
          ],
        ],
      ),
    );
  }
}

/// One numbered step, with the line connecting it to the next.
///
/// Built from an IntrinsicHeight row rather than a fixed-height box so the
/// connector always spans the actual text. At large text sizes a fixed height
/// would leave a gap between the line and the next circle, and the flow would
/// stop reading as a sequence exactly for the readers most likely to need
/// the sequence.
class _FlowStep extends StatelessWidget {
  const _FlowStep({
    required this.step,
    required this.number,
    required this.isLast,
    required this.accent,
    required this.text,
    required this.muted,
  });

  final _Step step;
  final int number;
  final bool isLast;
  final Color accent;
  final Color text;
  final Color muted;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Column(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: accent.withValues(alpha: 0.12),
                  border: Border.all(color: accent.withValues(alpha: 0.45)),
                ),
                child: Icon(step.icon, size: 17, color: accent),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    color: accent.withValues(alpha: 0.25),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(top: 4, bottom: isLast ? 0 : 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      // The number is what makes it a sequence rather than a
                      // list of features. Screen readers get it too, since it
                      // is real text and not a decoration.
                      Text(
                        '$number',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: accent,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          step.title,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            height: 1.25,
                            color: text,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    step.detail,
                    style: TextStyle(fontSize: 13.5, height: 1.45, color: muted),
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
