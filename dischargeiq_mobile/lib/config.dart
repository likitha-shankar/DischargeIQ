import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

/// API base URL - override at build time with `--dart-define=API_BASE=http://...`
///
/// Resolution order:
///   1. --dart-define=API_BASE (always wins, debug and release)
///   2. Release builds default to the hosted Cloud Run backend. The nginx
///      proxy there routes only `/api/*` to FastAPI, so the base includes
///      the `/api` prefix - endpoints are appended as `/analyze`, `/chat`.
///   3. Debug builds default to a local FastAPI (no `/api` prefix - local
///      uvicorn serves routes at the root).
///
/// Local real-device demo: `flutter run --dart-define=API_BASE=http://<laptop-lan-ip>:8000`
/// Phone and laptop must be on the same Wi-Fi. FastAPI must be running (start.sh).
class ApiConfig {
  // Hosted backend (Cloud Run, project dischargeiq-502723, migrated
  // July 2026). `/api` prefix required.
  static const _cloudRunBase =
      'https://dischargeiq-678599658918.us-central1.run.app/api';

  static String get baseUrl {
    const fromDefine = String.fromEnvironment('API_BASE');
    if (fromDefine.isNotEmpty) return fromDefine;
    // Release builds must work on any network, so they talk to Cloud Run.
    if (kReleaseMode) return _cloudRunBase;
    if (kIsWeb) return 'http://localhost:8000';
    // Android debug defaults to the emulator's host loopback. A physical
    // device MUST pass the laptop's address explicitly:
    //   flutter run --dart-define=API_BASE=http://<laptop-lan-ip>:8000
    // Never hardcode that address here - a stale entry can point at a public
    // IP and send document text over plain HTTP to whoever holds it now.
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  /// Bearer token for the backend, supplied at build time with
  /// `--dart-define=API_KEY=<key>`.
  ///
  /// Empty by default so a local uvicorn with no `DISCHARGEIQ_API_KEY` still
  /// works untouched. Release builds that talk to the hosted backend MUST
  /// pass it, because that deployment requires the key:
  ///   flutter build apk --release \
  ///     --dart-define=API_KEY=$DISCHARGEIQ_API_KEY
  ///
  /// Not a secret from the patient holding the phone - it is a spend gate that
  /// stops anonymous internet traffic from running the pipeline on our bill.
  static const String apiKey = String.fromEnvironment('API_KEY');
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

// ── Dark-theme semantic colours ───────────────────────────────────────────────
// The colours above were chosen against a white background and are used
// unchanged in dark mode, where they fail WCAG badly. Measured against the dark
// card (#0F4A36) on 6 Sep 2026:
//
//     kTier1            2.12:1   <- the CALL 911 colour
//     kMedDiscontinued  1.45:1
//     kMedNew           1.57:1
//     kMedContinued     1.65:1
//     kMedChanged       2.75:1
//     kTier3            3.10:1
//     kTier2            3.21:1
//
// AA needs 4.5:1 for body text and 3.0:1 for large text, so most of these fail
// even the lenient bar. kTier1 is the worst place for it: a patient reading the
// escalation guide in dark mode gets the emergency tier in the least legible
// colour on the screen.
//
// Each value below is the MOST SATURATED colour at the original hue that
// reaches 4.5:1. Saturation is preserved deliberately - the naive fix is to
// lighten until it passes, which turns the 911 red into a pastel pink and
// throws away the urgency the colour is carrying. Emotional weight and
// legibility are both requirements here, not a trade.
//
// kMedDiscontinuedDark is pulled toward a muted rose rather than sharing
// kTier1Dark's vivid red: at the same hue and saturation the two were
// indistinguishable, and "stopped taking this" must not read as "call 911".
//
// Enforced by dischargeiq/tests/test_palette_contrast.py, which recomputes
// every ratio from these hex values.
const Color kTier1Dark = Color(0xFFFF8A8A);
const Color kTier2Dark = Color(0xFFFF900F);
const Color kTier3Dark = Color(0xFF00C749);
const Color kMedNewDark = Color(0xFF61B1FF);
const Color kMedChangedDark = Color(0xFFFFB259);
const Color kMedContinuedDark = Color(0xFF5BC700);
const Color kMedDiscontinuedDark = Color(0xFFD9A0A0);

/// Semantic colour for the current theme. Use these instead of the raw
/// constants anywhere a colour sits on a themed surface.
Color tier1Colour(bool dark) => dark ? kTier1Dark : kTier1;
Color tier2Colour(bool dark) => dark ? kTier2Dark : kTier2;
Color tier3Colour(bool dark) => dark ? kTier3Dark : kTier3;
Color medNewColour(bool dark) => dark ? kMedNewDark : kMedNew;
Color medChangedColour(bool dark) => dark ? kMedChangedDark : kMedChanged;
Color medContinuedColour(bool dark) => dark ? kMedContinuedDark : kMedContinued;
Color medDiscontinuedColour(bool dark) =>
    dark ? kMedDiscontinuedDark : kMedDiscontinued;
