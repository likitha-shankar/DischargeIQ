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
/// Shape language (2026 revamp): one radius family (24 cards / 16 controls /
/// 14 fields), TONAL DEPTH instead of hairline borders - cards float on a
/// teal-tinted soft shadow in light mode and sit as lighter tonal panels in
/// dark mode. Flat app bars, pill tab indicators, generous touch targets
/// (patients may be older, unwell, or medicated - nothing small or subtle).

/// Radius tokens - the only three values any rounded corner should use.
const double kRadiusCard = 24;
const double kRadiusControl = 16;
const double kRadiusField = 14;

/// Soft ambient shadow under raised surfaces. Teal-tinted so depth reads as
/// part of the brand, not grey smog; near-invisible in dark mode where the
/// tonal fill does the lifting instead.
List<BoxShadow> cardShadow(bool dark) => dark
    ? const []
    : [
        BoxShadow(
          color: kTeal.withValues(alpha: 0.10),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ];

/// The revamp's standard raised surface for hand-rolled containers - screens
/// use this instead of inventing hairline-border decorations.
BoxDecoration tonalCardDecoration(bool dark, {double? radius}) =>
    BoxDecoration(
      color: dark ? kCardDark : kCardLight,
      borderRadius: BorderRadius.circular(radius ?? kRadiusCard),
      boxShadow: cardShadow(dark),
    );

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
          fontSize: 24,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.5,
          color: textPrimary),
      titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.3,
          color: textPrimary),
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

    // Cards: tonal depth - no border; a soft teal-tinted shadow lifts the
    // surface in light mode, the lighter tonal fill does it in dark mode.
    cardTheme: CardThemeData(
      color: card,
      elevation: dark ? 0 : 2,
      shadowColor: kTeal.withValues(alpha: 0.18),
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusCard),
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

    // Fields: borderless tonal fill; focus is the only stroke that appears.
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: dark ? kSurfaceDark : kTealPale.withValues(alpha: 0.45),
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(kRadiusField),
        borderSide: BorderSide.none,
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
      backgroundColor: dark ? kSurfaceDark : kTealPale.withValues(alpha: 0.5),
      selectedColor: dark ? kTeal.withValues(alpha: 0.35) : kTealPale,
      labelStyle: TextStyle(fontSize: 13, color: textPrimary),
      side: BorderSide.none,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(999),
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
    // Pill tabs: the active tab is a filled teal capsule, not an underline.
    tabBarTheme: TabBarThemeData(
      indicator: BoxDecoration(
        color: accent,
        borderRadius: BorderRadius.circular(999),
      ),
      indicatorSize: TabBarIndicatorSize.tab,
      dividerColor: Colors.transparent,
      labelColor: dark ? kBgDark : Colors.white,
      unselectedLabelColor: textSecondary,
      labelStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
      unselectedLabelStyle:
          const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500),
      overlayColor: const WidgetStatePropertyAll(Colors.transparent),
      labelPadding: const EdgeInsets.symmetric(horizontal: 14),
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
