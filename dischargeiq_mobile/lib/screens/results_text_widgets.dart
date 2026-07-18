// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _RichTextSection extends StatelessWidget {
  const _RichTextSection({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 110),
      child: PatientText(text: text),
    );
  }
}

/// Renders agent text the way a patient should see it, not the way the model
/// wrote it: `# / ##` lines become styled section headings, `**bold**`
/// becomes bold, `- ` / `* ` lines become real bullets, and stray markdown
/// symbols never reach the screen. Deliberately tiny - the agents only ever
/// emit headings, bold, and bullets, so a markdown package would be dead
/// weight.
class PatientText extends StatelessWidget {
  const PatientText({
    super.key,
    required this.text,
    this.fontSize = 14.5,
    this.collapsible = false,
  });

  final String text;
  final double fontSize;

  /// When true and the text has 2+ headed sections, only the first section
  /// shows expanded; the rest collapse behind their headings (progressive
  /// disclosure for tired patients). NEVER set on safety-critical text -
  /// the escalation guide must stay fully visible.
  final bool collapsible;

  /// One parsed line: a heading (with level) or a body/bullet line.
  static ({int? headingLevel, String text, bool isBullet}) _parseLine(String rawLine) {
    final line = rawLine.trimRight();
    final heading = RegExp(r'^\s*(#{1,6})\s+(.*)$').firstMatch(line);
    if (heading != null) {
      return (
        headingLevel: heading.group(1)!.length,
        text: heading.group(2)!.replaceAll('*', '').trim(),
        isBullet: false,
      );
    }
    // Heading-intent lines the model wrapped in stray asterisks instead
    // ("*When to expect improvement:**") - treated as a level-2 heading.
    final stray = RegExp(r'^\s*\*{1,2}([^*]+?):?\*{1,2}\s*$').firstMatch(line);
    if (stray != null) {
      return (headingLevel: 2, text: stray.group(1)!.trim(), isBullet: false);
    }
    final bullet = RegExp(r'^\s*[-*•]\s+').firstMatch(line);
    if (bullet != null) {
      return (headingLevel: null, text: line.substring(bullet.end), isBullet: true);
    }
    return (headingLevel: null, text: line, isBullet: false);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final base = TextStyle(
      fontSize: fontSize,
      height: 1.5,
      color: dark ? kTextPrimaryDark : kTextPrimaryLight,
    );

    // Group lines into sections at heading boundaries so sections can
    // collapse. Section 0 is any preamble before the first heading.
    final sections = <({String? title, bool isTop, List<String> lines})>[];
    var current = (title: null as String?, isTop: false, lines: <String>[]);
    for (final rawLine in text.split('\n')) {
      final parsed = _parseLine(rawLine);
      if (parsed.headingLevel != null) {
        if (current.title != null || current.lines.any((l) => l.trim().isNotEmpty)) {
          sections.add(current);
        }
        current = (
          title: parsed.text,
          isTop: parsed.headingLevel! <= 1,
          lines: <String>[],
        );
      } else {
        current.lines.add(rawLine);
      }
    }
    if (current.title != null || current.lines.any((l) => l.trim().isNotEmpty)) {
      sections.add(current);
    }

    final headedCount = sections.where((s) => s.title != null && !s.isTop).length;
    final useCollapse = collapsible && headedCount >= 2;

    final children = <Widget>[];
    var expandedShown = false;
    for (final section in sections) {
      if (section.title != null) {
        if (useCollapse && !section.isTop) {
          if (expandedShown) {
            children.add(_CollapsibleSection(
              title: section.title!,
              dark: dark,
              fontSize: fontSize,
              child: _linesColumn(section.lines, base, dark),
            ));
            continue;
          }
          expandedShown = true;
        }
        children.add(Padding(
          padding: EdgeInsets.only(
              top: children.isEmpty ? 0 : (section.isTop ? 18 : 14), bottom: 6),
          child: Text(
            section.title!,
            style: TextStyle(
              fontSize: fontSize + (section.isTop ? 3.5 : 1.5),
              height: 1.3,
              fontWeight: FontWeight.w700,
              color: section.isTop
                  ? (dark ? kTextPrimaryDark : kTextPrimaryLight)
                  : (dark ? kTealGlow : kTeal),
            ),
          ),
        ));
      }
      children.add(_linesColumn(section.lines, base, dark));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  /// Render a section's body lines. Long runs (4+) of consecutive
  /// "Call your doctor..." bullets collapse into one expandable row so a
  /// tired reader sees the section, not a wall of near-identical lines.
  Widget _linesColumn(List<String> lines, TextStyle base, bool dark) {
    final children = <Widget>[];
    final pendingDoctorBullets = <String>[];

    void flushDoctorRun() {
      if (pendingDoctorBullets.length >= 4) {
        children.add(_CollapsibleSection(
          title: 'When to call your doctor (${pendingDoctorBullets.length})',
          dark: dark,
          fontSize: fontSize,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final b in pendingDoctorBullets) _bulletRow(b, base, dark),
            ],
          ),
        ));
      } else {
        for (final b in pendingDoctorBullets) {
          children.add(_bulletRow(b, base, dark));
        }
      }
      pendingDoctorBullets.clear();
    }

    for (final rawLine in lines) {
      final parsed = _parseLine(rawLine);
      if (parsed.text.trim().isEmpty) {
        flushDoctorRun();
        children.add(const SizedBox(height: 8));
        continue;
      }
      if (parsed.isBullet &&
          parsed.text.toLowerCase().startsWith('call your doctor')) {
        pendingDoctorBullets.add(parsed.text);
        continue;
      }
      flushDoctorRun();
      if (parsed.isBullet) {
        children.add(_bulletRow(parsed.text, base, dark));
      } else {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text.rich(TextSpan(children: _boldSpans(parsed.text, base))),
        ));
      }
    }
    flushDoctorRun();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  Widget _bulletRow(String text, TextStyle base, bool dark) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: EdgeInsets.only(top: fontSize * 0.42),
            child: Container(
              width: 5.5,
              height: 5.5,
              decoration: BoxDecoration(
                color: dark ? kTealGlow : kTeal,
                shape: BoxShape.circle,
              ),
            ),
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text.rich(TextSpan(children: _boldSpans(text, base))),
          ),
        ],
      ),
    );
  }

  /// Split `a **b** c` into styled spans; unmatched `**` markers are
  /// stripped - a patient should never see raw asterisks, and dropping a
  /// stray marker is safer than guessing what it meant to emphasise.
  static List<InlineSpan> _boldSpans(String line, TextStyle base) {
    final spans = <InlineSpan>[];
    final parts = line.split('**');
    if (parts.length.isEven) {
      return [TextSpan(text: line.replaceAll('**', ''), style: base)];
    }
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].isEmpty) continue;
      spans.add(TextSpan(
        text: parts[i],
        style: i.isOdd
            ? base.copyWith(fontWeight: FontWeight.w700)
            : base,
      ));
    }
    return spans;
  }
}

/// One collapsed content section: heading row with a chevron, body revealed
/// on tap. Styled to match PatientText subheadings so collapsed and expanded
/// sections read as the same document.
class _CollapsibleSection extends StatefulWidget {
  const _CollapsibleSection({
    required this.title,
    required this.dark,
    required this.fontSize,
    required this.child,
  });

  final String title;
  final bool dark;
  final double fontSize;
  final Widget child;

  @override
  State<_CollapsibleSection> createState() => _CollapsibleSectionState();
}

class _CollapsibleSectionState extends State<_CollapsibleSection> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final accent = widget.dark ? kTealGlow : kTeal;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () => setState(() => _open = !_open),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.title,
                    style: TextStyle(
                      fontSize: widget.fontSize + 1.5,
                      height: 1.3,
                      fontWeight: FontWeight.w700,
                      color: accent,
                    ),
                  ),
                ),
                Icon(
                  _open ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: accent,
                ),
              ],
            ),
          ),
        ),
        if (_open)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: widget.child,
          ),
      ],
    );
  }
}

/// Rich Discharge Check / AI Review tab - mirrors the Streamlit web UI.
/// Shows: HITL notice, gap score bar, severity-coded missed concept cards.
