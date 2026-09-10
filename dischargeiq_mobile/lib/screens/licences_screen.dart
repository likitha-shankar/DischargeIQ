/// screens/licences_screen.dart
///
/// A readable summary of what DischargeIQ is built on, in front of the
/// complete generated licence list.
///
/// WHY A SUMMARY AND NOT A SHORTER LIST
/// ------------------------------------
/// Tapping "Open source licences" used to land straight on Flutter's
/// showLicensePage, which collects every Dart and Flutter package plus the
/// whole transitive tree, plus the 18 backend entries this project registers
/// by hand. That is upwards of a hundred rows, alphabetical, with no
/// indication of which ones matter - unreadable as attribution and useless as
/// orientation.
///
/// The obvious response is to list only the recognisable packages. That is
/// not available: MIT, BSD-3-Clause and Apache-2.0 each require the notice
/// and copyright to travel with the distribution, so dropping entries turns a
/// long page into a non-compliant one. The complete list has to stay.
///
/// So this follows the pattern consumer apps settle on - a curated summary
/// that answers "what is this built on", with the full generated list one tap
/// further in for anyone who needs it. Nothing is hidden; the ordering just
/// stops pretending every entry is equally interesting.
///
/// The summary is DELIBERATELY hand-maintained. A generated "top N" would
/// need a popularity signal that does not exist in a pubspec, and would drift
/// silently. A short hand-written list drifts loudly, because a reader
/// notices a component that is missing.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

/// One component worth naming, with the licence it ships under.
typedef _Component = ({String name, String licence, String role});

/// The mobile app's own main dependencies.
const List<_Component> _appComponents = [
  (name: 'Flutter', licence: 'BSD-3-Clause', role: 'the app framework itself'),
  (name: 'pdfx', licence: 'MIT', role: 'renders your original document'),
  (name: 'google_mlkit_text_recognition', licence: 'MIT', role: 'reads photographed pages'),
  (name: 'audioplayers', licence: 'MIT', role: 'plays the audio explainers'),
  (name: 'flutter_tts / speech_to_text', licence: 'MIT / BSD-3-Clause', role: 'read aloud and voice input'),
  (name: 'provider', licence: 'MIT', role: 'app state'),
  (name: 'shared_preferences', licence: 'BSD-3-Clause', role: 'saves your notes and ticks on this phone'),
];

/// The backend that actually performs the analysis.
const List<_Component> _backendComponents = [
  (name: 'FastAPI', licence: 'MIT', role: 'the analysis service'),
  (name: 'Pydantic', licence: 'MIT', role: 'validates every agent output'),
  (name: 'pdfplumber', licence: 'MIT', role: 'extracts text from your PDF'),
  (name: 'pypdf / pdfminer.six', licence: 'BSD-3-Clause / MIT', role: 'PDF parsing underneath'),
  (name: 'textstat', licence: 'MIT', role: 'measures reading grade'),
  (name: 'asyncpg', licence: 'Apache-2.0', role: 'database access'),
  (name: 'google-auth', licence: 'Apache-2.0', role: 'authenticates to Vertex AI'),
];

/// Concise licence summary, with the full list behind one more tap.
class LicencesScreen extends StatelessWidget {
  const LicencesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = dark ? kTextPrimaryDark : kTextPrimaryLight;
    final muted = dark ? kTextSecondaryDark : kTextSecondaryLight;

    return Scaffold(
      appBar: AppBar(title: const Text('Open source licences')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          Text(
            'DischargeIQ is released under the Apache License 2.0 and is '
            'built on open source software.',
            style: TextStyle(fontSize: 15, height: 1.45, color: text),
          ),
          const SizedBox(height: 20),
          _Group(title: 'In the app', components: _appComponents, dark: dark),
          const SizedBox(height: 18),
          _Group(
            title: 'In the analysis service',
            components: _backendComponents,
            dark: dark,
          ),
          const SizedBox(height: 22),
          Text(
            'These are the main components. The full list below names every '
            'package, including the ones they depend on in turn, with the '
            'licence text each one requires.',
            style: TextStyle(fontSize: 13, height: 1.45, color: muted),
          ),
          const SizedBox(height: 12),
          FilledButton.tonalIcon(
            onPressed: () => showLicensePage(
              context: context,
              applicationName: 'DischargeIQ',
              applicationVersion: '1.0.0',
              applicationLegalese:
                  '© 2026 Likitha Shankar. Released under the Apache '
                  'License 2.0.\n\nPatient education only. Not medical advice.',
            ),
            icon: const Icon(Icons.list_alt_outlined, size: 19),
            label: const Text('View all licences'),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
            ),
          ),
        ],
      ),
    );
  }
}

class _Group extends StatelessWidget {
  const _Group({
    required this.title,
    required this.components,
    required this.dark,
  });

  final String title;
  final List<_Component> components;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final text = dark ? kTextPrimaryDark : kTextPrimaryLight;
    final muted = dark ? kTextSecondaryDark : kTextSecondaryLight;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title.toUpperCase(),
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.8,
            color: dark ? kTealGlow : kTeal,
          ),
        ),
        const SizedBox(height: 10),
        for (final component in components)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        component.name,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: text,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      component.licence,
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: muted,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  component.role,
                  style: TextStyle(fontSize: 12.5, height: 1.35, color: muted),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
