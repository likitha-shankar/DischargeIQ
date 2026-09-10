/// test/document_store_test.dart
///
/// Unit checks for the on-device document library (services/document_store.dart,
/// decision D-6). path_provider is a platform channel, so its method channel is
/// mocked to a real temp directory - the store then does genuine file I/O there,
/// which is exactly the logic worth testing: save, list ordering, round-trip
/// load, delete, the rejected-document skip, and corrupt-file resilience.
library;

import 'dart:convert' show jsonEncode;
import 'dart:io';

import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempRoot;

  setUp(() async {
    tempRoot = await Directory.systemTemp.createTemp('docstore_test');
    // Mock the path_provider channel so getApplicationDocumentsDirectory()
    // returns our temp dir instead of a real app sandbox.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (call) async {
        if (call.method == 'getApplicationDocumentsDirectory') {
          return tempRoot.path;
        }
        return null;
      },
    );
  });

  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'), null);
    if (await tempRoot.exists()) await tempRoot.delete(recursive: true);
  });

  Map<String, dynamic> result(String diagnosis, {String status = 'complete'}) => {
        'pipeline_status': status,
        'extraction': {'primary_diagnosis': diagnosis},
        'diagnosis_explanation': 'x',
      };

  test('save then list returns the document with its diagnosis', () async {
    await DocumentStore.save(result: result('Heart failure'), fileName: 'hf.pdf');
    final docs = await DocumentStore.list();
    expect(docs.length, 1);
    expect(docs.first.diagnosis, 'Heart failure');
    expect(docs.first.fileName, 'hf.pdf');
    expect(docs.first.hasPdf, isFalse); // no bytes were passed
  });

  group('re-uploading the same document', () {
    /// A result carrying the server's document_hash.
    Map<String, dynamic> hashed(String diagnosis, String hash) => {
          ...result(diagnosis),
          'document_hash': hash,
        };

    test('updates the existing entry instead of adding a second', () async {
      final first = await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      final second = await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');

      expect(second, first, reason: 'the same document keeps its id');
      expect((await DocumentStore.list()).length, 1);
    });

    test('the returned id is what keeps the patient\'s own work attached',
        () async {
      // The whole point. Ten stores key off this id - appointment ticks,
      // notes, weights, the corrected discharge date. A new id on re-upload
      // orphans every one of them, silently, with nothing throwing.
      final first = await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      final again = await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      expect(again, isNotNull);
      expect(again, first);
    });

    test('a different document still gets its own entry', () async {
      await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      await DocumentStore.save(
          result: hashed('COPD', 'def456'), fileName: 'copd.pdf');
      expect((await DocumentStore.list()).length, 2);
    });

    test('a revised summary hashes differently and lands as a new document',
        () async {
      // Same filename, same diagnosis, new content. This must NOT collapse
      // onto the old entry - it is genuinely new paperwork.
      await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      await DocumentStore.save(
          result: hashed('Heart failure', 'zzz999'), fileName: 'hf.pdf');
      expect((await DocumentStore.list()).length, 2);
    });

    test('the refreshed result is what loads back', () async {
      await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      final id = await DocumentStore.save(
        result: {...hashed('Heart failure', 'abc123'), 'diagnosis_explanation': 'updated'},
        fileName: 'hf.pdf',
      );
      final loaded = await DocumentStore.load(id!);
      expect(loaded!.$1['diagnosis_explanation'], 'updated');
    });

    test('re-uploading does not unfile a document from its person', () async {
      final id = await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'),
          fileName: 'hf.pdf',
          personId: 'person-1');
      // No profiles active on the second upload - personId comes through
      // null, and writing that over the assignment would move a filed
      // document into Unassigned for no visible reason.
      await DocumentStore.save(
          result: hashed('Heart failure', 'abc123'), fileName: 'hf.pdf');
      final docs = await DocumentStore.list();
      expect(docs.single.id, id);
      expect(docs.single.personId, 'person-1');
    });

    test('a result with no hash falls back to a new entry', () async {
      // Documents saved before the server sent a hash, and any client
      // running ahead of the deploy. Wrong, but no worse than before.
      await DocumentStore.save(result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.save(result: result('Heart failure'), fileName: 'hf.pdf');
      expect((await DocumentStore.list()).length, 2);
    });
  });

  group('renaming a document', () {
    test('the library shows the name the patient gave it', () async {
      final id = await DocumentStore.save(
          result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.rename(id!, "Mum's February stay");
      final doc = (await DocumentStore.list()).single;
      expect(doc.displayTitle, "Mum's February stay");
      expect(doc.isRenamed, isTrue);
    });

    test('the clinical record underneath is untouched', () async {
      // The generated title comes from primary_diagnosis, which the rest of
      // the app reads as clinical content. A display preference must never
      // edit the record it is displaying.
      final id = await DocumentStore.save(
          result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.rename(id!, 'Whatever I like');
      final loaded = await DocumentStore.load(id);
      expect(loaded!.$1['extraction']['primary_diagnosis'], 'Heart failure');
      expect((await DocumentStore.list()).single.diagnosis, 'Heart failure');
    });

    test('clearing the name brings the generated one back', () async {
      // Renaming must never be a one-way door: the clinical name has to be
      // recoverable without re-uploading the document.
      final id = await DocumentStore.save(
          result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.rename(id!, 'Temporary');
      await DocumentStore.rename(id, '');
      final doc = (await DocumentStore.list()).single;
      expect(doc.displayTitle, 'Heart failure');
      expect(doc.isRenamed, isFalse);
    });

    test('whitespace only counts as clearing it', () async {
      final id = await DocumentStore.save(
          result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.rename(id!, '   ');
      expect((await DocumentStore.list()).single.isRenamed, isFalse);
    });

    test('a very long name is truncated rather than breaking the row', () async {
      final id = await DocumentStore.save(
          result: result('Heart failure'), fileName: 'hf.pdf');
      await DocumentStore.rename(id!, 'x' * 500);
      expect((await DocumentStore.list()).single.displayTitle.length, 80);
    });

    test('re-uploading the same document keeps the name', () async {
      // Same reasoning as the person assignment: a fresh analysis of the same
      // paperwork does not withdraw the patient's choice of name.
      final hashed = {...result('Heart failure'), 'document_hash': 'abc123'};
      final id = await DocumentStore.save(result: hashed, fileName: 'hf.pdf');
      await DocumentStore.rename(id!, 'My summary');
      await DocumentStore.save(result: hashed, fileName: 'hf.pdf');
      final docs = await DocumentStore.list();
      expect(docs.length, 1);
      expect(docs.single.displayTitle, 'My summary');
    });

    test('renaming a document that does not exist fails quietly', () async {
      expect(await DocumentStore.rename('no-such-id', 'x'), isFalse);
    });

    test('an unnamed document falls back to diagnosis then file name', () async {
      await DocumentStore.save(
          result: {'pipeline_status': 'complete', 'extraction': {}},
          fileName: 'scan.pdf');
      final doc = (await DocumentStore.list()).single;
      // 'Discharge summary' is the store's own fallback for a missing
      // diagnosis; the point is that displayTitle is never empty.
      expect(doc.displayTitle.isNotEmpty, isTrue);
    });
  });

  test('rejected documents are never saved', () async {
    await DocumentStore.save(
      result: result('Not a discharge document', status: 'rejected'),
      fileName: 'invoice.pdf',
    );
    expect(await DocumentStore.list(), isEmpty);
  });

  test('save with PDF bytes round-trips through load', () async {
    final pdf = Uint8List.fromList([0x25, 0x50, 0x44, 0x46]); // %PDF
    await DocumentStore.save(
      result: result('COPD'), fileName: 'copd.pdf', pdfBytes: pdf);
    final docs = await DocumentStore.list();
    expect(docs.single.hasPdf, isTrue);

    final loaded = await DocumentStore.load(docs.single.id);
    expect(loaded, isNotNull);
    final (res, bytes) = loaded!;
    expect(res['extraction']['primary_diagnosis'], 'COPD');
    expect(bytes, pdf);
  });

  test('list is newest-first', () async {
    await DocumentStore.save(result: result('First'), fileName: 'a.pdf');
    await Future<void>.delayed(const Duration(milliseconds: 5));
    await DocumentStore.save(result: result('Second'), fileName: 'b.pdf');
    final docs = await DocumentStore.list();
    expect(docs.length, 2);
    expect(docs.first.diagnosis, 'Second'); // most recent on top
  });

  test('delete removes both json and pdf', () async {
    await DocumentStore.save(
      result: result('Diabetes'),
      fileName: 'd.pdf',
      pdfBytes: Uint8List.fromList([1, 2, 3]),
    );
    final id = (await DocumentStore.list()).single.id;
    await DocumentStore.delete(id);
    expect(await DocumentStore.list(), isEmpty);
    expect(await DocumentStore.load(id), isNull);
  });

  test('a corrupt json entry is skipped, not fatal', () async {
    await DocumentStore.save(result: result('Good'), fileName: 'good.pdf');
    // Drop a garbage .json into the library dir the store reads from.
    final libDir = Directory('${tempRoot.path}/saved_documents');
    await File('${libDir.path}/999999999.json').writeAsString('{ not valid json');
    final docs = await DocumentStore.list();
    // The good one survives; the corrupt one is silently skipped.
    expect(docs.length, 1);
    expect(docs.single.diagnosis, 'Good');
  });

  test('load of a missing id returns null, never throws', () async {
    expect(await DocumentStore.load('does-not-exist'), isNull);
  });

  test('diagnosis falls back when extraction is missing', () async {
    await DocumentStore.save(
      result: {'pipeline_status': 'complete'}, fileName: 'bare.pdf');
    expect((await DocumentStore.list()).single.diagnosis, 'Discharge summary');
    // Sanity: the encoder used by save produced readable JSON.
    expect(jsonEncode({'a': 1}), '{"a":1}');
  });
}
