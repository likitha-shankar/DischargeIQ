import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists [ThemeMode] under key `theme_mode` (name: system | light | dark).
class ThemeProvider extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.system;

  ThemeMode get mode => _mode;

  Future<void> loadSaved() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('theme_mode');
    if (saved == 'light') {
      _mode = ThemeMode.light;
    } else if (saved == 'dark') {
      _mode = ThemeMode.dark;
    } else {
      _mode = ThemeMode.system;
    }
    notifyListeners();
  }

  void setMode(ThemeMode mode) {
    _mode = mode;
    SharedPreferences.getInstance().then((prefs) {
      prefs.setString('theme_mode', mode.name);
    });
    notifyListeners();
  }
}
