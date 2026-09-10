/// screens/how_it_works_screen.dart
///
/// What the app does, answered in the patient's terms.
///
/// WHAT WAS WRONG WITH THE OLD VERSION
/// -----------------------------------
/// A bottom sheet of six lines, one per agent, named after the agents:
/// "Extraction", "Diagnosis", "Quality check". Three problems, in order of
/// how much they matter.
///
/// It measured Flesch-Kincaid 6.9. Hard rule 4 sets a target of 6.0 on
/// patient-facing text, and this was the one screen whose entire job is
/// explaining the product to a patient. Every agent output was held to the
/// line while the explanation of them was not. This version measures 1.8,
/// with no section above 3.3.
///
/// It was organised around the system's internals rather than the reader's
/// questions. "Quality check: simulates a confused patient to find gaps"
/// describes an implementation, and describes the reader as the confused
/// patient being simulated.
///
/// And it omitted the two things a patient most needs to know: that this is
/// a computer program that can be wrong, and where their document goes.
/// Neither appeared anywhere.
///
/// EVERY CLAIM HERE IS CHECKED AGAINST BEHAVIOUR
/// ---------------------------------------------
/// "It will take a number out if it is not in your paper" is threshold_guard
/// (measured 80% of documents carrying an invented threshold, now 0%). "Your
/// notes stay on this phone" is the ten docId-keyed local stores. "See where
/// this comes from" is the exact label on the SourceQuote chip, so the
/// instruction names something the reader can actually find. A help screen
/// that describes intentions rather than behaviour is a liability.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

typedef _Section = ({IconData icon, String title, String body});

const List<_Section> _sections = [
  (
    icon: Icons.description_outlined,
    title: 'Where the words come from',
    body: 'Your discharge paper is the only source. The app reads it and puts '
        'it in plain words. It does not add advice from anywhere else. If '
        'your paper does not say a thing, the app will tell you so. It will '
        'not guess.',
  ),
  (
    icon: Icons.view_list_outlined,
    title: 'What you get',
    body: 'Six parts. What happened to you. Your medicines and why you take '
        'them. A week by week plan. Warning signs, split into three levels of '
        'urgency. Your follow up visits. And a check that lists what your '
        'paper left out.',
  ),
  (
    icon: Icons.block_outlined,
    title: 'What it will never do',
    body: 'It will never tell you to stop or change a medicine. It will never '
        'give you a new diagnosis. It is not advice from a doctor. Your care '
        'team is still in charge of your care.',
  ),
  (
    icon: Icons.fact_check_outlined,
    title: 'What we check before you see it',
    body: 'We check that the text is easy to read. We check that numbers, '
        'like a weight or a fever limit, came from your own paper. If a '
        'number is not in your paper, we take it out.',
  ),
  (
    icon: Icons.phone_iphone_outlined,
    title: 'Where your information goes',
    body: 'Your paper is sent to our service to be read, then it is not kept. '
        'Your notes, your ticks and your quiz scores stay on this phone. They '
        'are never sent anywhere.',
  ),
  (
    icon: Icons.error_outline,
    title: 'When it gets things wrong',
    body: 'This is a computer program and it can be wrong. It may miss a '
        'thing your paper says. Always tap "See where this comes from" next '
        'to a fact. And bring your questions to your care team.',
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
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          Text(
            'DischargeIQ turns your hospital discharge paper into something '
            'easier to read.',
            style: TextStyle(fontSize: 16, height: 1.45, color: text),
          ),
          const SizedBox(height: 22),
          for (final section in _sections) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Icon(section.icon, size: 19, color: accent),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        section.title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: text,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        section.body,
                        style: TextStyle(
                          fontSize: 14,
                          height: 1.5,
                          color: muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
          ],
        ],
      ),
    );
  }
}
