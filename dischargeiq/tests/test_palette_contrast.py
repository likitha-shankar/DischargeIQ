"""
WCAG contrast enforcement for the mobile colour palette.

LOF review action item, 26 Aug 2026 (34:05): UI refinements including colour
palette adjustments for emotional impact and accessibility.

The accessibility half is measurable, so it is measured here rather than
eyeballed. Ratios are recomputed from the hex values in config.dart on every
run, so a colour cannot be nudged for aesthetic reasons and silently drop below
the bar.

What this found on 6 Sep 2026: the semantic colours were all chosen against a
white background and used unchanged in dark mode, where seven of them failed.
kTier1 - the CALL 911 colour - scored 2.12:1 against the dark card, below even
the 3.0:1 large-text bar. A patient reading the escalation guide in dark mode
was getting the emergency tier in the least legible colour on the screen.

WCAG 2.1 AA: 4.5:1 for body text, 3.0:1 for large or bold text.
"""

import re
from pathlib import Path

import pytest

_CONFIG = (Path(__file__).resolve().parents[2]
           / "dischargeiq_mobile" / "lib" / "config.dart")

#: Surfaces a semantic colour is drawn on.
_LIGHT_CARD = "FFFFFF"
_DARK_CARD = "0F4A36"   # kCardDark

_AA_BODY = 4.5
_AA_LARGE = 3.0


def _channel(value: int) -> float:
    """sRGB channel to linear light, per WCAG."""
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_colour: str) -> float:
    """Relative luminance of an RRGGBB or AARRGGBB hex string."""
    h = hex_colour.lstrip("#")
    if len(h) == 8:      # Flutter's 0xAARRGGBB - drop alpha
        h = h[2:]
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _palette() -> dict[str, str]:
    """Read every colour constant straight out of config.dart."""
    source = _CONFIG.read_text(encoding="utf-8")
    found = re.findall(r"const Color (k\w+) = Color\(0x([0-9A-Fa-f]{8})\)", source)
    return {name: value for name, value in found}


#: Semantic colours and the theme surface each is actually drawn on.
_DARK_TOKENS = [
    "kTier1Dark", "kTier2Dark", "kTier3Dark",
    "kMedNewDark", "kMedChangedDark", "kMedContinuedDark",
    "kMedDiscontinuedDark",
]
_LIGHT_TOKENS = [
    "kTier1", "kTier2", "kTier3",
    "kMedNew", "kMedChanged", "kMedContinued", "kMedDiscontinued",
]


class TestDarkThemeSemanticColours:
    """The set that did not exist before and is the reason for this file."""

    @pytest.mark.parametrize("token", _DARK_TOKENS)
    def test_meets_aa_body_text_on_the_dark_card(self, token):
        palette = _palette()
        assert token in palette, f"{token} missing from config.dart"
        ratio = contrast(palette[token], _DARK_CARD)
        assert ratio >= _AA_BODY, (
            f"{token} is {ratio:.2f}:1 on the dark card, below AA's "
            f"{_AA_BODY}:1. Pick a lighter value at the same hue."
        )

    def test_the_emergency_colour_is_the_one_to_watch(self):
        """
        kTier1 is CALL 911. It was 2.12:1 in dark mode - worse than every
        other semantic colour, in the place where legibility matters most.
        """
        ratio = contrast(_palette()["kTier1Dark"], _DARK_CARD)
        assert ratio >= _AA_BODY

    def test_stopped_medication_is_not_mistakable_for_an_emergency(self):
        """
        Both are red. At matching hue and saturation they were the same
        colour, and "you stopped taking this" must never read as "call 911".
        """
        palette = _palette()
        def rgb(name):
            h = palette[name][2:]
            return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
        a, b = rgb("kTier1Dark"), rgb("kMedDiscontinuedDark")
        distance = sum(abs(x - y) for x, y in zip(a, b))
        assert distance >= 60, (
            f"kTier1Dark and kMedDiscontinuedDark differ by only {distance}; "
            "they will look like the same colour."
        )


class TestLightThemeSemanticColours:
    """The originals. These were designed on white and mostly hold up."""

    @pytest.mark.parametrize("token", _LIGHT_TOKENS)
    def test_meets_at_least_the_large_text_bar_on_white(self, token):
        """
        Large-text bar, not body. These are used as icon tints and bold
        labels rather than paragraphs, and holding them to 4.5:1 would force
        a redesign of colours that are legible in practice.
        """
        ratio = contrast(_palette()[token], _LIGHT_CARD)
        assert ratio >= _AA_LARGE, (
            f"{token} is {ratio:.2f}:1 on white, below {_AA_LARGE}:1"
        )


class TestEveryDarkTokenHasALightCounterpart:
    """A dark variant with no partner is a colour nobody will remember to use."""

    @pytest.mark.parametrize("dark_token", _DARK_TOKENS)
    def test_pairs_up(self, dark_token):
        assert dark_token.removesuffix("Dark") in _palette()


class TestSectionDesignTokens:
    """
    section_design.dart darkens colours for AA on white, which necessarily
    lowers their contrast on the dark card. That trade was made without
    checking the other side: sdDanger landed at 1.58:1 in dark mode, and
    results_warnings_body.dart - the escalation guide - uses these tokens
    fifteen times.
    """

    @staticmethod
    def _section_palette() -> dict[str, str]:
        source = (_CONFIG.parent / "section_design.dart").read_text(encoding="utf-8")
        return dict(re.findall(
            r"const Color (sd\w+) = Color\(0x([0-9A-Fa-f]{8})\)", source))

    @pytest.mark.parametrize("token", ["sdDanger", "sdSafe", "sdChanged"])
    def test_light_variants_still_pass_on_white(self, token):
        palette = self._section_palette()
        assert token in palette, f"{token} is referenced but never defined"
        assert contrast(palette[token], _LIGHT_CARD) >= _AA_BODY

    @pytest.mark.parametrize("alias,source_token", [
        ("sdDangerDark", "kTier1Dark"),
        ("sdSafeDark", "kTier3Dark"),
        ("sdChangedDark", "kMedChangedDark"),
    ])
    def test_dark_variants_reuse_the_validated_tokens(self, alias, source_token):
        """
        One red should mean one thing everywhere. A parallel set of dark
        section colours would drift from the config ones over time, so these
        alias rather than redefine - and the aliasing is asserted so a future
        edit cannot quietly fork them.
        """
        source = (_CONFIG.parent / "section_design.dart").read_text(encoding="utf-8")
        assert f"const Color {alias} = {source_token};" in source

    def test_sd_changed_is_actually_defined(self):
        """
        It was documented in the file header from the redesign onward and
        never declared, so the accessor that used it did not compile. The
        header described a token that did not exist.
        """
        assert "sdChanged" in self._section_palette()


class TestForegroundColoursAreNotUsedAsBackgrounds:
    """
    The dark variants are FOREGROUND colours. Swapping them in blindly is a
    real hazard, not a hypothetical one.

    sdDanger is used two ways in the warning-signs tab: as the CALL 911 header
    fill and button background with white text on it, and as text and icon
    colour. White on sdDanger (#B91C1C) is 6.47:1 and fine. White on
    sdDangerDark (#FF8A8A) is 2.27:1 and unreadable, so a blanket
    find-and-replace would have made the emergency banner worse than the bug
    it was fixing.
    """

    def test_white_stays_readable_on_the_light_danger_fill(self):
        assert contrast("FFFFFF", "B91C1C") >= _AA_BODY

    def test_white_would_fail_on_the_dark_variant(self):
        """Documents WHY backgrounds keep the original colour."""
        assert contrast("FFFFFF", "FF8A8A") < _AA_LARGE

    def test_no_background_property_uses_a_dark_token(self):
        """
        Guards the mistake directly. A dark foreground token appearing in a
        backgroundColor is the failure this class exists to prevent.
        """
        lib = _CONFIG.parent
        offenders = []
        for path in lib.rglob("*.dart"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "Dark" not in line:
                    continue
                if any(key in line for key in ("backgroundColor:", "fillColor:")):
                    if any(t in line for t in ("sdDangerDark", "kTier1Dark",
                                               "sdSafeDark", "kTier3Dark")):
                        offenders.append(f"{path.name}:{number}")
        assert not offenders, (
            f"foreground dark tokens used as a background fill: {offenders}. "
            "White text on those is unreadable."
        )


class TestTheMathItself:
    """Guard the ratio function, since every other test trusts it."""

    def test_black_on_white_is_21_to_1(self):
        assert round(contrast("000000", "FFFFFF"), 1) == 21.0

    def test_identical_colours_are_1_to_1(self):
        assert round(contrast("0F4A36", "0F4A36"), 2) == 1.0

    def test_alpha_prefix_is_ignored(self):
        """Flutter writes 0xAARRGGBB; the alpha byte must not skew luminance."""
        assert contrast("FF000000", "FFFFFF") == contrast("000000", "FFFFFF")
