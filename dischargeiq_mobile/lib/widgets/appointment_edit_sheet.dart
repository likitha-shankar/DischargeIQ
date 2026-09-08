/// widgets/appointment_edit_sheet.dart
///
/// Correct one follow-up appointment: when, who, what for.
///
/// Scoped to the four fields a patient can genuinely know better than the
/// document - most often because the clinic rang and moved the date. The
/// document's own values stay visible beside each field rather than being
/// overwritten in place, so the patient can see what they are changing and
/// what it used to say.
///
/// Returns a map of CHANGED fields only, or null on cancel. Unchanged fields
/// are omitted deliberately: storing every field as an "edit" would mark an
/// appointment as corrected when the patient only fixed a typo in one line.
library;

import 'package:flutter/material.dart';

import 'package:dischargeiq_mobile/section_design.dart';
import 'package:dischargeiq_mobile/services/appointment_edits.dart';
import 'package:dischargeiq_mobile/theme.dart' show kRadiusField;

class AppointmentEditSheet extends StatefulWidget {
  const AppointmentEditSheet({
    super.key,
    required this.appointment,
    this.existing,
  });

  /// The appointment as the DOCUMENT gave it, not as currently displayed.
  /// The sheet shows the document's wording as the reference, so it must not
  /// be handed an already-merged map.
  final Map appointment;

  /// A previous correction, so re-editing starts from what the patient last
  /// entered rather than from values they already rejected.
  final AppointmentEdit? existing;

  @override
  State<AppointmentEditSheet> createState() => _AppointmentEditSheetState();
}

class _AppointmentEditSheetState extends State<AppointmentEditSheet> {
  late final Map<String, TextEditingController> _controllers = {
    for (final field in kEditableAppointmentFields)
      field: TextEditingController(
        text: widget.existing?.changes[field] ?? _documentValue(field),
      ),
  };

  String _documentValue(String field) => '${widget.appointment[field] ?? ''}';

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  /// Only the fields whose value differs from the document's.
  Map<String, String> get _changed {
    final out = <String, String>{};
    for (final field in kEditableAppointmentFields) {
      final typed = _controllers[field]!.text.trim();
      if (typed != _documentValue(field).trim()) out[field] = typed;
    }
    return out;
  }

  static const _labels = {
    'date': 'When',
    'provider': 'Who you are seeing',
    'specialty': 'Department',
    'reason': 'What it is for',
  };

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    final changed = _changed;
    return Padding(
      // Keeps fields above the keyboard.
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
            Text('Update this appointment',
                style: TextStyle(
                    fontSize: 17, fontWeight: FontWeight.w700, color: c.text)),
            const SizedBox(height: 4),
            Text(
              'Change what the clinic told you. Your document keeps its '
              'original wording.',
              style: TextStyle(fontSize: 12.5, height: 1.4, color: c.textMute),
            ),
            const SizedBox(height: 16),
            for (final field in kEditableAppointmentFields) ...[
              TextField(
                controller: _controllers[field],
                textCapitalization: TextCapitalization.sentences,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: _labels[field],
                  border: const OutlineInputBorder(),
                  isDense: true,
                  // The document's value, shown under the field rather than
                  // as a hint - a hint disappears the moment you type, which
                  // is exactly when you want to compare against it.
                  helperText: _documentValue(field).isEmpty
                      ? 'Your document did not say'
                      : 'Document says: ${_documentValue(field)}',
                  helperMaxLines: 2,
                ),
              ),
              const SizedBox(height: 14),
            ],
            if (changed.isNotEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(11),
                decoration: BoxDecoration(
                  color: sdWarnTint,
                  borderRadius: BorderRadius.circular(kRadiusField),
                  border: Border.all(color: sdWarnLine),
                ),
                child: const Text(
                  'This appointment will be marked as changed by you. Your '
                  "document's original wording is kept and you can undo it.",
                  style: TextStyle(
                      fontSize: 11.5, height: 1.35, color: sdWarnInk),
                ),
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
                  // Nothing changed means nothing to save - an enabled button
                  // that records an empty edit would flag the appointment as
                  // corrected when it is not.
                  onPressed: changed.isEmpty
                      ? null
                      : () => Navigator.pop(context, changed),
                  child: const Text('Save'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
