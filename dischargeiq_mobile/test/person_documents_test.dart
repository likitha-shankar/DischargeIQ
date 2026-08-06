/// test/person_documents_test.dart
///
/// Black-box tests for filing documents under people: the PersonStore file
/// layer, DocumentStore.assignPerson, the active-person rules, and the
/// derived states the UI depends on (a person's documents, the Unassigned
/// bucket, orphans left by a deleted person).
///
/// path_provider and shared_preferences are platform channels, so both are
/// mocked - path_provider to a real temp directory so the stores do genuine
/// file I/O. These exercise the store contract the way the screens use it,
/// which is where the bugs actually were.
library;

import 'dart:io';

import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Minimal successful pipeline result - enough for DocumentStore.save().
Map<String, dynamic> _result(String diagnosis) => {
      'pipeline_status': 'complete',
      'extraction': {'primary_diagnosis': diagnosis},
      'diagnosis_explanation': 'Explanation text.',
      'medication_rationale': '',
      'recovery_trajectory': '',
      'escalation_guide': '',
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempRoot;

  setUp(() async {
    tempRoot = await Directory.systemTemp.createTemp('person_docs_test');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (call) async =>
          call.method == 'getApplicationDocumentsDirectory' ? tempRoot.path : null,
    );
    SharedPreferences.setMockInitialValues({});
  });

  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      null,
    );
    if (await tempRoot.exists()) await tempRoot.delete(recursive: true);
  });

  group('container self-heal', () {
    test('a file squatting on the Documents path is repaired, not fatal',
        () async {
      // The exact corruption seen on the device after a bad restore: the
      // backup script had left a FILE where the Documents directory belongs,
      // so every save failed as "could not save" with no diagnosis possible.
      final docsPath = tempRoot.path;
      await tempRoot.delete(recursive: true);
      await File(docsPath).writeAsString('squatter');

      final person =
          await PersonStore.add(name: 'Heal', relationship: Relationship.myself);
      expect(person, isNotNull, reason: 'save must repair the container');
      expect((await PersonStore.list()).single.name, 'Heal');

      final id = await DocumentStore.save(
          result: _result('COPD'), fileName: 'c.pdf');
      expect(id, isNotNull);
    });
  });

  group('people persist', () {
    test('a person round-trips through the file store', () async {
      final added = await PersonStore.add(
        name: 'Priya',
        relationship: Relationship.sibling,
        age: 31,
      );
      expect(added, isNotNull);

      final people = await PersonStore.list();
      expect(people, hasLength(1));
      expect(people.first.name, 'Priya');
      expect(people.first.relationship, Relationship.sibling);
      expect(people.first.age, 31);
    });

    test('a blank name is rejected rather than creating a nameless person',
        () async {
      expect(await PersonStore.add(name: '   ', relationship: Relationship.other),
          isNull);
      expect(await PersonStore.list(), isEmpty);
    });

    test('names are trimmed', () async {
      await PersonStore.add(name: '  Mom  ', relationship: Relationship.parent);
      expect((await PersonStore.list()).first.name, 'Mom');
    });

    test('removing a person leaves the others intact', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      await PersonStore.add(name: 'B', relationship: Relationship.other);
      await PersonStore.remove(a!.id);

      final people = await PersonStore.list();
      expect(people, hasLength(1));
      expect(people.first.name, 'B');
    });
  });

  group('filing documents', () {
    test('a document saves under the person it was filed for', () async {
      final person =
          await PersonStore.add(name: 'Priya', relationship: Relationship.sibling);
      final id = await DocumentStore.save(
        result: _result('Hip replacement'),
        fileName: 'hip.pdf',
        personId: person!.id,
      );
      expect(id, isNotNull);

      final docs = await DocumentStore.list();
      expect(docs.single.personId, person.id);
    });

    test('a document saved with no person is unassigned, not orphaned',
        () async {
      await DocumentStore.save(
        result: _result('COPD'),
        fileName: 'copd.pdf',
      );
      final docs = await DocumentStore.list();
      expect(docs.single.personId, isNull);
      expect(docs.single.diagnosis, 'COPD');
    });

    test('assignPerson files an unassigned document', () async {
      final person =
          await PersonStore.add(name: 'Mom', relationship: Relationship.parent);
      final id = await DocumentStore.save(
          result: _result('Diabetes'), fileName: 'd.pdf');

      expect(await DocumentStore.assignPerson(id!, person!.id), isTrue);
      expect((await DocumentStore.list()).single.personId, person.id);
    });

    test('a document moves between people, never duplicating', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      final id = await DocumentStore.save(
        result: _result('Heart failure'),
        fileName: 'hf.pdf',
        personId: a!.id,
      );

      await DocumentStore.assignPerson(id!, b!.id);

      final docs = await DocumentStore.list();
      // One document, one owner: moving must not leave a copy behind.
      expect(docs, hasLength(1));
      expect(docs.single.personId, b.id);
    });

    test('a document can be sent back to unassigned', () async {
      final person =
          await PersonStore.add(name: 'A', relationship: Relationship.other);
      final id = await DocumentStore.save(
        result: _result('COPD'),
        fileName: 'c.pdf',
        personId: person!.id,
      );

      await DocumentStore.assignPerson(id!, null);
      expect((await DocumentStore.list()).single.personId, isNull);
    });

    test('refiling preserves the stored analysis', () async {
      final person =
          await PersonStore.add(name: 'A', relationship: Relationship.other);
      final id = await DocumentStore.save(
        result: _result('Heart failure'),
        fileName: 'hf.pdf',
      );
      await DocumentStore.assignPerson(id!, person!.id);

      final loaded = await DocumentStore.load(id);
      expect(loaded, isNotNull);
      final (result, _) = loaded!;
      expect(result['extraction']['primary_diagnosis'], 'Heart failure');
      expect(result['diagnosis_explanation'], 'Explanation text.');
    });

    test('assignPerson on an unknown id fails rather than throwing', () async {
      expect(await DocumentStore.assignPerson('does-not-exist', 'x'), isFalse);
    });

    test('rapid saves never overwrite each other', () async {
      // The id was the millisecond timestamp alone. Two saves inside the same
      // millisecond produced the same id and the second silently overwrote
      // the first, losing a saved discharge summary. Measured before the fix:
      // eight saves, six documents.
      final ids = <String?>[];
      for (var i = 0; i < 8; i++) {
        ids.add(await DocumentStore.save(
          result: _result('Dx$i'),
          fileName: 'f$i.pdf',
        ));
      }
      expect(ids.whereType<String>().toSet(), hasLength(8));
      expect(await DocumentStore.list(), hasLength(8));
    });
  });

  group('deleting a person', () {
    test('their documents survive and become unassigned to the UI', () async {
      final person =
          await PersonStore.add(name: 'Gone', relationship: Relationship.other);
      await DocumentStore.save(
        result: _result('COPD'),
        fileName: 'c.pdf',
        personId: person!.id,
      );

      await PersonStore.remove(person.id);

      // The document is NOT deleted - losing a discharge summary as a side
      // effect of tidying a name would be indefensible.
      final docs = await DocumentStore.list();
      expect(docs, hasLength(1));

      // Its person_id now points at nobody. This is the exact rule the people
      // screen uses to build the Unassigned bucket.
      final ids = (await PersonStore.list()).map((p) => p.id).toSet();
      final unassigned = docs
          .where((d) => d.personId == null || !ids.contains(d.personId))
          .toList();
      expect(unassigned, hasLength(1));
    });
  });

  group('active person', () {
    test('is null before anyone exists', () async {
      expect(await PersonStore.active(), isNull);
    });

    test('stays All even when one person exists', () async {
      // No "fall back to the first person" rule: that would silently file one
      // person's summary under another the moment a second profile appeared.
      await PersonStore.add(name: 'Solo', relationship: Relationship.myself);
      expect(await PersonStore.active(), isNull);
    });

    test('an explicit choice wins over the fallback', () async {
      await PersonStore.add(name: 'First', relationship: Relationship.myself);
      final second =
          await PersonStore.add(name: 'Second', relationship: Relationship.parent);

      await PersonStore.setActive(second!.id);
      expect((await PersonStore.active())!.name, 'Second');
    });

    test('a deleted active person does not keep collecting documents', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      await PersonStore.setActive(a!.id);
      await PersonStore.remove(a.id);

      // The stale id must not resolve; without the guard, uploads would file
      // under a person who no longer exists and vanish from every folder.
      expect(await PersonStore.activeId(), isNull);
      // Falls back to All, not to another person.
      expect(await PersonStore.active(), isNull);
      expect((await PersonStore.list()).single.id, b!.id);
    });

    test('clearing the active person is honoured', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      await PersonStore.setActive(a!.id);
      await PersonStore.setActive(null);
      expect(await PersonStore.activeId(), isNull);
    });
  });

  group('deleting a profile keeps its documents', () {
    test('documents are unfiled, not destroyed', () async {
      final person =
          await PersonStore.add(name: 'Mom', relationship: Relationship.parent);
      final keep = await DocumentStore.save(
        result: _result('COPD'),
        fileName: 'c.pdf',
        personId: person!.id,
      );

      // The screen unfiles first, then removes the person.
      for (final d in (await DocumentStore.list())
          .where((d) => d.personId == person.id)) {
        await DocumentStore.assignPerson(d.id, null);
      }
      await PersonStore.remove(person.id);

      final docs = await DocumentStore.list();
      expect(docs, hasLength(1), reason: 'the summary must survive');
      expect(docs.single.personId, isNull, reason: 'and land in Unassigned');

      // Still openable: deleting a profile must not damage the analysis.
      final loaded = await DocumentStore.load(keep!);
      expect(loaded, isNotNull);
      final (reopened, _) = loaded!;
      expect(reopened['extraction']['primary_diagnosis'], 'COPD');
    });

    test('choosing to delete the documents removes them entirely', () async {
      final person =
          await PersonStore.add(name: 'Mom', relationship: Relationship.parent);
      final id = await DocumentStore.save(
        result: _result('COPD'),
        fileName: 'c.pdf',
        personId: person!.id,
      );

      // The delete-documents branch: remove each document, then the person.
      for (final d in (await DocumentStore.list())
          .where((d) => d.personId == person.id)) {
        await DocumentStore.delete(d.id);
      }
      await PersonStore.remove(person.id);

      expect(await DocumentStore.list(), isEmpty);
      expect(await DocumentStore.load(id!), isNull);
      expect(await PersonStore.list(), isEmpty);
    });

    test('deleting one profile with its documents spares everyone else',
        () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);
      await DocumentStore.save(
          result: _result('Two'), fileName: '2.pdf', personId: b!.id);
      await DocumentStore.save(result: _result('Loose'), fileName: '3.pdf');

      for (final d in (await DocumentStore.list())
          .where((d) => d.personId == a.id)) {
        await DocumentStore.delete(d.id);
      }
      await PersonStore.remove(a.id);

      final docs = await DocumentStore.list();
      expect(docs, hasLength(2), reason: 'only A\'s document is destroyed');
      expect(docs.where((d) => d.personId == b.id), hasLength(1));
      expect(docs.where((d) => d.personId == null), hasLength(1));
    });

    test('other people keep their documents', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);
      await DocumentStore.save(
          result: _result('Two'), fileName: '2.pdf', personId: b!.id);

      for (final d in (await DocumentStore.list())
          .where((d) => d.personId == a.id)) {
        await DocumentStore.assignPerson(d.id, null);
      }
      await PersonStore.remove(a.id);

      final docs = await DocumentStore.list();
      expect(docs.where((d) => d.personId == b.id), hasLength(1));
      expect(docs.where((d) => d.personId == null), hasLength(1));
    });
  });

  group('profile filtering', () {
    test('a named profile shows only its own documents', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);
      await DocumentStore.save(
          result: _result('Two'), fileName: '2.pdf', personId: b!.id);
      await DocumentStore.save(result: _result('Three'), fileName: '3.pdf');

      final all = await DocumentStore.list();
      // The exact filter the home list applies.
      final forA = DocumentStore.forPerson(all, a.id);
      expect(forA, hasLength(1));
      expect(forA.single.diagnosis, 'One');
    });

    test('a profile with no analysis of its own gets no journey documents',
        () async {
      // The bug: the recovery journey listed documents its own way instead of
      // scoping to the active profile, so a brand-new profile opened showing
      // the other profile's newest document and its stars.
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);
      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);

      final all = await DocumentStore.list();
      expect(DocumentStore.forPerson(all, b!.id), isEmpty);
      // An unassigned document must not leak into a named profile either.
      await DocumentStore.save(result: _result('Loose'), fileName: 'x.pdf');
      expect(
        DocumentStore.forPerson(await DocumentStore.list(), b.id),
        isEmpty,
      );
    });

    test('the journey picker lists every document for one profile', () async {
      // Drives the dropdown: several analyses for the same person all stay
      // selectable, so the patient chooses which recovery journey to view.
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      for (final name in ['One', 'Two', 'Three']) {
        await DocumentStore.save(
            result: _result(name), fileName: '$name.pdf', personId: a!.id);
      }
      final forA = DocumentStore.forPerson(await DocumentStore.list(), a!.id);
      expect(forA, hasLength(3));
      // Newest first, so the journey defaults to the document being lived with.
      expect(forA.first.diagnosis, 'Three');
    });

    test('All shows every document including unassigned ones', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);
      await DocumentStore.save(result: _result('Two'), fileName: '2.pdf');

      // Active null means no filter at all.
      expect(await PersonStore.active(), isNull);
      expect(await DocumentStore.list(), hasLength(2));
    });
  });

  group('grouping the library', () {
    test('documents split correctly across people and unassigned', () async {
      final a = await PersonStore.add(name: 'A', relationship: Relationship.other);
      final b = await PersonStore.add(name: 'B', relationship: Relationship.other);

      await DocumentStore.save(
          result: _result('One'), fileName: '1.pdf', personId: a!.id);
      await DocumentStore.save(
          result: _result('Two'), fileName: '2.pdf', personId: a.id);
      await DocumentStore.save(
          result: _result('Three'), fileName: '3.pdf', personId: b!.id);
      await DocumentStore.save(result: _result('Four'), fileName: '4.pdf');

      final docs = await DocumentStore.list();
      final ids = (await PersonStore.list()).map((p) => p.id).toSet();

      expect(docs.where((d) => d.personId == a.id), hasLength(2));
      expect(docs.where((d) => d.personId == b.id), hasLength(1));
      expect(
        docs.where((d) => d.personId == null || !ids.contains(d.personId)),
        hasLength(1),
      );
    });

    test('a corrupt people file degrades to empty rather than crashing',
        () async {
      await File('${tempRoot.path}/people.json').writeAsString('{not json');
      expect(await PersonStore.list(), isEmpty);
      expect(await PersonStore.active(), isNull);
    });
  });
}
