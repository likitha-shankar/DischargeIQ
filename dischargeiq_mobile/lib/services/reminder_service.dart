/// services/reminder_service.dart
///
/// Local notification plumbing for medication reminders AND the daily garden
/// nudge. LOCAL ONLY: the schedule lives in the phone's notification system,
/// nothing is sent to or stored on any server. Wraps
/// flutter_local_notifications with the app's safety framing: every
/// medication body carries the verbatim dose text and a follow-your-label
/// reminder, never advice; the garden nudge is invitation-only copy with no
/// guilt or urgency (docs/GAMIFICATION_STRATEGY.md rule 5).
///
/// Notification id map (never overlap - cancels are id-scoped):
///   1        garden daily nudge
///   100-199  medication reminders
library;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'package:dischargeiq_mobile/services/game_store.dart' show CompanionStore;
import 'package:dischargeiq_mobile/services/medication_schedule.dart';

/// SharedPreferences key remembering the patient's garden-nudge opt-in, so
/// the toggle survives restarts and the schedule can be re-asserted on launch.
const String kGardenReminderPrefKey = 'garden_reminder_on';

const int _kGardenNotifId = 1;
const int _kMedIdStart = 100;
const int _kMedIdEnd = 199;

class ReminderService {
  static final _plugin = FlutterLocalNotificationsPlugin();
  static bool _ready = false;

  static Future<void> _init() async {
    if (_ready) return;
    tzdata.initializeTimeZones();
    try {
      final name = await FlutterTimezone.getLocalTimezone();
      tz.setLocalLocation(tz.getLocation(name));
    } catch (_) {
      // Fall back to the plugin default; times still fire, worst case the
      // schedule is created in UTC until next app launch.
    }
    await _plugin.initialize(const InitializationSettings(
      iOS: DarwinInitializationSettings(),
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    ));
    _ready = true;
  }

  /// Ask the OS for notification permission. Returns whether granted.
  static Future<bool> requestPermission() async {
    await _init();
    final ios = _plugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin>();
    if (ios != null) {
      return await ios.requestPermissions(alert: true, badge: true, sound: true) ??
          false;
    }
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android != null) {
      return await android.requestNotificationsPermission() ?? false;
    }
    return false;
  }

  /// Replace the entire MEDICATION reminder schedule with this plan: one
  /// repeating daily notification per medication per confirmed time. Only the
  /// med id block is cleared - cancelAll() here would silently kill the
  /// garden nudge every time the patient re-saved their medication times.
  static Future<void> scheduleAll(List<MedReminder> plan) async {
    await _init();
    for (var i = _kMedIdStart; i <= _kMedIdEnd; i++) {
      await _plugin.cancel(i); // no-op for ids never scheduled
    }
    var id = _kMedIdStart; // deterministic block for med reminders
    for (final med in plan) {
      if (med.asNeeded) continue;
      for (final t in med.times) {
        final now = tz.TZDateTime.now(tz.local);
        var when = tz.TZDateTime(
            tz.local, now.year, now.month, now.day, t.hour, t.minute);
        if (when.isBefore(now)) when = when.add(const Duration(days: 1));
        await _plugin.zonedSchedule(
          id++,
          'Medicine time: ${med.name}',
          '${med.doseText.isNotEmpty ? '${med.doseText} - ' : ''}'
              'as written on your discharge papers. Follow your pharmacy '
              'label if it differs.',
          when,
          const NotificationDetails(
            iOS: DarwinNotificationDetails(),
            android: AndroidNotificationDetails(
              'med_reminders',
              'Medication reminders',
              channelDescription: 'Daily medicine time reminders',
              importance: Importance.high,
              priority: Priority.high,
            ),
          ),
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
          uiLocalNotificationDateInterpretation:
              UILocalNotificationDateInterpretation.absoluteTime,
          matchDateTimeComponents: DateTimeComponents.time, // repeat daily
        );
      }
    }
  }

  /// Turn MEDICATION reminders off - clears only the med id block so the
  /// garden nudge (id 1) keeps its own independent on/off switch.
  static Future<void> cancelMedReminders() async {
    await _init();
    for (var i = _kMedIdStart; i <= _kMedIdEnd; i++) {
      await _plugin.cancel(i);
    }
  }

  // ── Garden daily nudge (gamification: gentle re-entry hook) ──────────────

  /// Whether the patient has the garden nudge switched on.
  static Future<bool> gardenReminderEnabled() async =>
      (await SharedPreferences.getInstance()).getBool(kGardenReminderPrefKey) ??
      false;

  /// Opt in to one gentle daily notification at 10:00 local time. Copy rules
  /// from the strategy doc: invitation, never obligation - no streak talk, no
  /// "you missed", no countdowns. Requests OS permission first; returns false
  /// (and stores nothing) when the patient declines the system prompt.
  static Future<bool> enableGardenReminder() async {
    if (!await requestPermission()) return false;
    final now = tz.TZDateTime.now(tz.local);
    var when = tz.TZDateTime(tz.local, now.year, now.month, now.day, 10);
    if (when.isBefore(now)) when = when.add(const Duration(days: 1));
    // A named companion makes the nudge personal ("Maple found something")
    // instead of institutional ("the app wants you back"). Re-call this
    // method after a rename to refresh the copy - same id, so it replaces.
    final companion = await CompanionStore.name();
    await _plugin.zonedSchedule(
      _kGardenNotifId,
      companion.isEmpty ? 'Your recovery garden' : "$companion's garden",
      companion.isEmpty
          ? 'A minute with your discharge plan helps your garden grow. '
              'Come back whenever suits you.'
          : '$companion found something new in your garden. '
              'Come see whenever suits you.',
      when,
      const NotificationDetails(
        iOS: DarwinNotificationDetails(),
        android: AndroidNotificationDetails(
          'garden_nudge',
          'Recovery garden',
          channelDescription: 'One gentle daily reminder to visit your garden',
          // Low importance on purpose: this is an invitation, not an alert.
          importance: Importance.low,
          priority: Priority.low,
        ),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time, // repeat daily
    );
    await (await SharedPreferences.getInstance())
        .setBool(kGardenReminderPrefKey, true);
    return true;
  }

  /// Opt out - cancels only the garden notification, med reminders untouched.
  static Future<void> disableGardenReminder() async {
    await _init();
    await _plugin.cancel(_kGardenNotifId);
    await (await SharedPreferences.getInstance())
        .setBool(kGardenReminderPrefKey, false);
  }
}
