/// The date the recovery timeline is measured from.
///
/// `currentPhaseIndex` anchors on the discharge date and returns null without
/// one - no "you are here", no week position, just the shape of a timeline
/// with the patient nowhere in it. Measured on the corpus, only **35 of 106
/// documents (33%)** carry a discharge date, so the feature worked for a
/// third of real paperwork and silently did nothing for the rest.
///
/// The property these tests hold: the timeline anchors on when the patient
/// LEFT HOSPITAL, never on when they uploaded the document. A summary
/// uploaded two weeks late must place them in week three, not restart their
/// recovery. That is why "today" is never substituted for a missing date -
/// it would be a confident wrong answer where the honest one is "we do not
/// know, tell us".
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dischargeiq_mobile/services/discharge_date.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('where the date comes from', () {
    test('the document supplies it when it has one', () async {
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: '2026-08-22');
      expect(r.source, DischargeDateSource.document);
      expect(r.date, DateTime(2026, 8, 22));
      expect(r.isKnown, isTrue);
    });

    test('an absent date is unknown, NOT today', () async {
      // The tempting fallback is "assume they were discharged today". It
      // would place every patient in week 1 and be wrong for anyone
      // uploading late - a confident wrong answer instead of an honest gap.
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: null);
      expect(r.source, DischargeDateSource.unknown);
      expect(r.date, isNull);
      expect(r.isKnown, isFalse);
    });

    test('an unparseable date is unknown rather than guessed', () async {
      // Agent 1 never normalises dates, so "in 2 weeks" and "TBD" arrive
      // verbatim. Same rule isAppointmentPast follows.
      for (final raw in ['TBD', 'in 2 weeks', 'on discharge', '']) {
        final r = await DischargeDateStore.resolve(
            docId: 'doc1', documentValue: raw);
        expect(r.isKnown, isFalse, reason: 'should not parse "$raw"');
      }
    });

    test("the patient's value wins over the document's", () async {
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: '2026-08-01');
      expect(r.source, DischargeDateSource.patient);
      expect(r.date, DateTime(2026, 8, 20));
    });

    test("the document's value is kept even when overridden", () async {
      // The original must stay recoverable, same rule as every other
      // override in the app.
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: '2026-08-01');
      expect(r.documentValue, '2026-08-01');
      expect(r.correctsTheDocument, isTrue);
    });

    test('filling a blank is not the same as correcting a date', () async {
      // Both are patient-supplied, but only one contradicts the paperwork,
      // and the UI labels them differently.
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: null);
      expect(r.source, DischargeDateSource.patient);
      expect(r.correctsTheDocument, isFalse);
    });
  });

  group('a future discharge date is refused', () {
    test('save returns false and stores nothing', () async {
      // Recovery is measured FORWARD from discharge. A future date yields a
      // negative elapsed time, which currentPhaseIndex discards - so storing
      // it would leave the patient with an override that does nothing and no
      // indication why.
      final now = DateTime(2026, 9, 9);
      final ok = await DischargeDateStore.save(
          'doc1', DateTime(2026, 9, 20), now: now);
      expect(ok, isFalse);
      expect(await DischargeDateStore.loadOverride('doc1'), isNull);
    });

    test('today itself is accepted', () async {
      final now = DateTime(2026, 9, 9, 14, 30);
      final ok = await DischargeDateStore.save('doc1', DateTime(2026, 9, 9),
          now: now);
      expect(ok, isTrue);
    });
  });

  group('undo restores the document', () {
    test('clearing the override falls back to the document value', () async {
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      await DischargeDateStore.clear('doc1');
      final r = await DischargeDateStore.resolve(
          docId: 'doc1', documentValue: '2026-08-01');
      expect(r.source, DischargeDateSource.document);
      expect(r.date, DateTime(2026, 8, 1));
    });

    test('clearing with no document value returns to unknown', () async {
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      await DischargeDateStore.clear('doc1');
      final r =
          await DischargeDateStore.resolve(docId: 'doc1', documentValue: null);
      expect(r.isKnown, isFalse);
    });
  });

  group('the ISO text handed to the timeline parser', () {
    test('is zero-padded so the parser accepts it', () async {
      await DischargeDateStore.save('doc1', DateTime(2026, 1, 5));
      final r =
          await DischargeDateStore.resolve(docId: 'doc1', documentValue: null);
      expect(r.isoText, '2026-01-05');
    });

    test('is empty when the date is unknown', () async {
      final r =
          await DischargeDateStore.resolve(docId: 'doc1', documentValue: null);
      expect(r.isoText, isEmpty);
    });
  });

  group('documents stay isolated', () {
    test('a date set on one document does not apply to another', () async {
      await DischargeDateStore.save('doc1', DateTime(2026, 8, 20));
      expect(await DischargeDateStore.loadOverride('doc2'), isNull);
    });

    test('an unsaved run stores nothing and does not throw', () async {
      expect(await DischargeDateStore.save('', DateTime(2026, 8, 20)), isFalse);
    });
  });
}
