import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/case_audio_player.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/intro_screen.dart';
import 'package:dischargeiq_mobile/services/backend_licenses.dart';
import 'package:dischargeiq_mobile/screens/results_screen.dart';
import 'package:dischargeiq_mobile/screens/upload_screen.dart';
import 'package:dischargeiq_mobile/theme.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Backend dependencies are invisible to Flutter's automatic licence
  // collector, so they are registered here before any licence page can open.
  registerBackendLicenses();
  final themeProvider = ThemeProvider();
  await themeProvider.loadSaved();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ThemeProvider>.value(value: themeProvider),
        ChangeNotifierProvider<DischargeProvider>(create: (_) => DischargeProvider()),
        // Above the tabs on purpose: an explainer keeps playing while the
        // patient reads another section, and can be paused from any of them.
        ChangeNotifierProvider<CaseAudioPlayer>(create: (_) => CaseAudioPlayer()),
      ],
      child: const DischargeIQApp(),
    ),
  );
}

class DischargeIQApp extends StatelessWidget {
  const DischargeIQApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ThemeProvider>(
      builder: (context, theme, _) {
        return MaterialApp(
          title: 'DischargeIQ',
          theme: lightTheme,
          darkTheme: darkTheme,
          themeMode: theme.mode,
          // Accessibility text size (Settings → Text size): multiplies on
          // top of the phone's own accessibility setting, app-wide. Clamped
          // so system-max + Extra large cannot break layouts entirely.
          builder: (context, child) {
            final mq = MediaQuery.of(context);
            final total =
                (mq.textScaler.scale(1.0) * theme.textSize.scale).clamp(0.8, 2.2);
            return MediaQuery(
              data: mq.copyWith(textScaler: TextScaler.linear(total)),
              child: child ?? const SizedBox.shrink(),
            );
          },
          home: const _HomeGate(),
        );
      },
    );
  }
}

class _HomeGate extends StatefulWidget {
  const _HomeGate();

  @override
  State<_HomeGate> createState() => _HomeGateState();
}

class _HomeGateState extends State<_HomeGate> {
  // Cinematic landing intro: plays once per app LAUNCH, by product decision.
  //
  // Static, not an instance field, so it survives widget rebuilds - navigating
  // back to the gate mid-session must not replay the animation. It resets when
  // the process does, which is exactly the "every time you open the app"
  // behaviour intended.
  //
  // This deliberately no longer persists a flag. It previously read and wrote
  // SharedPreferences('intro_seen') to play only once ever; that key is now
  // unused and can be ignored on existing installs. Settings still offers
  // "Watch the intro again", which pushes IntroScreen directly and is
  // unaffected by this gate.
  static bool _introDone = false;

  @override
  Widget build(BuildContext context) {
    if (!_introDone) {
      return IntroScreen(
        onDone: () => setState(() => _introDone = true),
      );
    }
    return Consumer<DischargeProvider>(
      builder: (context, dp, _) {
        if (dp.hasResult) return const ResultsScreen();
        // Home stays the upload screen. Family-health apps put the person
        // switcher IN the home surface rather than making people a separate
        // landing: it answers "whose records am I looking at?" continuously,
        // and it removes a navigation layer between opening the app and
        // reading a summary. PeopleScreen is reached from that switcher.
        return const UploadScreen();
      },
    );
  }
}
