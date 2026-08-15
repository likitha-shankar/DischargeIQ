/// services/escalation_tiers.dart
///
/// Splits Agent 5's escalation guide into its three tiers.
///
/// The extraction schema carries `red_flag_symptoms` as ONE flat list with no
/// tier information. The tiers exist only in the escalation prose, under the
/// fixed headers Agent 5 is contractually required to emit (see
/// dischargeiq/agents/escalation_agent.py, which fails the agent outright if
/// the CALL 911 header is missing).
///
/// So any UI that wants to show "call 911 / go to the ER / call your doctor"
/// separately has to parse them out of that prose. This is the one place that
/// happens, because getting a symptom into the wrong tier is the most
/// dangerous mistake this app could make.
///
/// Pure Dart, no Flutter, so the parsing is unit-testable.
library;

/// One symptom line, split into the part a frightened patient scans for and
/// the part that tells them why it matters.
///
/// Agent 5 writes "Symptom: why it matters". Both halves are kept: the
/// symptom carries the scan, the explanation is what made the original design
/// more useful than a bare list of two-word phrases.
class EscalationItem {
  const EscalationItem(this.symptom, this.detail);

  /// The symptom itself, e.g. "Unresponsive or cannot be woken".
  final String symptom;

  /// Agent 5's explanation, or empty when the line carried none.
  final String detail;

  /// Symptom and explanation as one line, for read-aloud and search.
  @override
  String toString() => detail.isEmpty ? symptom : '$symptom: $detail';
}

/// Symptoms grouped by urgency. Any tier may be empty.
class EscalationTiers {
  const EscalationTiers({
    required this.call911,
    required this.erToday,
    required this.callDoctor,
  });

  /// Life-threatening: call emergency services now.
  final List<EscalationItem> call911;

  /// Urgent: be seen today, but not an ambulance call.
  final List<EscalationItem> erToday;

  /// Non-urgent: raise it with the care team during office hours.
  final List<EscalationItem> callDoctor;

  bool get isEmpty =>
      call911.isEmpty && erToday.isEmpty && callDoctor.isEmpty;

  static const empty =
      EscalationTiers(call911: [], erToday: [], callDoctor: []);
}

/// Tier headers, in the order Agent 5 emits them.
///
/// Matched on the SHORT form ("CALL 911" rather than "CALL 911 IMMEDIATELY")
/// because the backend only guarantees the short form - escalation_agent.py
/// gates on `"CALL 911" not in text.upper()` and warns on "GO TO THE ER" and
/// "CALL YOUR DOCTOR". Matching the longer wording would silently produce an
/// empty tier if the model shortened a heading.
const _kTierHeaders = ['CALL 911', 'GO TO THE ER', 'CALL YOUR DOCTOR'];

/// A symptom line long enough to be a paragraph is not a symptom - it is prose
/// that happened to start with a dash. Guards against rendering a wall of text
/// inside a tier chip.
const _kMaxSymptomLength = 120;

/// Parse the three tiers out of the escalation guide.
///
/// Each tier's section runs from its header to the next header found. Within a
/// section, bulleted lines are the symptoms; the explanation after the first
/// colon is dropped so the caller gets the symptom alone.
///
/// Args:
///   guide: `escalation_guide` from the pipeline response.
///
/// Returns:
///   [EscalationTiers]; every list is empty when the guide is missing or has
///   no recognisable headers, which callers must treat as "show the prose
///   instead" rather than "this patient has no warning signs".
EscalationTiers parseEscalationTiers(String? guide) {
  final text = guide ?? '';
  if (text.trim().isEmpty) return EscalationTiers.empty;

  final upper = text.toUpperCase();

  // Locate each header once, so a tier whose header is missing simply yields
  // an empty list rather than swallowing the following tier's content.
  final starts = <int>[];
  for (final header in _kTierHeaders) {
    starts.add(upper.indexOf(header));
  }

  List<EscalationItem> sectionFor(int tier) {
    final start = starts[tier];
    if (start < 0) return const [];
    // The section ends at the next header that actually appears AFTER this
    // one. Headers can be missing, so this cannot just be starts[tier + 1].
    var end = text.length;
    for (var next = tier + 1; next < starts.length; next++) {
      if (starts[next] > start) {
        end = starts[next];
        break;
      }
    }
    return _symptomsIn(text.substring(start, end));
  }

  return EscalationTiers(
    call911: sectionFor(0),
    erToday: sectionFor(1),
    callDoctor: sectionFor(2),
  );
}

/// Bulleted symptom lines within one tier section, cleaned for display.
///
/// Splits "Symptom: why it matters" at the FIRST colon and keeps both halves.
/// The length guard still applies to the symptom alone, so a paragraph that
/// merely starts with a dash is rejected as before - but an explanation of any
/// length rides along with its symptom instead of being thrown away.
List<EscalationItem> _symptomsIn(String section) {
  final out = <EscalationItem>[];
  for (final raw in section.split('\n')) {
    final line = raw.trim();
    if (!line.startsWith('-') && !line.startsWith('•') && !line.startsWith('*')) {
      continue;
    }
    final stripped = line.replaceFirst(RegExp(r'^[-•*]\s*'), '');
    final colon = stripped.indexOf(':');
    final symptom = (colon > 0 ? stripped.substring(0, colon) : stripped).trim();
    final detail = colon > 0 ? stripped.substring(colon + 1).trim() : '';
    if (symptom.isEmpty || symptom.length > _kMaxSymptomLength) continue;
    out.add(EscalationItem(symptom, detail));
  }
  return out;
}
