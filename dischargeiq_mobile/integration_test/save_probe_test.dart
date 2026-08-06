// Integration probe: exercises the REAL DocumentStore.save + PersonStore.add
// against the app's real documents directory on the device, to prove saving
// works rather than asserting it.
import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('real device: profile saves and document persists', (t) async {
    final p = await PersonStore.add(
        name: 'Probe Person', relationship: Relationship.myself, age: 40);
    expect(p, isNotNull, reason: 'PROFILE SAVE FAILED on device');

    final id = await DocumentStore.save(
      result: const {
        'pipeline_status': 'complete',
        'extraction': {'primary_diagnosis': 'Heart failure'},
        'diagnosis_explanation': 'Your heart was not pumping well.',
        'medication_rationale': '',
        'recovery_trajectory': '',
        'escalation_guide': '',
      },
      fileName: 'probe.pdf',
      personId: p!.id,
    );
    expect(id, isNotNull, reason: 'DOCUMENT SAVE FAILED on device');

    final docs = await DocumentStore.list();
    expect(docs, hasLength(1), reason: 'DOCUMENT NOT IN LIBRARY');
    expect(docs.single.personId, p.id);
    expect(docs.single.diagnosis, 'Heart failure');

    final reopened = await DocumentStore.load(id!);
    expect(reopened, isNotNull, reason: 'SAVED DOC COULD NOT BE REOPENED');
  });
}
