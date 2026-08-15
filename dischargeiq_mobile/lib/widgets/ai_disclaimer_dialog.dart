/// widgets/ai_disclaimer_dialog.dart
///
/// The usage disclaimer a patient must acknowledge before reading an
/// analysis. Shown once per document, on the results screen, after the
/// guided tour has closed.
///
/// It is a BLOCKING dialog by design: tapping outside does nothing and there
/// is no back-button escape. Every other HITL notice in the app is passive
/// text beside the content it qualifies, which is easy to scroll past. This
/// one is the single point where the patient is told, and has to confirm,
/// that a language model wrote what follows and their care team decides.
///
/// It records acknowledgement per document id rather than per install, so a
/// second discharge - a different hospital stay, possibly a different family
/// member - is acknowledged on its own terms.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusCard;

/// SharedPreferences key holding the acknowledgement for one document.
String _ackKey(String docId) => 'ai_disclaimer_ack_$docId';

/// Whether this document's disclaimer has already been acknowledged.
Future<bool> wasDisclaimerAcknowledged(String docId) async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getBool(_ackKey(docId)) ?? false;
}

/// Show the disclaimer and wait for the patient to acknowledge it.
///
/// Args:
///   context: A context under the results screen's Navigator.
///   docId:   Document being opened. The acknowledgement is stored against
///            it; pass null for an unsaved run, which shows the dialog
///            without remembering the answer.
///
/// Returns when the dialog is dismissed, by either the X or the OK button.
Future<void> showAiDisclaimer(BuildContext context, {String? docId}) async {
  await showDialog<void>(
    context: context,
    // Blocking: no tap-outside dismissal, and no back-button escape either.
    // Acknowledgement has to be a deliberate act or it is not one.
    barrierDismissible: false,
    builder: (ctx) => const PopScope(
      canPop: false,
      child: _AiDisclaimerDialog(),
    ),
  );
  if (docId == null) return;
  final prefs = await SharedPreferences.getInstance();
  await prefs.setBool(_ackKey(docId), true);
}

class _AiDisclaimerDialog extends StatelessWidget {
  const _AiDisclaimerDialog();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final bodyColor = dark ? kTextPrimaryDark : kTextPrimaryLight;

    return AlertDialog(
      backgroundColor: dark ? kCardDark : kCardLight,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusCard),
      ),
      titlePadding: const EdgeInsets.fromLTRB(20, 14, 8, 0),
      title: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              'Before you start',
              style: TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w700,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
          ),
          // The X closes the dialog exactly as the button does. It exists
          // because a dialog with no visible way out reads as a trap.
          IconButton(
            tooltip: 'Close',
            visualDensity: VisualDensity.compact,
            onPressed: () => Navigator.pop(context),
            icon: Icon(Icons.close,
                size: 21, color: dark ? kTextSecondaryDark : kTextSecondaryLight),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Point(
              icon: Icons.auto_awesome_outlined,
              text: 'Everything in this app was written by AI from the '
                  'document you uploaded. It can miss things, and it can be '
                  'wrong.',
              color: bodyColor,
              dark: dark,
            ),
            _Point(
              icon: Icons.medical_information_outlined,
              text: 'This is not medical advice and not a diagnosis. It '
                  'explains your paperwork in plainer words. Your care team '
                  'decides what you should do.',
              color: bodyColor,
              dark: dark,
            ),
            _Point(
              icon: Icons.medication_outlined,
              text: 'Never start, stop or change a medicine because of '
                  'something you read here.',
              color: bodyColor,
              dark: dark,
            ),
            _Point(
              icon: Icons.emergency_outlined,
              text: 'In an emergency, call 911. Do not wait to check the app.',
              color: bodyColor,
              dark: dark,
            ),
            _Point(
              icon: Icons.lock_outline,
              text: 'Your document stays on this phone. Nothing is shared '
                  'with anyone.',
              color: bodyColor,
              dark: dark,
            ),
          ],
        ),
      ),
      actionsPadding: const EdgeInsets.fromLTRB(20, 4, 20, 16),
      actions: [
        SizedBox(
          width: double.infinity,
          height: 46,
          child: FilledButton(
            style: FilledButton.styleFrom(backgroundColor: kTeal),
            onPressed: () => Navigator.pop(context),
            child: const Text(
              'OK, I understand',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
          ),
        ),
      ],
    );
  }
}

/// One line of the disclaimer: an icon and a sentence a tired patient can
/// read in one pass.
class _Point extends StatelessWidget {
  const _Point({
    required this.icon,
    required this.text,
    required this.color,
    required this.dark,
  });

  final IconData icon;
  final String text;
  final Color color;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 13),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: dark ? kTealGlow : kTeal),
          const SizedBox(width: 11),
          Expanded(
            child: Text(
              text,
              style: TextStyle(fontSize: 13.5, height: 1.5, color: color),
            ),
          ),
        ],
      ),
    );
  }
}
