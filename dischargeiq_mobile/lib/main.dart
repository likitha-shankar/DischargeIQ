import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/intro_screen.dart';
import 'package:dischargeiq_mobile/screens/results_screen.dart';
import 'package:dischargeiq_mobile/screens/upload_screen.dart';
import 'package:dischargeiq_mobile/theme.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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
  // Cinematic landing intro (mirror of the web version): plays once per cold
  // app launch - process-scoped, so backgrounding the app does not replay it,
  // but a fresh open does (same behavior as the web's per-session replay).
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
        return const UploadScreen();
      },
    );
  }
}
