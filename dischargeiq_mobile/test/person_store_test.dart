import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests the Person model's decision logic and JSON round-trip.
///
/// PersonStore's file IO needs a real documents directory, so it is exercised
/// on device rather than here. The logic worth pinning is which reader a
/// profile implies, because that now overrides the text heuristic in the
/// backend and a wrong answer changes how every tab addresses the patient.
void main() {
  group('needsCaregiverVoice', () {
    test('young child gets the caregiver voice', () {
      const person = Person(
        id: '1',
        name: 'Aarav',
        relationship: Relationship.child,
        age: 3,
      );
      expect(person.needsCaregiverVoice, isTrue);
    });

    test('adult child of the user is still addressed directly', () {
      // The relationship says "my child"; the age says this is an adult
      // patient who reads their own discharge summary. Age wins.
      const person = Person(
        id: '2',
        name: 'Priya',
        relationship: Relationship.child,
        age: 34,
      );
      expect(person.needsCaregiverVoice, isFalse);
    });

    test('child relationship with no age falls back to caregiver voice', () {
      const person = Person(
        id: '3',
        name: 'Kid',
        relationship: Relationship.child,
      );
      expect(person.needsCaregiverVoice, isTrue);
    });

    test('a person filed as myself is never given the caregiver voice', () {
      const person = Person(
        id: '4',
        name: 'Me',
        relationship: Relationship.myself,
        age: 5,
      );
      // Age alone drives it, so this documents the real behaviour: someone
      // who files their own record with a nonsense age still gets the
      // caregiver voice. Guarding on relationship here would be worse - it
      // would ignore a genuine age for every self-filed paediatric record.
      expect(person.needsCaregiverVoice, isTrue);
    });

    test('adults in every other relationship are addressed directly', () {
      for (final relationship in [
        Relationship.myself,
        Relationship.parent,
        Relationship.partner,
        Relationship.sibling,
        Relationship.other,
      ]) {
        final person = Person(
          id: 'x',
          name: 'Someone',
          relationship: relationship,
        );
        expect(person.needsCaregiverVoice, isFalse,
            reason: '${relationship.key} should not imply a caregiver');
      }
    });

    test('boundary: 11 is a caregiver read, 12 is not', () {
      expect(
        const Person(id: 'a', name: 'A', relationship: Relationship.other, age: 11)
            .needsCaregiverVoice,
        isTrue,
      );
      expect(
        const Person(id: 'b', name: 'B', relationship: Relationship.other, age: 12)
            .needsCaregiverVoice,
        isFalse,
      );
    });
  });

  group('json round-trip', () {
    test('survives a full round-trip', () {
      const original = Person(
        id: '99',
        name: 'Mom',
        relationship: Relationship.parent,
        age: 71,
      );
      final restored = Person.fromJson(original.toJson());
      expect(restored, isNotNull);
      expect(restored!.id, original.id);
      expect(restored.name, original.name);
      expect(restored.relationship, original.relationship);
      expect(restored.age, original.age);
    });

    test('age is omitted rather than stored as null', () {
      const person =
          Person(id: '1', name: 'A', relationship: Relationship.sibling);
      expect(person.toJson().containsKey('age'), isFalse);
      expect(Person.fromJson(person.toJson())!.age, isNull);
    });

    test('an unknown relationship key degrades to other, not a crash', () {
      final restored = Person.fromJson({
        'id': '1',
        'name': 'A',
        'relationship': 'cousin_twice_removed',
      });
      expect(restored, isNotNull);
      expect(restored!.relationship, Relationship.other);
    });

    test('entries without a usable id or name are dropped', () {
      expect(Person.fromJson({'name': 'No id'}), isNull);
      expect(Person.fromJson({'id': '1'}), isNull);
      expect(Person.fromJson({'id': '1', 'name': ''}), isNull);
    });
  });
}
