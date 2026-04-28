import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
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
          home: const _HomeGate(),
        );
      },
    );
  }
}

class _HomeGate extends StatelessWidget {
  const _HomeGate();

  @override
  Widget build(BuildContext context) {
    return Consumer<DischargeProvider>(
      builder: (context, dp, _) {
        if (dp.hasResult) return const ResultsScreen();
        return const UploadScreen();
      },
    );
  }
}
