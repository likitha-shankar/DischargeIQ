// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

class _DiagnosisBody extends StatelessWidget {
  const _DiagnosisBody({
    required this.explanation,
    required this.extraction,
    this.documentType = '',
  });
  final String explanation;
  final dynamic extraction;

  /// Router classification - drives the per-diagnosis audio explainer.
  final String documentType;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final primaryDx = '${ext['primary_diagnosis'] ?? ''}';
    final rawSec = ext['secondary_diagnoses'];
    final secList = rawSec is List
        ? rawSec.map((e) => '$e').where((e) => e.isNotEmpty).toList()
        : <String>[];

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHero(
            icon: Icons.monitor_heart_outlined,
            title: 'What happened',
            subtitle: 'Your diagnosis, explained in plain words',
          ),
          if (documentType.isNotEmpty && documentType != 'unknown')
            AudioExplainerCard(documentType: documentType),
          if (primaryDx.isNotEmpty || secList.isNotEmpty) ...[
            if (primaryDx.isNotEmpty) ...[
              _DxLabel(label: 'Your main condition', dark: dark),
              const SizedBox(height: 4),
              _DxBadgeRow(text: primaryDx, dark: dark),
              // Provenance (trust feature): the exact document passage
              // Agent 1 extracted this diagnosis from.
              SourceQuote(source: ext['primary_diagnosis_source']),
            ],
            if (secList.isNotEmpty) ...[
              const SizedBox(height: 10),
              _DxLabel(label: 'Other conditions treated', dark: dark),
              const SizedBox(height: 4),
              ...secList.map((dx) => _DxBadgeRow(text: dx, dark: dark)),
            ],
            const SizedBox(height: 12),
            Divider(color: dark ? kBorderDark : kBorderLight),
            const SizedBox(height: 12),
          ],
          explanation.isEmpty
              ? Text(
                  'No explanation available.',
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                )
              : PatientText(text: explanation, collapsible: true),
        ],
      ),
    );
  }
}

class _DxLabel extends StatelessWidget {
  const _DxLabel({required this.label, required this.dark});
  final String label;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Text(
      label.toUpperCase(),
      style: TextStyle(
        fontSize: 10,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
        color: dark ? kTextSecondaryDark : kTextSecondaryLight,
      ),
    );
  }
}

class _DxBadgeRow extends StatelessWidget {
  const _DxBadgeRow({required this.text, required this.dark});
  final String text;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 18,
            height: 8,
            decoration: BoxDecoration(
              color: dark ? kTealLight : kTeal,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 14,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Medications tab - per-drug cards with status badge + expandable rationale.
class _MedicationsBody extends StatelessWidget {
  const _MedicationsBody({
    required this.rationaleText,
    required this.extraction,
    required this.simulator,
  });
  final String rationaleText;
  final dynamic extraction;
  final dynamic simulator;

  static const _borderColor = {
    'new': kMedNew,
    'changed': kMedChanged,
    'continued': kMedContinued,
    'discontinued': kMedDiscontinued,
  };

  static const _badgeLabel = {
    'new': 'NEW',
    'changed': 'CHANGED',
    'continued': 'CONTINUED',
    'discontinued': 'STOPPED',
  };

  Map<String, String> _parseRationale(String text) {
    final blocks = <String, String>{};
    for (final block in text.split(RegExp(r'\n\s*\n'))) {
      final trimmed = block.trim();
      if (trimmed.isEmpty) continue;
      final nl = trimmed.indexOf('\n');
      if (nl < 0) continue;
      var header = trimmed.substring(0, nl).trim();
      final body = trimmed.substring(nl + 1).trim();
      if (!header.endsWith(':') || body.isEmpty) continue;
      header = header.replaceAll(RegExp(r' [--] stopping:?$', caseSensitive: false), '').replaceAll(':', '').trim();
      if (header.isNotEmpty) blocks[header.toLowerCase()] = body;
    }
    return blocks;
  }

  String? _findRationale(String name, Map<String, String> blocks) {
    final needle = name.trim().toLowerCase();
    if (blocks.containsKey(needle)) return blocks[needle];
    for (final key in blocks.keys) {
      if (key.startsWith(needle) || needle.startsWith(key)) return blocks[key];
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ext = extraction is Map ? extraction as Map : <dynamic, dynamic>{};
    final meds = ext['medications'];
    final medList = meds is List ? meds.whereType<Map>().toList() : <Map>[];
    final rationale = _parseRationale(rationaleText);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 110),
      children: [
        const _SectionHero(
          icon: Icons.medication_outlined,
          title: 'Your medications',
          subtitle: 'What each one is for and how to take it',
        ),
        if (medList.isNotEmpty) ...[
          // Medication reminders (competitor-gap B1): patient-confirmed
          // daily nudges, scheduled locally on the phone only.
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            child: Material(
              color: dark ? kTeal.withValues(alpha: 0.2) : kTealPale,
              borderRadius: BorderRadius.circular(kRadiusField),
              child: InkWell(
                borderRadius: BorderRadius.circular(kRadiusField),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => MedicationRemindersScreen(
                      extraction: extraction is Map
                          ? (extraction as Map).cast<String, dynamic>()
                          : <String, dynamic>{},
                    ),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                  child: Row(
                    children: [
                      Icon(Icons.notifications_active_outlined,
                          size: 19, color: dark ? kTealGlow : kTeal),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          'Never miss a dose - set up daily reminders',
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: dark ? kTealGlow : kTeal,
                          ),
                        ),
                      ),
                      Icon(Icons.chevron_right,
                          size: 18, color: dark ? kTealGlow : kTeal),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
        if (medList.isEmpty)
          Text(
            'No medications found in this document.',
            style: TextStyle(color: dark ? kTextSecondaryDark : kTextSecondaryLight),
          )
        else
          ...medList.asMap().entries.map((e) {
            final med = e.value;
            final name = '${med['name'] ?? 'Unknown'}';
            final status = '${med['status'] ?? ''}'.toLowerCase();
            final dose = '${med['dose'] ?? ''}';
            final freq = '${med['frequency'] ?? ''}';
            final duration = '${med['duration'] ?? ''}';
            final details = [dose, freq, duration].where((s) => s.isNotEmpty).join(' · ');
            final borderCol = _borderColor[status] ?? kTextHintLight;
            final badgeTxt = _badgeLabel[status] ?? '';
            final rationaleBody = _findRationale(name, rationale);
            return _MedCard(
              name: name,
              details: details,
              status: status,
              borderColor: borderCol,
              badgeText: badgeTxt,
              rationale: rationaleBody,
              source: med['source'],
              dark: dark,
            );
          }),
        // AI-review questions BELOW the medication list - same rule as the
        // warning tab: the patient's actual content first, meta last.
        _GapCallout(
          simulator: simulator,
          keywords: const ['medication', 'medicine', 'drug', 'dose', 'pill', 'tablet', 'inhaler', 'insulin', 'prescription'],
          dark: dark,
        ),
      ],
    );
  }
}

class _MedCard extends StatefulWidget {
  const _MedCard({
    required this.name,
    required this.details,
    required this.status,
    required this.borderColor,
    required this.badgeText,
    required this.rationale,
    this.source,
    required this.dark,
  });
  final String name;
  final String details;
  final String status;
  final Color borderColor;
  final String badgeText;
  final String? rationale;
  final dynamic source; // SourceSpan map - provenance for this medication
  final bool dark;

  @override
  State<_MedCard> createState() => _MedCardState();
}

class _MedCardState extends State<_MedCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: widget.dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(kRadiusField),
        border: Border(left: BorderSide(color: widget.borderColor, width: 4)),
        boxShadow: widget.dark
            ? null
            : [const BoxShadow(color: Color(0x0A000000), blurRadius: 4, offset: Offset(0, 1))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.name,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                          color: widget.dark ? kTextPrimaryDark : kTextPrimaryLight,
                        ),
                      ),
                      if (widget.details.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          widget.details,
                          style: TextStyle(
                            fontSize: 12,
                            color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                          ),
                        ),
                      ],
                      SourceQuote(source: widget.source),
                      if (widget.status == 'changed') ...[
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF3C7),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'Changed from previous prescription',
                            style: TextStyle(fontSize: 10, color: Color(0xFF92400E)),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (widget.badgeText.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: widget.borderColor,
                      borderRadius: BorderRadius.circular(kRadiusField),
                    ),
                    child: Text(
                      widget.badgeText,
                      style: const TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (widget.rationale != null) ...[
            InkWell(
              borderRadius: const BorderRadius.only(
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(8),
              ),
              onTap: () => setState(() => _expanded = !_expanded),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    Text(
                      _expanded ? 'Hide explanation' : 'Why you\'re taking this',
                      style: TextStyle(
                        fontSize: 11,
                        color: widget.dark ? kTealGlow : kTeal,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(
                      _expanded ? Icons.expand_less : Icons.expand_more,
                      size: 14,
                      color: widget.dark ? kTealGlow : kTeal,
                    ),
                  ],
                ),
              ),
            ),
            if (_expanded)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: Text(
                  widget.rationale!,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: widget.dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ),
          ] else
            const SizedBox(height: 10),
        ],
      ),
    );
  }
}

/// Warning Signs tab - red-flag bullet list + 3-tier escalation cards with bullets.
