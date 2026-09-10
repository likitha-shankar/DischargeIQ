/// Appointments the patient adds themselves.
///
/// Only 90% of corpus documents name any follow-up, and a discharge summary is
/// written before the clinic rings back with a date. So the appointment a
/// patient is actually attending was invisible to the app - it could correct
/// one and tick one off, but not know about one the paperwork missed.
///
/// Two properties carry the risk, and both are tested harder than the CRUD:
///
///   provenance - an added appointment must never be mistakable for something
///   the hospital wrote. That distinction is what the whole app rests on.
///
///   key stability - an added appointment is edited by the person who made
///   it, so a content-derived key would move on the first correction and
///   silently detach the done-tick. That failure is invisible: the tick just
///   stops being there.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/added_appointments.dart';
import 'package:dischargeiq_mobile/services/appointment_status.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<Map<String, dynamic>> addOne({
    String doc = 'doc-1',
    String provider = 'Dr. Chen',
    String specialty = 'Cardiology',
    String date = '2026-04-20',
  }) async {
    final list = await AddedAppointmentsStore.add(
        docId: doc, provider: provider, specialty: specialty, date: date);
    return list.last;
  }

  group('adding', () {
    test('an added appointment comes back on load', () async {
      await addOne();
      final list = await AddedAppointmentsStore.load('doc-1');
      expect(list.length, 1);
      expect(list.single['provider'], 'Dr. Chen');
      expect(list.single['date'], '2026-04-20');
    });

    test('documents do not see each other\'s additions', () async {
      await addOne(doc: 'doc-1');
      expect(await AddedAppointmentsStore.load('doc-2'), isEmpty);
    });

    test('an entry with nothing identifying is refused', () async {
      // Neither provider nor specialty: the card would render as a blank row
      // that cannot be told apart from any other or meaningfully edited.
      final list = await AddedAppointmentsStore.add(
          docId: 'doc-1', provider: '  ', specialty: '', date: '2026-04-20');
      expect(list, isEmpty);
    });

    test('a specialty alone is enough', () async {
      final list = await AddedAppointmentsStore.add(
          docId: 'doc-1', specialty: 'Physiotherapy');
      expect(list.length, 1);
    });

    test('the date is stored exactly as typed', () async {
      // "in 2 weeks" is a real answer, and Agent 1 is forbidden from
      // resolving relative dates. Normalising here would make the patient's
      // own entry behave differently from every extracted one.
      final entry = await addOne(date: 'in 2 weeks');
      expect(entry['date'], 'in 2 weeks');
    });
  });

  group('provenance', () {
    test('an added appointment is marked as patient-added', () async {
      expect(isPatientAdded(await addOne()), isTrue);
    });

    test('an extracted appointment is not', () async {
      expect(isPatientAdded({'provider': 'Dr. Chen', 'date': '2026-04-05'}),
          isFalse);
    });

    test('the marker is re-asserted on read', () async {
      // An entry that lost its marker in storage would render as though the
      // hospital wrote it, which is the one outcome this must prevent.
      final entry = await addOne();
      SharedPreferences.setMockInitialValues({
        'added_appointments_doc-1':
            '[{"provider":"Dr. Chen","_added_id":"${entry['_added_id']}"}]'
      });
      final list = await AddedAppointmentsStore.load('doc-1');
      expect(isPatientAdded(list.single), isTrue);
    });
  });

  group('key stability', () {
    test('an added appointment keys off its id, not its content', () async {
      final entry = await addOne();
      expect(appointmentKey(entry), 'added:${entry['_added_id']}');
    });

    test('editing the date does NOT move the key', () async {
      // The failure this prevents is silent: the tick simply stops being
      // there, on the appointment the patient just corrected.
      final entry = await addOne();
      final before = appointmentKey(entry);
      final updated = await AddedAppointmentsStore.update(
          docId: 'doc-1', addedId: '${entry['_added_id']}', date: '2026-05-02');
      expect(appointmentKey(updated.single), before);
      expect(updated.single['date'], '2026-05-02');
    });

    test('two additions made in the same run get different keys', () async {
      final a = await addOne(provider: 'Dr. Chen');
      final b = await addOne(provider: 'Dr. Chen');
      expect(appointmentKey(a), isNot(appointmentKey(b)));
    });

    test('extracted appointments keep their content key', () async {
      // The existing rule must be untouched, or every stored tick and
      // correction on a real document detaches at once.
      expect(appointmentKey({'provider': 'Dr. Chen', 'specialty': 'Cardiology',
                             'date': '2026-04-05'}),
             'dr. chen|cardiology|2026-04-05');
    });
  });

  group('editing and removing', () {
    test('update changes only the named fields', () async {
      final entry = await addOne(specialty: 'Cardiology', date: '2026-04-20');
      final updated = await AddedAppointmentsStore.update(
          docId: 'doc-1', addedId: '${entry['_added_id']}', date: '2026-05-02');
      expect(updated.single['specialty'], 'Cardiology');
      expect(updated.single['date'], '2026-05-02');
    });

    test('remove takes out only the named one', () async {
      final a = await addOne(provider: 'Dr. Chen');
      await addOne(provider: 'Dr. Patel');
      final left = await AddedAppointmentsStore.remove(
          'doc-1', '${a['_added_id']}');
      expect(left.length, 1);
      expect(left.single['provider'], 'Dr. Patel');
    });

    test('removing something that is not there is harmless', () async {
      await addOne();
      expect((await AddedAppointmentsStore.remove('doc-1', 'nope')).length, 1);
    });
  });

  group('degrades rather than breaks', () {
    test('a corrupt store reads as empty', () async {
      SharedPreferences.setMockInitialValues(
          {'added_appointments_doc-1': 'not json at all'});
      expect(await AddedAppointmentsStore.load('doc-1'), isEmpty);
    });

    test('a store holding the wrong shape reads as empty', () async {
      SharedPreferences.setMockInitialValues(
          {'added_appointments_doc-1': '{"not":"a list"}'});
      expect(await AddedAppointmentsStore.load('doc-1'), isEmpty);
    });

    test('clear empties it', () async {
      await addOne();
      await AddedAppointmentsStore.clear('doc-1');
      expect(await AddedAppointmentsStore.load('doc-1'), isEmpty);
    });
  });
}
