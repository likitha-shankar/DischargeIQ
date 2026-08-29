import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/screens/intro_screen.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/services/read_aloud.dart';
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

/// Read-aloud toggle (accessibility): shows/hides the speaker button on the
/// results screen. Default on - the patients who need it most are the least
/// likely to go looking for a setting.
class _ReadAloudTile extends StatefulWidget {
  const _ReadAloudTile();

  @override
  State<_ReadAloudTile> createState() => _ReadAloudTileState();
}

class _ReadAloudTileState extends State<_ReadAloudTile> {
  bool _enabled = true;

  @override
  void initState() {
    super.initState();
    ReadAloud.enabled().then((v) {
      if (mounted) setState(() => _enabled = v);
    });
  }

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      title: const Text('Read aloud'),
      subtitle: const Text(
          'Show a speaker button that reads each results section out loud'),
      activeThumbColor: kTeal,
      value: _enabled,
      onChanged: (v) {
        setState(() => _enabled = v);
        ReadAloud.setEnabled(v);
      },
    );
  }
}

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
          Consumer<ThemeProvider>(
            builder: (context, tp, _) => ListTile(
              title: const Text('Text size'),
              subtitle: Text(tp.textSize.label),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => _showTextSizeSheet(context, tp),
            ),
          ),
          const _ReadAloudTile(),
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
            leading: const Icon(Icons.play_circle_outline, color: kTeal),
            title: const Text('Watch the intro again'),
            subtitle: const Text('The short welcome animation'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push<void>(
              context,
              MaterialPageRoute<void>(
                builder: (routeCtx) => IntroScreen(
                  onDone: () => Navigator.of(routeCtx).maybePop(),
                ),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.balance_outlined, color: kTeal),
            title: const Text('Open source licences'),
            subtitle: const Text('The software this app is built on'),
            trailing: const Icon(Icons.chevron_right),
            // Flutter's built-in page, which collects Dart and Flutter package
            // licences automatically. registerBackendLicenses() adds the
            // Python backend, which the collector cannot see and which does
            // the actual analysis - a page listing only the mobile half would
            // look complete while omitting most of the product.
            onTap: () => showLicensePage(
              context: context,
              applicationName: 'DischargeIQ',
              applicationVersion: '1.0.0',
              applicationLegalese:
                  '\u00a9 2026 Likitha Shankar. Released under the Apache '
                  'License 2.0.\n\nPatient education only. Not medical advice.',
            ),
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
            subtitle: Text('Version 1.0'),
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
              'Your documents and results are saved only on this phone so you '
              'can reopen them anytime. Nothing is stored on our servers. '
              'Deleting the app deletes everything.',
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

  /// Text size picker - applies instantly (the sheet itself grows, which IS
  /// the preview). Three simple steps, no slider (accessibility, Task 3.5).
  Future<void> _showTextSizeSheet(BuildContext context, ThemeProvider tp) async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        return AnimatedBuilder(
          animation: tp,
          builder: (ctx, _) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 8),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final option in TextSizeOption.values)
                  ListTile(
                    leading: Icon(Icons.text_fields,
                        size: 18 + 6 * TextSizeOption.values.indexOf(option).toDouble(),
                        color: tp.textSize == option ? kTeal : null),
                    title: Text(option.label),
                    trailing: tp.textSize == option
                        ? const Icon(Icons.check, color: kTeal)
                        : null,
                    onTap: () => tp.setTextSize(option),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _showThemeSheet(BuildContext context, ThemeProvider tp) async {
    // Applies immediately on tap - the whole app re-themes behind the sheet,
    // which IS the preview. No confirm step to learn.
    Widget option(BuildContext ctx, ThemeMode mode, IconData icon, String label) {
      final selected = tp.mode == mode;
      return ListTile(
        leading: Icon(icon, color: selected ? kTeal : null),
        title: Text(label),
        trailing: selected ? const Icon(Icons.check, color: kTeal) : null,
        onTap: () => tp.setMode(mode),
      );
    }

    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        return AnimatedBuilder(
          animation: tp,
          builder: (ctx, _) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 8),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                option(ctx, ThemeMode.system, Icons.brightness_auto_outlined,
                    'Follow system default'),
                option(ctx, ThemeMode.light, Icons.light_mode_outlined,
                    'Always light'),
                option(ctx, ThemeMode.dark, Icons.dark_mode_outlined,
                    'Always dark'),
              ],
            ),
          ),
        );
      },
    );
  }
}
