/// People whose discharge documents this device holds.
///
/// A document belongs to a person, not to a filename. "Priya (sister)" is what
/// the patient recognises; "scan_20260728_141233.pdf" is not.
///
/// PRIVACY: people live only on the device, in the app's documents directory.
/// Names are identifying, and the backend schema is deliberately PHI-free
/// (see CLAUDE.md: only structured fields, hashes, and metadata are stored
/// server-side). Nothing in this file is ever uploaded.
///
/// The relationship and age captured here also settle a question the pipeline
/// otherwise has to guess: who the agent output should address. A document
/// filed under a 3-year-old is definitively a caregiver-voice document, which
/// is more reliable than inferring age from the document text.
library;

import 'dart:convert';
import 'dart:io';

import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// How the person filing documents relates to the patient they are filing for.
///
/// This is the patient's relationship TO THE APP USER, so `child` means "the
/// patient is my child" and therefore the output should address the caregiver.
enum Relationship { myself, child, parent, partner, sibling, other }

extension RelationshipLabel on Relationship {
  /// Human label for pickers and list rows.
  String get label => switch (this) {
        Relationship.myself => 'Myself',
        Relationship.child => 'My child',
        Relationship.parent => 'My parent',
        Relationship.partner => 'My partner',
        Relationship.sibling => 'My sibling',
        Relationship.other => 'Someone else',
      };

  /// Stable key for storage. Never derive this from [label] - renaming a label
  /// would orphan every previously saved person.
  String get key => name;
}

/// Below this age the app writes to the caregiver rather than the patient.
/// Matches _CAREGIVER_AGE_MAX in dischargeiq/utils/audience.py; the two must
/// move together or the app and the backend will disagree about the reader.
const int kCaregiverAgeMax = 12;

/// Oldest age the form accepts. Past this it is a typo, not a patient.
const int kMaxPersonAge = 120;

/// Interpret the optional age field of the add/edit form.
///
/// Age is optional, so blank input is valid and yields a null age. Text that
/// is present but not a plausible age is a typo worth telling the user about
/// rather than dropping: age decides whether every tab addresses the patient
/// or their caregiver, so a silently ignored "6" would change the whole
/// document's voice without anyone noticing.
///
/// Args:
///   raw: Exactly what the user typed, untrimmed.
///
/// Returns:
///   A record whose `valid` is false only for unparseable or out-of-range
///   text, and whose `age` is the accepted value (null when left blank).
({bool valid, int? age}) parseOptionalAge(String raw) {
  final trimmed = raw.trim();
  if (trimmed.isEmpty) return (valid: true, age: null);
  final parsed = int.tryParse(trimmed);
  if (parsed == null || parsed < 0 || parsed > kMaxPersonAge) {
    return (valid: false, age: null);
  }
  return (valid: true, age: parsed);
}

/// One person on this device.
class Person {
  const Person({
    required this.id,
    required this.name,
    required this.relationship,
    this.age,
  });

  final String id;
  final String name;
  final Relationship relationship;

  /// Optional. Only meaningful for deciding the reader, so it is never
  /// required - a patient who does not want to enter an age still gets a
  /// working profile.
  final int? age;

  /// Whether agent output for this person should address a caregiver.
  ///
  /// True when the patient is a young child, decided by age when it was given
  /// and by relationship otherwise. `Relationship.child` alone is not enough
  /// on its own once an age is present: an adult child of the user is still an
  /// adult patient and should be addressed directly.
  bool get needsCaregiverVoice {
    if (age != null) return age! < kCaregiverAgeMax;
    return relationship == Relationship.child;
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'relationship': relationship.key,
        if (age != null) 'age': age,
      };

  /// Rebuild from stored JSON, tolerating a relationship key written by a
  /// newer build than this one.
  static Person? fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final name = json['name'];
    if (id is! String || name is! String || name.isEmpty) return null;
    final rawAge = json['age'];
    return Person(
      id: id,
      name: name,
      relationship: Relationship.values.firstWhere(
        (r) => r.key == json['relationship'],
        orElse: () => Relationship.other,
      ),
      age: rawAge is int ? rawAge : null,
    );
  }
}

class PersonStore {
  /// Key for the person new uploads are filed under.
  static const _activeKey = 'active_person_id';

  /// The person whose documents the home screen is showing, and whom a new
  /// upload will be filed under.
  ///
  /// Having one active person is what stops uploads landing in Unassigned:
  /// the answer to "whose document is this?" is already on screen when the
  /// patient taps upload, so it never has to be asked afterwards.
  static Future<String?> activeId() async {
    final prefs = await SharedPreferences.getInstance();
    final id = prefs.getString(_activeKey);
    if (id == null) return null;
    // A stale id (person deleted) must not silently file documents under a
    // ghost. Verify before returning.
    return (await byId(id)) == null ? null : id;
  }

  /// Set the active person, or clear it with null.
  static Future<void> setActive(String? id) async {
    final prefs = await SharedPreferences.getInstance();
    if (id == null) {
      await prefs.remove(_activeKey);
    } else {
      await prefs.setString(_activeKey, id);
    }
  }

  /// The active person, or null meaning the built-in "All" view.
  ///
  /// Null is a real state, not a missing one. "All" shows every document on
  /// the phone and is the default, so someone who never wants to think about
  /// profiles never has to: they upload, and everything stays in one list.
  /// It cannot be renamed or deleted because it is not stored - it is the
  /// absence of a filter.
  ///
  /// There is deliberately no "fall back to the first person" rule. That
  /// would silently file one person's discharge summary under another the
  /// moment a second profile existed, which is the exact mix-up this whole
  /// feature is meant to prevent.
  static Future<Person?> active() async => byId(await activeId());

  static Future<File> _file() async {
    // healedDocumentsDir repairs a corrupted container (a file squatting on
    // the Documents path) that made every profile save fail with "Could not
    // save" - writeAsString cannot create a file under something that is not
    // a directory, and the catch-all in _write turned that into a permanent,
    // unexplained failure.
    final base = await healedDocumentsDir();
    final file = File('${base.path}/people.json');
    if (!await file.exists()) await file.writeAsString('[]');
    return file;
  }

  /// Every person on this device, in creation order.
  ///
  /// Returns an empty list rather than throwing when the file is missing or
  /// corrupt: a damaged profile list must not stop someone reading their
  /// discharge summary.
  static Future<List<Person>> list() async {
    try {
      final raw = jsonDecode(await (await _file()).readAsString());
      if (raw is! List) return [];
      return raw
          .whereType<Map>()
          .map((e) => Person.fromJson(e.cast<String, dynamic>()))
          .whereType<Person>()
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// Look up one person, or null when the id is unknown (e.g. the person was
  /// deleted while a document still referenced them).
  static Future<Person?> byId(String? id) async {
    if (id == null) return null;
    for (final person in await list()) {
      if (person.id == id) return person;
    }
    return null;
  }

  /// Add a person and return them, or null if the write failed.
  static Future<Person?> add({
    required String name,
    required Relationship relationship,
    int? age,
  }) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return null;
    final person = Person(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      name: trimmed,
      relationship: relationship,
      age: age,
    );
    final people = await list()..add(person);
    return await _write(people) ? person : null;
  }

  /// Replace a person's details, matched by id. No-op when the id is unknown.
  static Future<bool> update(Person updated) async {
    final people = await list();
    final index = people.indexWhere((p) => p.id == updated.id);
    if (index < 0) return false;
    people[index] = updated;
    return _write(people);
  }

  /// Remove a person. Their documents are NOT deleted - they become unassigned
  /// and can be refiled, because destroying a discharge summary as a side
  /// effect of tidying a name would be indefensible.
  static Future<bool> remove(String id) async {
    final people = await list()..removeWhere((p) => p.id == id);
    return _write(people);
  }

  static Future<bool> _write(List<Person> people) async {
    try {
      await (await _file())
          .writeAsString(jsonEncode(people.map((p) => p.toJson()).toList()));
      return true;
    } catch (_) {
      return false;
    }
  }
}
