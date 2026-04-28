import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kDisclaimerBody =
    'DischargeIQ provides patient education only. It is not medical advice, '
    'not a diagnosis, and not a substitute for your care team. Always follow '
    'your clinician’s instructions and seek urgent care when appropriate.';

const _kAgentHelp =
    'Extraction: reads your PDF and pulls out structured facts.\n\n'
    'Diagnosis: explains in plain language what happened in the hospital.\n\n'
    'Medications: explains each drug and why it was prescribed.\n\n'
    'Recovery: outlines a simple timeline for getting back to normal.\n\n'
    'Warning signs: three-tier guide for when to call 911, go to the ER, or call your doctor.\n\n'
    'Quality check: simulates a confused patient to find gaps in the discharge document.';

/// Theme persistence uses SharedPreferences key `theme_mode` (see [ThemeProvider]).
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: dark ? kBgDark : kBgLight,
        foregroundColor: dark ? kTextPrimaryDark : kTextPrimaryLight,
        title: Text(
          'Settings',
          style: TextStyle(color: dark ? kTextPrimaryDark : kTextPrimaryLight),
        ),
      ),
      body: ListView(
        children: [
          _sectionHeader(context, 'Appearance'),
          Consumer<ThemeProvider>(
            builder: (context, tp, _) {
              final label = switch (tp.mode) {
                ThemeMode.system => 'System',
                ThemeMode.light => 'Light',
                ThemeMode.dark => 'Dark',
              };
              return ListTile(
                title: const Text('App theme'),
                subtitle: Text(label),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _showThemeSheet(context, tp),
              );
            },
          ),
          _sectionHeader(context, 'Help'),
          ListTile(
            leading: const Icon(Icons.explore_outlined, color: kTeal),
            title: const Text('Guided tour'),
            subtitle: const Text('Learn how to use DischargeIQ'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setBool('tour_completed', false);
              if (!context.mounted) return;
              final has = context.read<DischargeProvider>().hasResult;
              if (has) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Starting guided tour...'),
                  ),
                );
                Navigator.pop(context, 'start_tour');
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Run an analysis first to see the guided tour on results.'),
                  ),
                );
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.info_outline, color: kTeal),
            title: const Text('How it works'),
            subtitle: const Text('About the AI agents and what they do'),
            onTap: () {
              showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                builder: (ctx) => Padding(
                  padding: const EdgeInsets.all(24),
                  child: SingleChildScrollView(
                    child: Text(
                      _kAgentHelp,
                      style: TextStyle(
                        fontSize: 14,
                        height: 1.5,
                        color: Theme.of(ctx).brightness == Brightness.dark
                            ? kTextSecondaryDark
                            : kTextSecondaryLight,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
          _sectionHeader(context, 'About'),
          const ListTile(
            title: Text('DischargeIQ'),
            subtitle: Text('Version 1.0 · CS 595 · IIT Chicago · Spring 2026'),
          ),
          ListTile(
            title: const Text('Disclaimer'),
            onTap: () {
              showModalBottomSheet<void>(
                context: context,
                builder: (ctx) => Padding(
                  padding: const EdgeInsets.all(24),
                  child: SingleChildScrollView(
                    child: Text(
                      _kDisclaimerBody,
                      style: TextStyle(
                        fontSize: 14,
                        height: 1.5,
                        color: Theme.of(ctx).brightness == Brightness.dark
                            ? kTextSecondaryDark
                            : kTextSecondaryLight,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
          _sectionHeader(context, 'Privacy'),
          const ListTile(
            leading: Icon(Icons.lock_outline, color: kTeal),
            title: Text('Your data'),
            subtitle: Text(
              'Your discharge documents are never stored. All data is deleted when you close the app.',
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionHeader(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: kTeal,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Future<void> _showThemeSheet(BuildContext context, ThemeProvider tp) async {
    var selected = tp.mode;
    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setSt) {
            void pick(ThemeMode m) => setSt(() => selected = m);
            return Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ListTile(
                    title: const Text('Follow system default'),
                    trailing: selected == ThemeMode.system
                        ? const Icon(Icons.check, color: kTeal)
                        : null,
                    onTap: () => pick(ThemeMode.system),
                  ),
                  ListTile(
                    title: const Text('Always light'),
                    trailing: selected == ThemeMode.light
                        ? const Icon(Icons.check, color: kTeal)
                        : null,
                    onTap: () => pick(ThemeMode.light),
                  ),
                  ListTile(
                    title: const Text('Always dark'),
                    trailing: selected == ThemeMode.dark
                        ? const Icon(Icons.check, color: kTeal)
                        : null,
                    onTap: () => pick(ThemeMode.dark),
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton(
                    onPressed: () {
                      tp.setMode(selected);
                      Navigator.pop(ctx);
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: kTeal,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('Apply'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
