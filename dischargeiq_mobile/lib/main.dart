import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/intro_screen.dart';
import 'package:dischargeiq_mobile/screens/results_screen.dart';
import 'package:dischargeiq_mobile/screens/upload_screen.dart';
import 'package:dischargeiq_mobile/theme.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final themeProvider = ThemeProvider();
  await themeProvider.loadSaved();
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ThemeProvider>.value(value: themeProvider),
        ChangeNotifierProvider<DischargeProvider>(create: (_) => DischargeProvider()),
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
  // Cinematic landing intro: plays once EVER (persisted flag), not once per
  // launch - a patient reopening the app to check a medication should land
  // on their content immediately. Settings offers "Watch the intro again".
  static bool _introDone = false;
  bool _flagLoaded = _introDone;

  @override
  void initState() {
    super.initState();
    if (_flagLoaded) return;
    SharedPreferences.getInstance().then((prefs) {
      if (!mounted) return;
      setState(() {
        _introDone = prefs.getBool('intro_seen') ?? false;
        _flagLoaded = true;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    // One blank frame while the persisted flag loads - imperceptible, and
    // avoids flashing the intro for returning patients.
    if (!_flagLoaded) return const Scaffold(body: SizedBox.shrink());
    if (!_introDone) {
      return IntroScreen(
        onDone: () {
          SharedPreferences.getInstance()
              .then((prefs) => prefs.setBool('intro_seen', true));
          setState(() => _introDone = true);
        },
      );
    }
    return Consumer<DischargeProvider>(
      builder: (context, dp, _) {
        if (dp.hasResult) return const ResultsScreen();
        return const UploadScreen();
      },
    );
  }
}
