/// widgets/run_state_screens.dart
///
/// The two full-screen notices `ResultsScreen` shows instead of section tabs:
/// a document the router rejected, and a run that produced nothing usable.
/// They live outside that screen because these strings are the app's only
/// voice for "we could not help you with this", and a screen file is where
/// safety-reviewed wording quietly gets edited.
///
/// Neither screen mentions API keys, quotas or providers: a patient reading
/// this is holding a piece of paper the app just failed to explain.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Full-screen notice for a run where analysis could not produce anything
/// usable. Honest, jargon-free, one action. Never mentions API keys.
class AnalysisFailedScreen extends StatelessWidget {
  const AnalysisFailedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.cloud_off_outlined, size: 60, color: kTier2),
                const SizedBox(height: 16),
                Text(
                  "We couldn't read your document right now",
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                Text(
                  'Our reading service is very busy at the moment. Nothing is '
                  'wrong with your document, and nothing was lost.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5),
                ),
                const SizedBox(height: 10),
                Text(
                  'Please try again in a few minutes. If it keeps happening, '
                  'try later today - your paper document always has the '
                  'complete instructions.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      height: 1.5,
                      color: Theme.of(context).textTheme.bodySmall?.color),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: () =>
                      context.read<DischargeProvider>().clear(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


/// Full-screen notice for a document the router rejected (bill, EOB, random
/// PDF). One action: go back and try another document.
class RejectedDocumentScreen extends StatelessWidget {
  const RejectedDocumentScreen({super.key, required this.reason});

  final String reason;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('DischargeIQ'),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.description_outlined, size: 60, color: kTier2),
                const SizedBox(height: 16),
                Text(
                  "This doesn't look like a discharge document",
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                Text(reason,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5)),
                const SizedBox(height: 10),
                Text(
                  'DischargeIQ works with the discharge summary your hospital '
                  'gave you when you went home - it usually lists your '
                  'diagnosis, medications, and follow-up appointments.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(height: 1.5, color: Theme.of(context).textTheme.bodySmall?.color),
                ),
                const SizedBox(height: 24),
                // Clearing the provider is what actually returns to the home
                // surface. This was Navigator.pop, which did nothing: the
                // loading screen pops itself, so this screen renders at the
                // ROOT route and there was nothing above it to pop - the only
                // button on the rejection screen was dead.
                FilledButton.icon(
                  onPressed: () => context.read<DischargeProvider>().clear(),
                  icon: const Icon(Icons.upload_file_outlined),
                  label: const Text('Try another document'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
