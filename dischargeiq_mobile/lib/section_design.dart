/// section_design.dart
///
/// Design tokens and shared containers for the three redesigned result
/// sections: What happened, Warning signs, and Recovery. The other four tabs
/// keep the original styling from config.dart, so this file deliberately
/// carries only what those three need.
///
/// It is a SEPARATE file from config.dart because it darkens four hues that
/// fail WCAG AA at the small label sizes this design uses. Every hue family
/// is otherwise the same:
///
///   kMedChanged   #BA7517  3.38:1  ->  sdChanged  #8F5A10  5.60:1
///   kTier1        #DC2626  4.47:1  ->  sdDanger   #B91C1C  5.90:1
///   kTier3        #16A34A  3.30:1  ->  sdSafe     #15803D  4.90:1
///   kTextHint     #94A3B8  2.56:1  ->  sdTextMute #5B6E68  5.42:1
///   kTextSecondary#64748B  4.14:1  ->  sdTextSub  #55627A  6.15:1
///
/// kTeal, kTealPale, kTealLight and kTealGlow already pass and are
/// re-exported unchanged, which is what keeps these sections looking like the
/// same app as the four they sit beside.
library;

import 'package:flutter/material.dart';

import 'package:dischargeiq_mobile/config.dart';

// Re-exported from config.dart, unchanged.
const Color sdTeal = kTeal;
const Color sdTealPale = kTealPale;
const Color sdTealLight = kTealLight;
const Color sdTealGlow = kTealGlow;

// Darkened one step for AA.
const Color sdDanger = Color(0xFFB91C1C);
const Color sdSafe = Color(0xFF15803D);
// Documented in this file's header since the redesign but never actually
// defined, so `changed` had nothing to resolve to. #8F5A10 is the value the
// header specified: kMedChanged darkened to 5.77:1 on white.
const Color sdChanged = Color(0xFF8F5A10);
const Color sdTextMute = Color(0xFF5B6E68);
const Color sdTextSub = Color(0xFF55627A);

// ── Dark-theme semantic colours ──────────────────────────────────────────────
// The five colours above are DARKENED versions of the config.dart originals,
// chosen to pass AA against white. That made light mode better and dark mode
// worse, and nothing checked. Measured against sdCardDark (#0F4A36) on
// 6 Sep 2026:
//
//     sdDanger    1.58:1     sdSafe      2.04:1     sdChanged   1.77:1
//     sdTextMute  1.89:1     sdTextSub   1.66:1
//
// The two TEXT colours turned out to be already handled: SectionPalette has
// carried dark variants for textMute and textSub since the redesign. Only the
// three SEMANTIC colours were unprotected.
//
// AA wants 4.5:1, and the lenient large-text bar is 3.0:1. Every one of these
// is below both. results_warnings_body.dart uses these tokens fifteen times,
// so in dark mode the Warning Signs tab - the escalation guide - was rendering
// its danger colour at 1.58:1, which is very close to invisible.
//
// The three semantic colours reuse the tokens already validated in config.dart
// rather than inventing parallel values: one red means one thing everywhere,
// and a second set would drift. The two text colours are neutral light greens
// chosen to stay muted; the naive hue-preserving fix pushed sdTextMute to a
// vivid green, which passes contrast and stops looking like secondary text.
//
// Enforced by dischargeiq/tests/test_palette_contrast.py.
const Color sdDangerDark = kTier1Dark;
const Color sdSafeDark = kTier3Dark;
const Color sdChangedDark = kMedChangedDark;
// NOTE: no sdTextMuteDark / sdTextSubDark. The SectionPalette accessors below
// already carry dark variants for both, as translucent whites over the dark
// card, and they pass. Adding a second pair would have been duplicate tokens
// solving a solved problem - caught by the analyzer, not by reading.

// Surfaces.
const Color sdInk = Color(0xFF0A2A1F);
const Color sdCard = Color(0xFFFFFFFF);
const Color sdLine = Color(0xFFDCE4E3);
const Color sdLineSoft = Color(0xFFF1F4F5);

// Tier tints. Tier 1 is solid rather than tinted: the one hierarchy in this
// app that must not read as flat.
const Color sdDangerTint = Color(0xFFFEF2F2);
const Color sdDangerLine = Color(0xFFFBD5D5);
const Color sdWarn = Color(0xFFD97706);
const Color sdWarnTint = Color(0xFFFFFBF3);
const Color sdWarnLine = Color(0xFFF5CE8E);
const Color sdWarnInk = Color(0xFF92400E);
const Color sdSafeTint = Color(0xFFF5FBF6);
const Color sdSafeLine = Color(0xFFC7E7CE);
const Color sdSafeInk = Color(0xFF14532D);

// Dark-mode surfaces. These sections respect the existing theme switch.
const Color sdCardDark = Color(0xFF0F4A36);
const Color sdLineDark = Color(0x331D9E75);

/// Radii. Rounder than kRadiusCard (12) at the container level.
const double sdRadiusCard = 20;
const double sdRadiusInner = 13;

/// The one place these sections decide light-versus-dark values.
class SectionColors {
  SectionColors(this.dark);

  final bool dark;

  Color get danger => dark ? sdDangerDark : sdDanger;
  Color get safe => dark ? sdSafeDark : sdSafe;
  Color get changed => dark ? sdChangedDark : sdChanged;
  Color get card => dark ? sdCardDark : sdCard;
  Color get line => dark ? sdLineDark : sdLine;
  Color get lineSoft => dark ? sdLineDark : sdLineSoft;
  Color get text => dark ? Colors.white : sdInk;
  Color get textSub => dark ? const Color(0xCCE1F5EE) : sdTextSub;
  // 0x99 (60% alpha) measured 4.36:1 against sdCardDark on 16 Aug 2026,
  // under the 4.5 WCAG AA floor for small text - and this token carries
  // dates, hints and secondary labels, all of which are small. 0xA5 (65%)
  // measures 4.80:1, which clears it with margin rather than by a hair.
  Color get textMute => dark ? const Color(0xA5E1F5EE) : sdTextMute;
  Color get accent => dark ? sdTealGlow : sdTeal;
  Color get accentTint => dark ? kTeal.withValues(alpha: 0.22) : sdTealPale;

  static SectionColors of(BuildContext context) =>
      SectionColors(Theme.of(context).brightness == Brightness.dark);
}

/// Small caps label opening a section, in place of the 52px hero that used to
/// repeat the tab name back at the patient.
class SectionEyebrow extends StatelessWidget {
  const SectionEyebrow(this.text, {super.key, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    return Text(
      text.toUpperCase(),
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.9,
        color: color ?? c.accent,
      ),
    );
  }
}

/// The plain-language sentence a patient reads first. Large, light, and never
/// a form label.
class SectionHeadline extends StatelessWidget {
  const SectionHeadline(this.text, {super.key, this.size = 24});

  final String text;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    // header: true lets a screen-reader user jump between sections by
    // heading instead of swiping through every line of a discharge summary.
    return Semantics(
      header: true,
      child: Text(
        text,
        style: TextStyle(
          fontSize: size,
          height: 1.24,
          letterSpacing: -0.3,
          fontWeight: FontWeight.w400,
          color: c.text,
        ),
      ),
    );
  }
}

/// Small uppercase label inside a card ("MAIN CONDITION", "ALSO TREATED").
class SectionMiniLabel extends StatelessWidget {
  const SectionMiniLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    return Text(
      text.toUpperCase(),
      style: TextStyle(
        fontSize: 10.5,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.8,
        color: c.textMute,
      ),
    );
  }
}

/// Standard container for these sections. One idea per card.
class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.onTap,
    this.color,
    this.border,
  });

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color? color;
  final Color? border;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    final body = Padding(padding: padding, child: child);
    return Container(
      decoration: BoxDecoration(
        color: color ?? c.card,
        borderRadius: BorderRadius.circular(sdRadiusCard),
        border: Border.all(color: border ?? c.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? body
          : Material(
              color: Colors.transparent,
              child: InkWell(onTap: onTap, child: body),
            ),
    );
  }
}

/// Shared scroll wrapper: consistent padding, and the same 110px bottom room
/// every other tab leaves so the chat button never covers the last card.
class SectionScroll extends StatelessWidget {
  const SectionScroll({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }
}
