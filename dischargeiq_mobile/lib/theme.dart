import 'package:flutter/material.dart';
import 'package:dischargeiq_mobile/config.dart';

/// App-wide Material 3 design system for DischargeIQ.
///
/// One builder produces both brightnesses so light and dark can never drift.
/// Every component theme below exists so SCREENS DON'T STYLE THEMSELVES:
/// buttons, cards, sheets, dialogs, chips, and inputs inherit their shape,
/// color, and padding from here. When a screen hand-rolls a style, move the
/// decision into this file instead.
///
/// Shape language: one radius family (18 cards / 14 controls / 12 fields),
/// hairline borders instead of shadows, flat app bars, generous touch targets
/// (patients may be older, unwell, or medicated - nothing small or subtle).

/// Radius tokens - the only three values any rounded corner should use.
const double kRadiusCard = 18;
const double kRadiusControl = 14;
const double kRadiusField = 12;

ThemeData _build(Brightness brightness) {
  final dark = brightness == Brightness.dark;

  final bg = dark ? kBgDark : kBgLight;
  final surface = dark ? kSurfaceDark : kSurfaceLight;
  final card = dark ? kCardDark : kCardLight;
  final border = dark ? kBorderDark : kBorderLight;
  final textPrimary = dark ? kTextPrimaryDark : kTextPrimaryLight;
  final textSecondary = dark ? kTextSecondaryDark : kTextSecondaryLight;
  final accent = dark ? kTealGlow : kTeal;

  return ThemeData(
    useMaterial3: true,
    primaryColor: kTeal,
    brightness: brightness,
    scaffoldBackgroundColor: bg,
    cardColor: card,
    dividerColor: border,
    colorScheme: ColorScheme.fromSeed(
      seedColor: kTeal,
      brightness: brightness,
      primary: kTeal,
      surface: surface,
    ),

    // Readable-first type scale: slightly larger body sizes and relaxed line
    // height for post-discharge readers; titles bold enough to scan by.
    textTheme: TextTheme(
      headlineSmall: TextStyle(
          fontSize: 22, fontWeight: FontWeight.w800, color: textPrimary),
      titleLarge: TextStyle(
          fontSize: 19, fontWeight: FontWeight.w700, color: textPrimary),
      titleMedium: TextStyle(
          fontSize: 16, fontWeight: FontWeight.w700, color: textPrimary),
      titleSmall: TextStyle(
          fontSize: 13.5, fontWeight: FontWeight.w600, color: textSecondary),
      bodyLarge: TextStyle(fontSize: 16, height: 1.5, color: textPrimary),
      bodyMedium: TextStyle(fontSize: 14.5, height: 1.5, color: textPrimary),
      bodySmall: TextStyle(fontSize: 12.5, height: 1.4, color: textSecondary),
      labelLarge: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
    ),

    appBarTheme: AppBarTheme(
      elevation: 0,
      scrolledUnderElevation: 0,
      backgroundColor: bg,
      foregroundColor: textPrimary,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: TextStyle(
        color: textPrimary,
        fontSize: 18,
        fontWeight: FontWeight.w600,
      ),
      shape: Border(bottom: BorderSide(color: border, width: 0.5)),
    ),

    // Cards: hairline border, no shadow - calm, paper-like surfaces.
    cardTheme: CardThemeData(
      color: card,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusCard),
        side: BorderSide(color: border, width: 0.5),
      ),
    ),

    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        minimumSize: const Size(64, 48), // comfortable tap target
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(kRadiusControl),
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: accent,
        side: BorderSide(color: dark ? kTealMid : kTeal),
        minimumSize: const Size(64, 48),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(kRadiusControl),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: accent,
        minimumSize: const Size(48, 44),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(kRadiusControl),
        ),
      ),
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surface,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
        borderSide: BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
        borderSide: BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
        borderSide: BorderSide(color: accent, width: 1.5),
      ),
      hintStyle: TextStyle(color: dark ? kTextHintDark : kTextHintLight),
    ),

    // Sheets and dialogs share the card language.
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: dark ? kSurfaceDark : kBgLight,
      surfaceTintColor: Colors.transparent,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(kRadiusCard)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: card,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusCard),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: dark ? kCardDark : kTextPrimaryLight,
      contentTextStyle: TextStyle(
          fontSize: 14, color: dark ? kTextPrimaryDark : Colors.white),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
      ),
    ),

    chipTheme: ChipThemeData(
      backgroundColor: surface,
      selectedColor: dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
      labelStyle: TextStyle(fontSize: 13, color: textPrimary),
      side: BorderSide(color: border, width: 0.5),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusControl),
      ),
    ),

    listTileTheme: ListTileThemeData(
      iconColor: accent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
      ),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: accent,
      linearTrackColor: dark ? Colors.white10 : kTealPale,
    ),
    tabBarTheme: TabBarThemeData(
      indicatorColor: accent,
      labelColor: accent,
      unselectedLabelColor: textSecondary,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: dark ? kSurfaceDark : Colors.white,
      indicatorColor: dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
      labelTextStyle: const WidgetStatePropertyAll(
        TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
      ),
    ),
  );
}

/// Light Material 3 theme for DischargeIQ.
final ThemeData lightTheme = _build(Brightness.light);

/// Dark Material 3 theme for DischargeIQ.
final ThemeData darkTheme = _build(Brightness.dark);
