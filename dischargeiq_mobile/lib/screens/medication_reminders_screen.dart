/// screens/medication_reminders_screen.dart
///
/// Medication reminder setup: shows the SUGGESTED schedule built from the
/// patient's own extracted medications, lets them confirm or edit every
/// time, then schedules local notifications. The patient is always the one
/// who decides - the app only suggests. Doses and frequencies display
/// verbatim from the document; unrecognized frequencies carry a
/// check-your-label note.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/medication_schedule.dart';
import 'package:dischargeiq_mobile/services/reminder_service.dart';
import 'package:flutter/material.dart';

class MedicationRemindersScreen extends StatefulWidget {
  const MedicationRemindersScreen({super.key, required this.extraction});

  final Map<String, dynamic> extraction;

  @override
  State<MedicationRemindersScreen> createState() =>
      _MedicationRemindersScreenState();
}

class _MedicationRemindersScreenState extends State<MedicationRemindersScreen> {
  List<MedReminder> _plan = [];
  bool _enabled = false;
  bool _busy = false;
  // True when reminders from a DIFFERENT document are still scheduled -
  // the banner tells the patient saving here replaces them.
  bool _otherDocActive = false;

  @override
  void initState() {
    super.initState();
    final suggested = buildSuggestedSchedule(widget.extraction);
    final fp = planFingerprint(suggested.map((m) => m.name));
    MedScheduleStore.load(currentFingerprint: fp).then((saved) {
      if (!mounted) return;
      setState(() {
        if (saved.$1.isNotEmpty) {
          _plan = saved.$1;
          _enabled = saved.$2;
        } else {
          _plan = suggested;
          _otherDocActive = saved.$3;
        }
      });
    });
  }

  Future<void> _editTime(MedReminder med, int index) async {
    final t = med.times[index];
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: t.hour, minute: t.minute),
    );
    if (picked != null) {
      setState(() =>
          med.times[index] = ReminderTime(picked.hour, picked.minute));
    }
  }

  Future<void> _enable() async {
    setState(() => _busy = true);
    final granted = await ReminderService.requestPermission();
    if (!granted) {
      if (mounted) {
        setState(() => _busy = false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
              'Notifications are off for DischargeIQ. Allow them in '
              'Settings to get medicine reminders.'),
        ));
      }
      return;
    }
    await ReminderService.scheduleAll(_plan);
    await MedScheduleStore.save(_plan, enabled: true);
    if (mounted) {
      setState(() {
        _enabled = true;
        _busy = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Daily medicine reminders are on.'),
      ));
    }
  }

  Future<void> _disable() async {
    setState(() => _busy = true);
    await ReminderService.cancelMedReminders();
    await MedScheduleStore.save(_plan, enabled: false);
    if (mounted) {
      setState(() {
        _enabled = false;
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final schedulable = _plan.where((m) => !m.asNeeded).toList();
    final prn = _plan.where((m) => m.asNeeded).toList();

    return Scaffold(
      appBar: AppBar(
        backgroundColor: kTeal,
        foregroundColor: Colors.white,
        title: const Text('Medicine reminders'),
      ),
      body: _plan.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: Text(
                  'No medications to remind you about were found in this document.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: dark ? kCardDark : kTealPale,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'These times are suggestions based on your discharge '
                    'papers. Tap any time to change it. Doses are shown '
                    'exactly as written - always follow your pharmacy label '
                    'if it differs.',
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.4,
                      color: dark ? kTextSecondaryDark : kTextPrimaryLight,
                    ),
                  ),
                ),
                if (_otherDocActive) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: kTier2Bg,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text(
                      'Reminders from an earlier document are still on. '
                      'Turning on reminders here replaces them.',
                      style: TextStyle(fontSize: 12.5, color: Color(0xFF92600A)),
                    ),
                  ),
                ],
                const SizedBox(height: 14),
                for (final med in schedulable) _medCard(med, dark),
                if (prn.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    'TAKE ONLY WHEN NEEDED (no daily reminder)',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                      color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                    ),
                  ),
                  const SizedBox(height: 6),
                  for (final med in prn)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Text(
                        '· ${med.name} ${med.doseText} - ${med.frequencyText}',
                        style: TextStyle(
                          fontSize: 13.5,
                          color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                        ),
                      ),
                    ),
                ],
                const SizedBox(height: 16),
                if (!_enabled)
                  FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: kTeal,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: _busy || schedulable.isEmpty ? null : _enable,
                    icon: const Icon(Icons.notifications_active_outlined),
                    label: const Text('Turn on daily reminders'),
                  )
                else ...[
                  FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: kTealMid,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: _busy ? null : _enable,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Save changes to reminders'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _busy ? null : _disable,
                    child: const Text('Turn reminders off'),
                  ),
                ],
                const SizedBox(height: 24),
              ],
            ),
    );
  }

  Widget _medCard(MedReminder med, bool dark) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: dark ? kCardDark : kCardLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: dark ? kBorderDark : kBorderLight, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${med.name}${med.doseText.isNotEmpty ? ' · ${med.doseText}' : ''}',
            style: TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 14.5,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          if (med.frequencyText.isNotEmpty)
            Text(
              'Document says: "${med.frequencyText}"',
              style: TextStyle(
                fontSize: 12,
                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
              ),
            ),
          if (!med.frequencyRecognized)
            const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text(
                'Could not read this frequency - one reminder suggested. '
                'Check your pharmacy label.',
                style: TextStyle(fontSize: 11.5, color: kTier2),
              ),
            ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (var i = 0; i < med.times.length; i++)
                ActionChip(
                  avatar: Icon(Icons.access_time,
                      size: 15, color: dark ? kTealGlow : kTeal),
                  label: Text(med.times[i].label),
                  onPressed: () => _editTime(med, i),
                ),
              if (med.times.length > 1)
                IconButton(
                  tooltip: 'Remove last time',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.remove_circle_outline, size: 20),
                  onPressed: () =>
                      setState(() => med.times.removeLast()),
                ),
              IconButton(
                tooltip: 'Add a time',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.add_circle_outline, size: 20),
                onPressed: () => setState(() =>
                    med.times.add(const ReminderTime(12, 0))),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
