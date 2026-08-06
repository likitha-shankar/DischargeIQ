import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:dischargeiq_mobile/services/scan_session_store.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Person-first home: whose documents are on this phone, and how many.
///
/// A discharge summary belongs to a person, not to a filename. "Priya (my
/// sister)" is what someone recognises three weeks later; "scan_20260728.pdf"
/// is not. People who care for several family members are a core case, not an
/// edge one.
///
/// Documents saved before people existed appear under "Unassigned" rather than
/// being forced through a filing prompt. Blocking someone from their discharge
/// summary with a modal is the wrong trade when they may be tired or in pain;
/// filing is a tidying task they can do whenever.
class PeopleScreen extends StatefulWidget {
  const PeopleScreen({
    super.key,
    required this.onUpload,
    this.openAddOnLaunch = false,
  });

  /// Opens the add-person sheet as soon as the screen appears.
  ///
  /// The switcher offers "Add a person" and "Manage people and documents" as
  /// separate choices; without this they both landed on the same list and the
  /// first one silently did not do what it said.
  final bool openAddOnLaunch;

  /// Opens the upload flow for a person, returning to the home screen.
  ///
  /// Takes the person so tapping "Add document" inside someone's folder files
  /// the new upload under THEM rather than under whoever happened to be
  /// active. Null means "no particular person" (the top-level button).
  final void Function(Person? person) onUpload;

  @override
  State<PeopleScreen> createState() => _PeopleScreenState();
}

class _PeopleScreenState extends State<PeopleScreen> {
  List<Person> _people = const [];
  List<SavedDocument> _docs = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final people = await PersonStore.list();
    final docs = await DocumentStore.list();
    if (!mounted) return;
    setState(() {
      _people = people;
      _docs = docs;
      _loading = false;
    });
    // Opened straight from the switcher's "Add a person". Runs after the
    // first load so the list behind the sheet is already correct, and only
    // once - _refresh() is called again on every return from a subscreen.
    if (widget.openAddOnLaunch && !_addSheetShown) {
      _addSheetShown = true;
      await _addPerson();
    }
  }

  /// Guard so the launch sheet opens once, not on every later refresh.
  bool _addSheetShown = false;

  /// Documents belonging to one person.
  List<SavedDocument> _docsFor(String personId) =>
      DocumentStore.forPerson(_docs, personId);

  /// Documents with no person, or whose person has since been deleted.
  List<SavedDocument> get _unassigned {
    final ids = _people.map((p) => p.id).toSet();
    return _docs.where((d) => d.personId == null || !ids.contains(d.personId)).toList();
  }

  Future<void> _addPerson() async {
    final added = await showModalBottomSheet<Person>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _AddPersonSheet(),
    );
    if (added == null) return;
    // Whoever was just created becomes the active person. Without this the
    // switcher still reads "All" after adding someone, so the next upload
    // lands in Unassigned and no audience is sent - the caregiver voice for a
    // young child would silently never trigger. Creating a person is an
    // explicit act; filing under them is what it was for.
    await PersonStore.setActive(added.id);
    await _refresh();
    if (!mounted) return;
    // Drop straight into the new person's folder. It is empty by definition,
    // and the "add already-analysed documents" action lives there - which is
    // exactly what someone wants the moment after creating a profile for a
    // family member whose summaries are already on the phone.
    await _openPerson(added);
  }

  /// Edit a profile's name, relationship, or age in place.
  ///
  /// Age and relationship decide who agent output addresses, so fixing a
  /// typo here matters beyond cosmetics - it changes the reader for every
  /// future upload filed under this person.
  Future<void> _editPerson(Person person) async {
    final updated = await showModalBottomSheet<Person>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _AddPersonSheet(initial: person),
    );
    if (updated != null) await _refresh();
  }

  /// Delete a profile, letting the patient decide what happens to its
  /// documents.
  ///
  /// The two are genuinely separate decisions and only the patient knows
  /// which they mean. "Delete Mom's profile" can mean tidying a duplicate
  /// profile whose summaries still matter, or clearing out records they are
  /// done with. Guessing either way is wrong, so the choice is explicit and
  /// keeping the documents is the default - it is the recoverable option.
  Future<void> _deletePerson(Person person) async {
    final docs = _docsFor(person.id);
    final count = docs.length;

    if (count == 0) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Delete ${person.name}?'),
          content: const Text(
            'This profile has no documents. It will be removed from this phone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: FilledButton.styleFrom(backgroundColor: kMedDiscontinued),
              child: const Text('Delete profile'),
            ),
          ],
        ),
      );
      if (ok != true) return;
      await _finishDelete(person, docs, deleteDocuments: false);
      return;
    }

    final noun = count == 1 ? 'document' : 'documents';
    final choice = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Delete ${person.name}?'),
        content: Text(
          'This profile has $count $noun. What should happen to '
          '${count == 1 ? 'it' : 'them'}?',
        ),
        actionsOverflowDirection: VerticalDirection.down,
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'cancel'),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'keep'),
            child: Text('Keep $noun'),
          ),
          // Destructive option styled and worded so it cannot be picked by
          // accident: it says what is being destroyed, not just "delete".
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'delete'),
            style: TextButton.styleFrom(foregroundColor: kMedDiscontinued),
            child: Text('Delete profile and $noun'),
          ),
        ],
      ),
    );

    if (choice == null || choice == 'cancel') return;

    if (choice == 'delete') {
      // Second confirmation. Discharge summaries are not recoverable from
      // this phone once removed, and the patient may no longer have the
      // paper copy, so a single tap is not enough authority to destroy them.
      if (!mounted) return;
      final sure = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Permanently delete $count $noun?'),
          content: Text(
            'The ${count == 1 ? 'summary' : 'summaries'} for ${person.name} '
            'will be removed from this phone and cannot be recovered. You '
            'would need the original paper or PDF to analyse '
            '${count == 1 ? 'it' : 'them'} again.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: FilledButton.styleFrom(backgroundColor: kMedDiscontinued),
              child: const Text('Delete permanently'),
            ),
          ],
        ),
      );
      if (sure != true) return;
    }

    await _finishDelete(person, docs, deleteDocuments: choice == 'delete');
  }

  /// Apply a confirmed profile deletion.
  ///
  /// Documents are handled BEFORE the person record is removed. If this fails
  /// partway, the documents are already unfiled or gone rather than pointing
  /// at a person who no longer exists.
  Future<void> _finishDelete(
    Person person,
    List<SavedDocument> docs, {
    required bool deleteDocuments,
  }) async {
    for (final doc in docs) {
      if (deleteDocuments) {
        await DocumentStore.delete(doc.id);
      } else {
        await DocumentStore.assignPerson(doc.id, null);
      }
    }
    // Read the active id BEFORE removing the person. activeId() verifies the
    // id still resolves, so asking after the removal always answers null and
    // the stored key would never be cleared.
    final wasActive = await PersonStore.activeId() == person.id;
    await PersonStore.remove(person.id);
    // Deleting whoever was active must not leave uploads filing into a ghost.
    if (wasActive) await PersonStore.setActive(null);
    if (mounted) await _refresh();
  }

  Future<void> _openPerson(Person? person) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute<void>(
        builder: (_) => _PersonDocumentsScreen(
          person: person,
          documents: person == null ? _unassigned : _docsFor(person.id),
          people: _people,
          onUpload: widget.onUpload,
        ),
      ),
    );
    // Refresh on return: documents may have been refiled or opened.
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final unassigned = _unassigned;

    return Scaffold(
      backgroundColor: dark ? kBgDark : kBgLight,
      appBar: AppBar(
        title: const Text('My people'),
        backgroundColor: dark ? kBgDark : kBgLight,
        elevation: 0,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => widget.onUpload(null),
        backgroundColor: kTeal,
        icon: const Icon(Icons.add, color: Colors.white),
        label: const Text('Add document', style: TextStyle(color: Colors.white)),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                children: [
                  if (_people.isEmpty && unassigned.isEmpty)
                    _EmptyState(onAddPerson: _addPerson, onUpload: widget.onUpload)
                  else ...[
                    ..._people.map((p) => _PersonRow(
                          person: p,
                          count: _docsFor(p.id).length,
                          onTap: () => _openPerson(p),
                          onEdit: () => _editPerson(p),
                          onDelete: () => _deletePerson(p),
                          dark: dark,
                        )),
                    if (unassigned.isNotEmpty)
                      _PersonRow(
                        person: null,
                        count: unassigned.length,
                        onTap: () => _openPerson(null),
                        // Unassigned is a built-in bucket, not a profile.
                        onEdit: null,
                        onDelete: null,
                        dark: dark,
                      ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _addPerson,
                      icon: const Icon(Icons.person_add_alt_1, size: 20),
                      label: const Text('Add person'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: dark ? kTealGlow : kTeal,
                        side: BorderSide(color: dark ? kBorderDark : kBorderLight),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}

/// One row: a person, or the Unassigned bucket when [person] is null.
class _PersonRow extends StatelessWidget {
  const _PersonRow({
    required this.person,
    required this.count,
    required this.onTap,
    required this.onEdit,
    required this.onDelete,
    required this.dark,
  });

  final Person? person;
  final int count;
  final VoidCallback onTap;

  /// Null for built-in rows (Unassigned), which cannot be edited.
  final VoidCallback? onEdit;

  /// Null for built-in rows (Unassigned), which cannot be deleted.
  final VoidCallback? onDelete;

  final bool dark;

  @override
  Widget build(BuildContext context) {
    final name = person?.name ?? 'Unassigned';
    final currentPerson = person;
    final subtitle = currentPerson == null
        ? 'Saved before you added people'
        : currentPerson.relationship.label;
    final initial = name.characters.first.toUpperCase();

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: dark ? kCardDark : kCardLight,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: dark ? kBorderDark : kBorderLight),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        leading: CircleAvatar(
          backgroundColor: person == null ? kTextHintLight : kTealMid,
          child: person == null
              ? const Icon(Icons.folder_open, color: Colors.white, size: 20)
              : Text(initial,
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w700)),
        ),
        title: Text(
          name,
          style: TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 16,
            color: dark ? kTextPrimaryDark : kTextPrimaryLight,
          ),
        ),
        subtitle: Text(
          '$subtitle  ·  $count ${count == 1 ? 'document' : 'documents'}',
          style: TextStyle(
            fontSize: 13,
            color: dark ? kTextSecondaryDark : kTextSecondaryLight,
          ),
        ),
        trailing: onDelete == null && onEdit == null
            ? const Icon(Icons.chevron_right)
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (onEdit != null)
                    IconButton(
                      icon: const Icon(Icons.edit_outlined, size: 20),
                      color: dark ? kTealGlow : kTeal,
                      tooltip: 'Edit profile',
                      onPressed: onEdit,
                    ),
                  if (onDelete != null)
                    IconButton(
                      icon: const Icon(Icons.delete_outline, size: 20),
                      color: kMedDiscontinued,
                      tooltip: 'Delete profile',
                      onPressed: onDelete,
                    ),
                  const Icon(Icons.chevron_right),
                ],
              ),
        onTap: onTap,
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onAddPerson, required this.onUpload});

  final VoidCallback onAddPerson;
  final void Function(Person? person) onUpload;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(top: 60),
      child: Column(
        children: [
          Icon(Icons.people_outline, size: 56, color: dark ? kTealGlow : kTealMid),
          const SizedBox(height: 16),
          Text(
            'Who are you keeping track of?',
            style: TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w700,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Add yourself, or someone you look after. Their discharge '
              'documents are saved under their name so you can find them later.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                height: 1.6,
                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
              ),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onAddPerson,
            icon: const Icon(Icons.person_add_alt_1),
            label: const Text('Add a person'),
            style: FilledButton.styleFrom(
              backgroundColor: kTeal,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
            ),
          ),
          TextButton(
            onPressed: () => onUpload(null),
            child: const Text('Skip and upload a document'),
          ),
        ],
      ),
    );
  }
}

/// Add/edit-person form. Name is required; relationship and age steer the
/// reader. Pass [initial] to edit an existing person in place - same fields,
/// same validation, saved via PersonStore.update instead of add.
class _AddPersonSheet extends StatefulWidget {
  const _AddPersonSheet({this.initial});

  final Person? initial;

  @override
  State<_AddPersonSheet> createState() => _AddPersonSheetState();
}

class _AddPersonSheetState extends State<_AddPersonSheet> {
  late final _name = TextEditingController(text: widget.initial?.name ?? '');
  late final _age =
      TextEditingController(text: widget.initial?.age?.toString() ?? '');
  late Relationship _relationship =
      widget.initial?.relationship ?? Relationship.myself;
  bool _saving = false;

  /// Field-level messages. Null means the field is fine. Silence was the old
  /// behaviour and it was indistinguishable from the app being broken: an
  /// empty name made Save do nothing at all, and "999" in the age box was
  /// dropped without a word even though age decides who the output addresses.
  String? _nameError;
  String? _ageError;

  @override
  void dispose() {
    _name.dispose();
    _age.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    final parsedAge = parseOptionalAge(_age.text);
    final age = parsedAge.age;

    if (name.isEmpty || !parsedAge.valid) {
      setState(() {
        _nameError = name.isEmpty ? 'Enter a name' : null;
        _ageError =
            parsedAge.valid ? null : 'Enter an age between 0 and $kMaxPersonAge';
      });
      return;
    }

    setState(() {
      _nameError = null;
      _ageError = null;
      _saving = true;
    });

    final existing = widget.initial;
    final Person? person;
    if (existing == null) {
      person = await PersonStore.add(
        name: name,
        relationship: _relationship,
        age: age,
      );
    } else {
      final updated = Person(
        id: existing.id,
        name: name,
        relationship: _relationship,
        age: age,
      );
      person = await PersonStore.update(updated) ? updated : null;
    }
    if (!mounted) return;

    // A failed write used to close the sheet as though it had worked, losing
    // the entry with no trace. Stay open and say so instead.
    if (person == null) {
      setState(() {
        _saving = false;
        _nameError = 'Could not save. Try again.';
      });
      return;
    }
    Navigator.pop(context, person);
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 8,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.initial == null ? 'Add a person' : 'Edit ${widget.initial!.name}',
            style: TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w700,
              color: dark ? kTextPrimaryDark : kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            autofocus: true,
            textCapitalization: TextCapitalization.words,
            decoration: InputDecoration(
              labelText: 'Name',
              hintText: 'Priya, Mom, or just Me',
              border: const OutlineInputBorder(),
              errorText: _nameError,
            ),
            onChanged: (_) {
              if (_nameError != null) setState(() => _nameError = null);
            },
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<Relationship>(
            initialValue: _relationship,
            decoration: const InputDecoration(
              labelText: 'Who is this?',
              border: OutlineInputBorder(),
            ),
            items: Relationship.values
                .map((r) => DropdownMenuItem(value: r, child: Text(r.label)))
                .toList(),
            onChanged: (r) => setState(() => _relationship = r ?? _relationship),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _age,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: 'Age (optional)',
              helperText: 'Helps us write for the right reader',
              border: const OutlineInputBorder(),
              errorText: _ageError,
            ),
            onChanged: (_) {
              if (_ageError != null) setState(() => _ageError = null);
            },
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _saving ? null : _save,
              style: FilledButton.styleFrom(
                backgroundColor: kTeal,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: Text(_saving ? 'Saving...' : 'Save'),
            ),
          ),
        ],
      ),
    );
  }
}

/// One person's documents, with the option to refile them.
class _PersonDocumentsScreen extends StatefulWidget {
  const _PersonDocumentsScreen({
    required this.person,
    required this.documents,
    required this.people,
    required this.onUpload,
  });

  final Person? person;
  final List<SavedDocument> documents;
  final List<Person> people;
  final void Function(Person? person) onUpload;

  @override
  State<_PersonDocumentsScreen> createState() => _PersonDocumentsScreenState();
}

class _PersonDocumentsScreenState extends State<_PersonDocumentsScreen> {
  late List<SavedDocument> _docs = widget.documents;

  Future<void> _open(SavedDocument doc) async {
    final loaded = await DocumentStore.load(doc.id);
    if (!mounted) return;
    if (loaded == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open that document.')),
      );
      return;
    }
    final (result, pdf) = loaded;
    // Same path a fresh analysis takes, with no API calls. Clearing the scan
    // session prevents an in-progress scan from mixing into a reopened doc.
    context.read<DischargeProvider>().scanPages.clear();
    ScanSessionStore.clear();
    context.read<DischargeProvider>().setResult(
          result,
          pdfBytes: pdf,
          fileName: doc.fileName,
          docId: doc.id,
        );
    if (mounted) Navigator.pop(context);
  }

  /// Move a document to another person. Offered on every document so a
  /// mis-filed summary is one tap to fix, not a reason to re-upload.
  ///
  /// The folder being viewed is left out of the list: "moving" a document to
  /// where it already is did nothing but drop it from the visible list, which
  /// reads as the summary having been lost. Unassigned is offered as a real
  /// destination so a document filed under the wrong person can be taken back
  /// out rather than only shuffled between people.
  Future<void> _refile(SavedDocument doc) async {
    // Sentinel rather than null: null is the "sheet dismissed" answer, and
    // un-filing has to be distinguishable from cancelling.
    const unassign = '__unassigned__';
    final current = widget.person;
    final targets = widget.people.where((p) => p.id != current?.id).toList();

    final target = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Move this document to...',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            ),
            ...targets.map((p) => ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(p.name),
                  subtitle: Text(p.relationship.label),
                  onTap: () => Navigator.pop(ctx, p.id),
                )),
            if (current != null)
              ListTile(
                leading: const Icon(Icons.folder_open),
                title: const Text('Unassigned'),
                subtitle: const Text('Not filed under anyone'),
                onTap: () => Navigator.pop(ctx, unassign),
              ),
          ],
        ),
      ),
    );
    if (target == null) return;
    await DocumentStore.assignPerson(doc.id, target == unassign ? null : target);
    if (!mounted) return;
    setState(() => _docs = _docs.where((d) => d.id != doc.id).toList());
  }

  /// Pull already-analysed documents into this person's folder.
  ///
  /// Multi-select, because someone setting up a profile for a parent usually
  /// has several of their summaries already on the phone and should not have
  /// to file them one at a time.
  Future<void> _addExisting() async {
    final person = widget.person;
    if (person == null) return;
    final all = await DocumentStore.list();
    final candidates = all.where((d) => d.personId != person.id).toList();
    if (!mounted) return;

    if (candidates.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No other documents on this phone.')),
      );
      return;
    }

    final picked = <String>{};
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                child: Text(
                  'Add documents to ${person.name}',
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                ),
              ),
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: candidates
                      .map((d) => CheckboxListTile(
                            value: picked.contains(d.id),
                            title: Text(
                              d.diagnosis.isEmpty ? d.fileName : d.diagnosis,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              '${d.savedAt.month}/${d.savedAt.day}/${d.savedAt.year}',
                            ),
                            onChanged: (on) => setSheetState(() {
                              if (on == true) {
                                picked.add(d.id);
                              } else {
                                picked.remove(d.id);
                              }
                            }),
                          ))
                      .toList(),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: picked.isEmpty ? null : () => Navigator.pop(ctx, true),
                    style: FilledButton.styleFrom(
                      backgroundColor: kTeal,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: Text('Add ${picked.length} document'
                        '${picked.length == 1 ? '' : 's'}'),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );

    if (confirmed != true || picked.isEmpty) return;

    // A document already filed under someone else is MOVED, not copied - one
    // document has one owner. Taking it away from another person silently is
    // the kind of thing you only notice when their folder is mysteriously
    // empty, so name them and ask first.
    final owned = candidates
        .where((d) => picked.contains(d.id) && d.personId != null)
        .toList();
    if (owned.isNotEmpty && mounted) {
      final owners = <String>{};
      for (final d in owned) {
        for (final other in widget.people) {
          if (other.id == d.personId) owners.add(other.name);
        }
      }
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Move ${owned.length == 1 ? 'this document' : 'these documents'}?'),
          content: Text(
            owners.isEmpty
                ? '${owned.length} of these are filed under someone else. '
                    'Moving them to ${person.name} removes them from where '
                    'they are now.'
                : '${owned.length == 1 ? 'This document is' : '${owned.length} of these are'} '
                    'currently filed under ${owners.join(', ')}. '
                    'Moving to ${person.name} removes '
                    '${owned.length == 1 ? 'it' : 'them'} from there.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: FilledButton.styleFrom(backgroundColor: kTeal),
              child: const Text('Move'),
            ),
          ],
        ),
      );
      if (ok != true) return;
    }

    for (final id in picked) {
      await DocumentStore.assignPerson(id, person.id);
    }
    final refreshed = await DocumentStore.list();
    if (!mounted) return;
    setState(() =>
        _docs = refreshed.where((d) => d.personId == person.id).toList());
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final title = widget.person?.name ?? 'Unassigned';

    return Scaffold(
      backgroundColor: dark ? kBgDark : kBgLight,
      appBar: AppBar(
        title: Text(title),
        backgroundColor: dark ? kBgDark : kBgLight,
        elevation: 0,
        actions: [
          // Documents analysed before this person existed have to be
          // reachable from inside their folder. Without this the only way to
          // file an old summary is to remember which bucket it landed in and
          // move it from there, which nobody will do.
          if (widget.person != null)
            IconButton(
              tooltip: 'Add already-analysed documents',
              icon: const Icon(Icons.library_add_outlined),
              onPressed: _addExisting,
            ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => widget.onUpload(widget.person),
        backgroundColor: kTeal,
        icon: const Icon(Icons.add, color: Colors.white),
        label: const Text('Add document', style: TextStyle(color: Colors.white)),
      ),
      body: _docs.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Text(
                  'No documents for $title yet.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
              itemCount: _docs.length,
              itemBuilder: (context, i) {
                final doc = _docs[i];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  color: dark ? kCardDark : kCardLight,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: BorderSide(color: dark ? kBorderDark : kBorderLight),
                  ),
                  child: ListTile(
                    title: Text(
                      doc.diagnosis.isEmpty ? doc.fileName : doc.diagnosis,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    subtitle: Text(
                      '${doc.savedAt.month}/${doc.savedAt.day}/${doc.savedAt.year}',
                      style: TextStyle(
                        fontSize: 13,
                        color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                    trailing: widget.people.isEmpty
                        ? null
                        : IconButton(
                            icon: const Icon(Icons.drive_file_move_outline),
                            tooltip: 'Move to another person',
                            onPressed: () => _refile(doc),
                          ),
                    onTap: () => _open(doc),
                  ),
                );
              },
            ),
    );
  }
}
