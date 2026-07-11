/// screens/intro_screen.dart
///
/// Cinematic landing intro - the mobile mirror of the web version's
/// `_landing_intro_html()` in streamlit_app.py. Same timeline, colors, and
/// cadence: HELPING eyebrow, five rising phrase lines, phrase fade, then the
/// "Discharge" typewriter with blinking caret, "IQ" snap-in, subtitle, and a
/// graceful fade into the upload screen. Plays on every cold app launch
/// (matching the web, which replays per Streamlit session); Skip is always
/// available. Timers are cancelled on dispose and on Skip.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

// Web intro palette (fixed - the intro is always dark regardless of theme).
const _kStage = Color(0xFF04342C);
const _kLineColor = Color(0xFFE6EFE9);
const _kItalicTeal = Color(0xFF5DCAA5);
const _kWordmarkTeal = Color(0xFF1FA47F);
const _kEyebrow = Color(0x8CBED2C8); // rgba(190,210,200,0.55)
const _kSubtitle = Color(0x80BED2C8); // rgba(190,210,200,0.5)

const _kEaseOut = Cubic(0.32, 0.72, 0, 1); // web cubic-bezier(.32,.72,0,1)

class IntroScreen extends StatefulWidget {
  const IntroScreen({super.key, required this.onDone});

  /// Called once the stage has fully faded - parent swaps to the upload
  /// screen (web equivalent: the hidden advance button click).
  final VoidCallback onDone;

  @override
  State<IntroScreen> createState() => _IntroScreenState();
}

class _IntroScreenState extends State<IntroScreen> {
  final List<Timer> _timers = [];
  Timer? _caretTimer;
  Timer? _typeTimer;

  bool _eyebrow = false;
  final List<bool> _lines = [false, false, false, false, false];
  bool _phraseGone = false;
  bool _logoVisible = false;
  String _typed = '';
  bool _showIq = false;
  bool _caretVisible = true;
  bool _caretOn = true;
  bool _subtitle = false;
  bool _decorGone = false;
  bool _stageGone = false;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    // Caret blink: web is 720ms step-start.
    _caretTimer = Timer.periodic(const Duration(milliseconds: 360), (_) {
      if (mounted && _caretVisible) setState(() => _caretOn = !_caretOn);
    });
    _runTimeline();
  }

  void _at(int ms, VoidCallback fn) {
    _timers.add(Timer(Duration(milliseconds: ms), () {
      if (mounted) setState(fn);
    }));
  }

  /// Web timeline verbatim (ms): phrase 300-2500, fade 4500, logo 4700,
  /// decorations out 7400, logo out 7800, stage out 8300, advance 9100.
  void _runTimeline() {
    _at(300, () => _eyebrow = true);
    _at(850, () => _lines[0] = true);
    _at(1250, () => _lines[1] = true);
    _at(1650, () => _lines[2] = true);
    _at(2050, () => _lines[3] = true);
    _at(2500, () => _lines[4] = true);
    _at(4500, () => _phraseGone = true);
    _at(4700, () {
      _logoVisible = true;
      _startTypewriter();
    });
    _at(7400, () => _decorGone = true);
    _at(7800, () => _logoVisible = false);
    _at(8300, () => _stageGone = true);
    _timers.add(Timer(const Duration(milliseconds: 9100), _finish));
  }

  /// "Discharge" at ~90ms/char, then IQ snaps in as the caret hides
  /// (simultaneous, so there is no caret-jump artifact), subtitle 350ms later.
  void _startTypewriter() {
    const word = 'Discharge';
    var i = 0;
    _typeTimer = Timer.periodic(const Duration(milliseconds: 90), (t) {
      if (!mounted) return t.cancel();
      i++;
      setState(() => _typed = word.substring(0, i));
      if (i >= word.length) {
        t.cancel();
        _at(240, () {
          _showIq = true;
          _caretVisible = false;
        });
        _at(590, () => _subtitle = true);
      }
    });
  }

  /// Skip mirrors the web path: decorations and content fade, stage fades
  /// 400ms later, advance at 1200ms.
  void _skip() {
    for (final t in _timers) {
      t.cancel();
    }
    _typeTimer?.cancel();
    setState(() {
      _decorGone = true;
      _phraseGone = true;
      _logoVisible = false;
    });
    _timers.add(Timer(const Duration(milliseconds: 400), () {
      if (mounted) setState(() => _stageGone = true);
    }));
    _timers.add(Timer(const Duration(milliseconds: 1200), _finish));
  }

  void _finish() {
    if (_done || !mounted) return;
    _done = true;
    widget.onDone();
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    _caretTimer?.cancel();
    _typeTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light, // dark stage → light status icons
      child: Scaffold(
        backgroundColor: _kStage,
        body: AnimatedOpacity(
          opacity: _stageGone ? 0 : 1,
          duration: const Duration(milliseconds: 700),
          curve: _kEaseOut,
          child: Stack(
            fit: StackFit.expand,
            children: [
              // Vignette - soft teal radial glow at center, like the web.
              AnimatedOpacity(
                opacity: _decorGone ? 0 : 1,
                duration: const Duration(milliseconds: 700),
                curve: _kEaseOut,
                child: const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      colors: [Color(0x380F6E56), Colors.transparent],
                      stops: [0.0, 0.55],
                    ),
                  ),
                ),
              ),
              // Phrase block.
              Center(
                child: AnimatedOpacity(
                  opacity: _phraseGone ? 0 : 1,
                  duration: const Duration(milliseconds: 600),
                  curve: _kEaseOut,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _Rise(
                        show: _eyebrow,
                        child: const Padding(
                          padding: EdgeInsets.only(bottom: 20),
                          child: Text(
                            'HELPING',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              letterSpacing: 5.5,
                              color: _kEyebrow,
                            ),
                          ),
                        ),
                      ),
                      for (final (i, text) in const [
                        'patients',
                        'understand',
                        'everything',
                        'the doctor',
                      ].indexed)
                        _Rise(show: _lines[i], child: _phraseLine(text)),
                      _Rise(
                        show: _lines[4],
                        child: Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: _phraseLine('just told them.',
                              italic: true, color: _kItalicTeal),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              // Logo block - typewriter wordmark + caret + IQ + subtitle.
              Center(
                child: AnimatedOpacity(
                  opacity: _logoVisible ? 1 : 0,
                  duration: const Duration(milliseconds: 600),
                  curve: _kEaseOut,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Text(_typed, style: _wordmarkStyle),
                          if (_caretVisible)
                            Opacity(
                              opacity: _caretOn ? 1 : 0,
                              child: Container(
                                width: 3,
                                height: 32,
                                margin: const EdgeInsets.only(left: 3, right: 2),
                                color: _kWordmarkTeal,
                              ),
                            ),
                          if (_showIq) const Text('IQ', style: _wordmarkStyle),
                        ],
                      ),
                      const SizedBox(height: 20),
                      AnimatedOpacity(
                        opacity: _subtitle ? 1 : 0,
                        duration: const Duration(milliseconds: 800),
                        curve: _kEaseOut,
                        child: const Text(
                          'YOUR DISCHARGE, SIMPLIFIED.',
                          style: TextStyle(
                            fontSize: 12,
                            letterSpacing: 1.4,
                            color: _kSubtitle,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              // Skip pill, top-right - always available.
              Positioned(
                top: 12,
                right: 16,
                child: SafeArea(
                  child: AnimatedOpacity(
                    opacity: _decorGone ? 0 : 1,
                    duration: const Duration(milliseconds: 450),
                    child: OutlinedButton(
                      onPressed: _decorGone ? null : _skip,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white70,
                        side: const BorderSide(color: Colors.white24),
                        shape: const StadiumBorder(),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        minimumSize: const Size(48, 34),
                      ),
                      child: const Text(
                        'SKIP',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static const _wordmarkStyle = TextStyle(
    fontSize: 46,
    fontWeight: FontWeight.w600,
    letterSpacing: -1.5,
    color: _kWordmarkTeal,
    height: 1,
  );

  static Widget _phraseLine(String text,
      {bool italic = false, Color color = _kLineColor}) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 34,
        fontWeight: italic ? FontWeight.w600 : FontWeight.w500,
        fontStyle: italic ? FontStyle.italic : FontStyle.normal,
        height: 1.14,
        letterSpacing: -0.2,
        color: color,
      ),
    );
  }
}

/// Fade + 16px upward rise, 800ms - the web `.line` transition.
class _Rise extends StatelessWidget {
  const _Rise({required this.show, required this.child});

  final bool show;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      opacity: show ? 1 : 0,
      duration: const Duration(milliseconds: 800),
      curve: _kEaseOut,
      child: AnimatedSlide(
        offset: show ? Offset.zero : const Offset(0, 0.35),
        duration: const Duration(milliseconds: 800),
        curve: _kEaseOut,
        child: child,
      ),
    );
  }
}
