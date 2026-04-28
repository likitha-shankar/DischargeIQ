import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

/// API base URL — override at build time with `--dart-define=API_BASE=http://...`
///
/// Real-device demo: flutter run --dart-define=API_BASE=http://104.194.97.253:8000
/// Phone and laptop must be on the same Wi-Fi. FastAPI must be running (start.bat).
class ApiConfig {
  // LAN IP of the demo laptop. Update if the IP changes (run `ipconfig` to check).
  static const _lanIp = '104.194.97.253';

  static String get baseUrl {
    const fromDefine = String.fromEnvironment('API_BASE');
    if (fromDefine.isNotEmpty) return fromDefine;
    if (kIsWeb) return 'http://localhost:8000';
    // Real Android device uses the laptop's LAN IP.
    // Emulator would use 10.0.2.2 — pass via --dart-define if testing in emulator.
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://$_lanIp:8000';
    }
    return 'http://localhost:8000';
  }
}

// Light theme
const Color kBgLight = Color(0xFFFFFFFF);
const Color kSurfaceLight = Color(0xFFF7FAF8);
const Color kCardLight = Color(0xFFFFFFFF);
const Color kBorderLight = Color(0xFFE1F5EE);
const Color kTextPrimaryLight = Color(0xFF0A2A1F);
const Color kTextSecondaryLight = Color(0xFF64748B);
const Color kTextHintLight = Color(0xFF94A3B8);

// Dark theme
const Color kBgDark = Color(0xFF04342C);
const Color kSurfaceDark = Color(0xFF0A3D2E);
const Color kCardDark = Color(0xFF0F4A36);
const Color kBorderDark = Color(0x331D9E75);
const Color kTextPrimaryDark = Color(0xFFFFFFFF);
const Color kTextSecondaryDark = Color(0x99E1F5EE);
const Color kTextHintDark = Color(0x669FE1CB);

// Same in both
const Color kTeal = Color(0xFF0F6E56);
const Color kTealMid = Color(0xFF1D9E75);
const Color kTealLight = Color(0xFF5DCAA5);
const Color kTealPale = Color(0xFFE1F5EE);
const Color kTealGlow = Color(0xFF9FE1CB);
const Color kTealDarkLeg = Color(0xFF085041);

// Status (same in both)
const Color kMedNew = Color(0xFF185FA5);
const Color kMedChanged = Color(0xFFBA7517);
const Color kMedContinued = Color(0xFF3B6D11);
const Color kMedDiscontinued = Color(0xFFA32D2D);
const Color kTier1 = Color(0xFFDC2626);
const Color kTier1Bg = Color(0xFFFEE2E2);
const Color kTier2 = Color(0xFFD97706);
const Color kTier2Bg = Color(0xFFFEF3C7);
const Color kTier3 = Color(0xFF16A34A);
const Color kTier3Bg = Color(0xFFF0FDF4);
