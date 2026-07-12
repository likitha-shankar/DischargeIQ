import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// App-wide text sizes (accessibility, Task 3.5): multiplies every font in
/// the app on top of the system setting. Three steps keep the choice simple
/// for older patients - no slider to fiddle with.
enum TextSizeOption {
  normal(1.0, 'Normal'),
  large(1.15, 'Large'),
  extraLarge(1.3, 'Extra large');

  const TextSizeOption(this.scale, this.label);

  final double scale;
  final String label;
}

/// Persists [ThemeMode] under key `theme_mode` (name: system | light | dark)
/// and the text size under `text_size` (enum name).
class ThemeProvider extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.system;
  TextSizeOption _textSize = TextSizeOption.normal;

  ThemeMode get mode => _mode;
  TextSizeOption get textSize => _textSize;

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
    final sizeName = prefs.getString('text_size');
    _textSize = TextSizeOption.values.firstWhere(
      (o) => o.name == sizeName,
      orElse: () => TextSizeOption.normal,
    );
    notifyListeners();
  }

  void setMode(ThemeMode mode) {
    _mode = mode;
    SharedPreferences.getInstance().then((prefs) {
      prefs.setString('theme_mode', mode.name);
    });
    notifyListeners();
  }

  void setTextSize(TextSizeOption size) {
    _textSize = size;
    SharedPreferences.getInstance().then((prefs) {
      prefs.setString('text_size', size.name);
    });
    notifyListeners();
  }
}
