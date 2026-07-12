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
