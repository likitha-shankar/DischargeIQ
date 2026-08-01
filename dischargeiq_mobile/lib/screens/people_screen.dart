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
  const PeopleScreen({super.key, required this.onUpload});

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
  }

  /// Documents belonging to one person.
  List<SavedDocument> _docsFor(String personId) =>
      _docs.where((d) => d.personId == personId).toList();

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
    await _refresh();
    if (!mounted) return;
    // Drop straight into the new person's folder. It is empty by definition,
    // and the "add already-analysed documents" action lives there - which is
    // exactly what someone wants the moment after creating a profile for a
    // family member whose summaries are already on the phone.
    await _openPerson(added);
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
    await PersonStore.remove(person.id);
    // Deleting whoever was active must not leave uploads filing into a ghost.
    if (await PersonStore.activeId() == person.id) {
      await PersonStore.setActive(null);
    }
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
                          onDelete: () => _deletePerson(p),
                          dark: dark,
                        )),
                    if (unassigned.isNotEmpty)
                      _PersonRow(
                        person: null,
                        count: unassigned.length,
                        onTap: () => _openPerson(null),
                        // Unassigned is a built-in bucket, not a profile.
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
    required this.onDelete,
    required this.dark,
  });

  final Person? person;
  final int count;
  final VoidCallback onTap;

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
        trailing: onDelete == null
            ? const Icon(Icons.chevron_right)
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
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

/// Add-person form. Name is required; relationship and age steer the reader.
class _AddPersonSheet extends StatefulWidget {
  const _AddPersonSheet();

  @override
  State<_AddPersonSheet> createState() => _AddPersonSheetState();
}

class _AddPersonSheetState extends State<_AddPersonSheet> {
  final _name = TextEditingController();
  final _age = TextEditingController();
  Relationship _relationship = Relationship.myself;
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _age.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) return;
    setState(() => _saving = true);
    final age = int.tryParse(_age.text.trim());
    final person = await PersonStore.add(
      name: _name.text,
      relationship: _relationship,
      // Reject implausible ages rather than storing them: a typo here would
      // silently change who every tab is written to.
      age: (age != null && age >= 0 && age <= 120) ? age : null,
    );
    if (!mounted) return;
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
            'Add a person',
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
            decoration: const InputDecoration(
              labelText: 'Name',
              hintText: 'Priya, Mom, or just Me',
              border: OutlineInputBorder(),
            ),
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
            decoration: const InputDecoration(
              labelText: 'Age (optional)',
              helperText: 'Helps us write for the right reader',
              border: OutlineInputBorder(),
            ),
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
  Future<void> _refile(SavedDocument doc) async {
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
            ...widget.people.map((p) => ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(p.name),
                  subtitle: Text(p.relationship.label),
                  onTap: () => Navigator.pop(ctx, p.id),
                )),
          ],
        ),
      ),
    );
    if (target == null) return;
    await DocumentStore.assignPerson(doc.id, target);
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
