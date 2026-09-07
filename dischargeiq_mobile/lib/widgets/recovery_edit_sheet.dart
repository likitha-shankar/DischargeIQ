/// widgets/recovery_edit_sheet.dart
///
/// The sheet for overriding one line of the recovery timeline.
///
/// Two routes to the same field, kept apart on purpose:
///
///   "Just for me"      - the patient rewrites the line in their own words.
///                        Recorded as their change and labelled as such.
///   "My care team told
///    me to change this" - a correction, which must name who said so.
///
/// The distinction is the point. A patient paraphrasing an instruction and a
/// nurse correcting a wrong dose look identical once they are text on a
/// screen, and only one of them should carry any authority. Making the author
/// a required field for the second is what keeps an unattributed edit from
/// later being read as clinical.
///
/// What this sheet deliberately does NOT do: send anything anywhere. Nothing
/// here is authenticated, so the wording avoids any suggestion that the care
/// team has seen, approved, or received the change.
library;

import 'package:flutter/material.dart';

import 'package:dischargeiq_mobile/section_design.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusField;
import 'package:dischargeiq_mobile/services/recovery_notes.dart';

class RecoveryEditSheet extends StatefulWidget {
  const RecoveryEditSheet({
    super.key,
    required this.phase,
    required this.bulletIndex,
    required this.original,
    this.existing,
  });

  final String phase;
  final int bulletIndex;

  /// The document's own wording. Always shown, never editable - it is the
  /// reference the change is measured against.
  final String original;

  /// A previous override on this line, so re-editing starts from it rather
  /// than from the document text the patient already rejected.
  final RecoveryEdit? existing;

  @override
  State<RecoveryEditSheet> createState() => _RecoveryEditSheetState();
}

class _RecoveryEditSheetState extends State<RecoveryEditSheet> {
  late final TextEditingController _text =
      TextEditingController(text: widget.existing?.text ?? widget.original);
  late final TextEditingController _author =
      TextEditingController(text: widget.existing?.author ?? '');

  late bool _clinical =
      widget.existing?.kind == RecoveryEditKind.correction;

  @override
  void dispose() {
    _text.dispose();
    _author.dispose();
    super.dispose();
  }

  /// Save is blocked until the change is attributable: text that actually
  /// differs, plus a name whenever this claims to come from a clinician.
  bool get _canSave {
    final body = _text.text.trim();
    if (body.isEmpty || body == widget.original.trim()) return false;
    if (_clinical && _author.text.trim().isEmpty) return false;
    return true;
  }

  void _save() {
    Navigator.pop(
      context,
      RecoveryEdit(
        kind: _clinical
            ? RecoveryEditKind.correction
            : RecoveryEditKind.patientEdit,
        phase: widget.phase,
        text: _text.text.trim(),
        bulletIndex: widget.bulletIndex,
        original: widget.original,
        author: _clinical ? _author.text.trim() : null,
        createdAt: DateTime.now(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    return Padding(
      // Keeps the fields above the keyboard, which otherwise covers the
      // author field - the one that gates saving.
      padding: EdgeInsets.only(
        left: 18,
        right: 18,
        top: 18,
        bottom: MediaQuery.of(context).viewInsets.bottom + 18,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Change this instruction',
                style: TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w700, color: c.text)),
            const SizedBox(height: 12),
            // The document's wording, verbatim and visibly locked.
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(11),
              decoration: BoxDecoration(
                color: c.lineSoft,
                borderRadius: BorderRadius.circular(kRadiusField),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('YOUR DOCUMENT SAYS',
                      style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.8,
                          color: c.textMute)),
                  const SizedBox(height: 5),
                  Text(widget.original,
                      style: TextStyle(
                          fontSize: 13, height: 1.45, color: c.text)),
                ],
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _text,
              autofocus: true,
              maxLines: 4,
              minLines: 2,
              textCapitalization: TextCapitalization.sentences,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'What it should say',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 6),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _clinical,
              onChanged: (v) => setState(() => _clinical = v),
              title: Text('My care team told me to change this',
                  style: TextStyle(fontSize: 13.5, color: c.text)),
              subtitle: Text(
                _clinical
                    ? 'Write who told you, so you can show them later.'
                    : 'Otherwise this is saved as your own change.',
                style: TextStyle(fontSize: 11.5, color: c.textMute),
              ),
            ),
            if (_clinical) ...[
              const SizedBox(height: 4),
              TextField(
                controller: _author,
                textCapitalization: TextCapitalization.words,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: 'Who told you (name and role)',
                  hintText: 'e.g. Nurse J. Patel',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              // Says plainly what this is not. Without it, "corrected by
              // Nurse Patel" on a screen could be mistaken for something the
              // hospital sent or approved.
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: sdWarnTint,
                  borderRadius: BorderRadius.circular(kRadiusField),
                  border: Border.all(color: sdWarnLine),
                ),
                child: const Text(
                  'This is your own record of what you were told. It is kept '
                  'on this phone only and is not sent to your care team.',
                  style: TextStyle(
                      fontSize: 11.5, height: 1.35, color: sdWarnInk),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Text(
              'Your document\'s original wording is always kept, and this '
              'line will be marked as changed.',
              style: TextStyle(fontSize: 11.5, height: 1.35, color: c.textMute),
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _canSave ? _save : null,
                  child: const Text('Save change'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
