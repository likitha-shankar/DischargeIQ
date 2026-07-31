import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

/// Shown when a results tab has nothing to display because the uploaded
/// discharge document did not contain that information.
///
/// Real discharge paperwork is frequently incomplete. Measured across the
/// 106-document MTSamples corpus: warning signs appear in only 34% of
/// documents, discharge medications in 62%, follow-up in 69%. So an empty tab
/// is not an edge case, it is the common case, and a blank panel reads to a
/// patient as a broken app rather than as a gap in their paperwork.
///
/// The wording is deliberate on three points:
///   1. It says the information was not in THEIR document, so the patient does
///      not conclude the instruction does not exist.
///   2. It never fills the gap with invented clinical content - that is hard
///      rule 1 (null is better than wrong) carried into the UI.
///   3. It routes the patient to their care team, which is the human-in-the-
///      loop framing the whole product rests on.
class EmptySection extends StatelessWidget {
  const EmptySection({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.safetyNote,
  });

  /// Icon for the missing section, matching that tab's hero icon.
  final IconData icon;

  /// Short headline, e.g. "No medications listed".
  final String title;

  /// One or two plain sentences naming what was missing and what to do.
  final String message;

  /// Optional general-safety line. Used only by the warning-signs tab, where
  /// leaving a patient with nothing at all is itself a risk. Rendered visually
  /// distinct and explicitly labelled as general guidance rather than
  /// something extracted from their document.
  final String? safetyNote;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final border = dark ? kBorderDark : kBorderLight;
    final primary = dark ? kTextPrimaryDark : kTextPrimaryLight;
    final secondary = dark ? kTextSecondaryDark : kTextSecondaryLight;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: dark ? kSurfaceDark : kSurfaceLight,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 22, color: kTealMid),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      title,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: primary,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                message,
                style: TextStyle(fontSize: 14, height: 1.6, color: secondary),
              ),
            ],
          ),
        ),
        if (safetyNote != null) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: kTier1Bg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: kTier1.withValues(alpha: 0.35)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.info_outline, size: 18, color: kTier1),
                    SizedBox(width: 8),
                    Text(
                      'General advice, not from your document',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: kTier1,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  safetyNote!,
                  // Fixed dark text: this card keeps its light red background
                  // in both themes so the warning reads identically.
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.6,
                    color: Color(0xFF7F1D1D),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
