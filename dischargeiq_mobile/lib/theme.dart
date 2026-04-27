import 'package:flutter/material.dart';
import 'package:dischargeiq_mobile/config.dart';

/// Light Material 3 theme for DischargeIQ.
final ThemeData lightTheme = ThemeData(
  useMaterial3: true,
  primaryColor: kTeal,
  brightness: Brightness.light,
  scaffoldBackgroundColor: kBgLight,
  cardColor: kCardLight,
  dividerColor: kBorderLight,
  colorScheme: ColorScheme.fromSeed(
    seedColor: kTeal,
    brightness: Brightness.light,
    primary: kTeal,
    surface: kSurfaceLight,
  ),
  appBarTheme: const AppBarTheme(
    elevation: 0,
    scrolledUnderElevation: 0,
    backgroundColor: kBgLight,
    foregroundColor: kTextPrimaryLight,
    surfaceTintColor: Colors.transparent,
    titleTextStyle: TextStyle(
      color: kTextPrimaryLight,
      fontSize: 18,
      fontWeight: FontWeight.w600,
    ),
    shape: Border(
      bottom: BorderSide(color: kBorderLight, width: 0.5),
    ),
  ),
  tabBarTheme: const TabBarThemeData(
    indicatorColor: kTeal,
    labelColor: kTeal,
    unselectedLabelColor: kTextSecondaryLight,
  ),
  navigationBarTheme: const NavigationBarThemeData(
    backgroundColor: Colors.white,
    indicatorColor: kTealPale,
    labelTextStyle: WidgetStatePropertyAll(
      TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
    ),
  ),
);

/// Dark Material 3 theme for DischargeIQ.
final ThemeData darkTheme = ThemeData(
  useMaterial3: true,
  primaryColor: kTeal,
  brightness: Brightness.dark,
  scaffoldBackgroundColor: kBgDark,
  cardColor: kCardDark,
  dividerColor: kBorderDark,
  colorScheme: ColorScheme.fromSeed(
    seedColor: kTeal,
    brightness: Brightness.dark,
    primary: kTeal,
    surface: kSurfaceDark,
  ),
  appBarTheme: const AppBarTheme(
    elevation: 0,
    scrolledUnderElevation: 0,
    backgroundColor: kBgDark,
    foregroundColor: kTextPrimaryDark,
    surfaceTintColor: Colors.transparent,
    titleTextStyle: TextStyle(
      color: kTextPrimaryDark,
      fontSize: 18,
      fontWeight: FontWeight.w600,
    ),
    shape: Border(
      bottom: BorderSide(color: kBorderDark, width: 0.5),
    ),
  ),
  tabBarTheme: const TabBarThemeData(
    indicatorColor: kTealGlow,
    labelColor: kTealGlow,
    unselectedLabelColor: kTextSecondaryDark,
  ),
  navigationBarTheme: NavigationBarThemeData(
    backgroundColor: kSurfaceDark,
    indicatorColor: kTeal.withValues(alpha: 0.3),
    labelTextStyle: const WidgetStatePropertyAll(
      TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
    ),
  ),
);
