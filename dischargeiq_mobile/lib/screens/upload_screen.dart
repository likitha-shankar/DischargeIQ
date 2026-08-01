import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/loading_screen.dart';
import 'package:dischargeiq_mobile/screens/puzzle_screen.dart';
import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/widgets/person_switcher.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:dischargeiq_mobile/screens/people_screen.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/scan_session_store.dart';
import 'package:dischargeiq_mobile/widgets/journey_widgets.dart';
import 'package:dischargeiq_mobile/screens/scan_screen.dart';
import 'package:dischargeiq_mobile/screens/settings_screen.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Design A (light) / Design B (dark) upload; follows [ThemeData] brightness.
class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  Uint8List? _bytes;
  String? _fileName;

  /// Person a new upload will be filed under. Null until someone is added.
  Person? _activePerson;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  @override
  void initState() {
    super.initState();
    _loadActivePerson();
  }

  Future<void> _loadActivePerson() async {
    final person = await PersonStore.active();
    if (mounted) setState(() => _activePerson = person);
  }

  /// Bumped whenever the document library may have changed elsewhere.
  ///
  /// The saved-documents list keeps its own state, so refiling a document
  /// inside the people screen used to leave the home list showing the old
  /// owner until the app restarted. Changing this value changes that widget's
  /// key, which rebuilds it and re-reads from disk.
  int _libraryVersion = 0;

  /// Open the people library, then re-read everything it could have changed:
  /// the active person, and the document list itself.
  Future<void> _openPeople() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute<void>(
        builder: (_) => PeopleScreen(onUpload: _uploadFor),
      ),
    );
    await _loadActivePerson();
    if (mounted) setState(() => _libraryVersion++);
  }

  /// Return to the home screen ready to upload for [person].
  ///
  /// "Add document" inside the people screens used to call Navigator.pop,
  /// which only stepped back one level and read as the button undoing itself.
  /// Popping to the root lands on this screen, which is where uploading
  /// actually happens, and making the person active first means the new
  /// document files under whoever's folder the button was pressed in.
  Future<void> _uploadFor(Person? person) async {
    if (person != null) {
      await PersonStore.setActive(person.id);
    }
    if (!mounted) return;
    Navigator.popUntil(context, (route) => route.isFirst);
    await _loadActivePerson();
    if (mounted) setState(() => _libraryVersion++);
  }

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf'],
      withData: true,
    );
    if (!mounted || r == null || r.files.isEmpty) return;
    final f = r.files.single;
    final bytes = f.bytes;
    if (bytes == null) return;
    setState(() {
      _bytes = bytes;
      _fileName = f.name;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header strip: own background so it reads as a bar, title and
            // the full (never truncated) tagline stacked on the left.
            Container(
              decoration: BoxDecoration(
                color: _dark ? kSurfaceDark : kTealPale.withValues(alpha: 0.55),
                border: Border(
                  bottom: BorderSide(
                    color: _dark ? kBorderDark : kBorderLight,
                    width: 0.5,
                  ),
                ),
              ),
              padding: const EdgeInsets.only(left: 16, right: 4, top: 6, bottom: 6),
              child: Row(
                children: [
                  // Person switcher sits where the title was. Whose records
                  // are on screen is the single most important thing to keep
                  // visible when one phone holds several family members'
                  // documents - mixing up two people's medications is the
                  // failure this prevents. The product name is not worth the
                  // space; the patient already knows which app they opened.
                  Expanded(
                    child: PersonSwitcher(
                      active: _activePerson,
                      onChanged: (p) => setState(() => _activePerson = p),
                      onManage: _openPeople,
                    ),
                  ),
                  // Theme toggle on the landing page itself - patients should
                  // not have to find Settings to switch light/dark.
                  IconButton(
                    tooltip: _dark ? 'Switch to light mode' : 'Switch to dark mode',
                    icon: Icon(
                      _dark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
                      size: 20,
                      color: _dark ? kTealGlow : kTeal,
                    ),
                    onPressed: () => context
                        .read<ThemeProvider>()
                        .setMode(_dark ? ThemeMode.light : ThemeMode.dark),
                  ),
                  IconButton(
                    tooltip: 'Settings',
                    icon: Icon(
                      Icons.settings_outlined,
                      size: 20,
                      color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                    ),
                    onPressed: () => Navigator.push<void>(
                      context,
                      MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                // Single calm entrance: fade + small upward drift. No looping
                // motion anywhere - same no-pressure principle as the quiz.
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: 1),
                  duration: const Duration(milliseconds: 500),
                  curve: Curves.easeOutCubic,
                  builder: (context, t, child) => Opacity(
                    opacity: t,
                    child: Transform.translate(
                      offset: Offset(0, 14 * (1 - t)),
                      child: child,
                    ),
                  ),
                  child: Column(
                    children: [
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                      decoration: BoxDecoration(
                        color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: _dark ? kTealGlow.withValues(alpha: 0.2) : kTealGlow,
                          width: 0.5,
                        ),
                      ),
                      child: Text(
                        'Your discharge, simplified',
                        style: TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w500,
                          color: _dark ? kTealGlow : kTeal,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text.rich(
                      TextSpan(
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                          color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                          height: 1.2,
                        ),
                        children: [
                          const TextSpan(text: 'Understand everything\nthe doctor told '),
                          TextSpan(
                            text: 'you.',
                            style: TextStyle(
                              color: _dark ? kTealLight : kTeal,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Upload your PDF. Get plain answers. Go home ready.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                    const SizedBox(height: 20),
                    ..._stepTiles(),
                    const SizedBox(height: 16),
                    Semantics(
                      button: true,
                      label: 'Choose your discharge PDF file',
                      child: GestureDetector(
                        onTap: _pickFile,
                        child: CustomPaint(
                        foregroundPainter: _DashedBorderPainter(
                          color: _dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow,
                          strokeWidth: 1.5,
                          radius: 20,
                        ),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: _dark
                                ? kTeal.withValues(alpha: 0.12)
                                : kTealPale.withValues(alpha: 0.35),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Column(
                            children: [
                              Container(
                                width: 54,
                                height: 54,
                                decoration: BoxDecoration(
                                  color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                                  borderRadius: BorderRadius.circular(18),
                                ),
                                child: Icon(
                                  Icons.arrow_upward_rounded,
                                  color: _dark ? kTealGlow : kTeal,
                                  size: 28,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Tap to choose your discharge PDF',
                                style: TextStyle(
                                  fontSize: 12.5,
                                  color: _dark ? kTextHintDark : kTextSecondaryLight,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'PDF format · Up to 200MB',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: _dark ? kTextHintDark : kTextHintLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                        ),
                      ),
                    ),
                    if (_fileName != null) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                        decoration: BoxDecoration(
                          color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          '${_fileName!} · ${_kb(_bytes?.length ?? 0)}',
                          style: TextStyle(
                            fontSize: 12,
                            color: _dark ? kTealGlow : kTeal,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: ElevatedButton(
                        onPressed: _bytes == null
                            ? null
                            : () async {
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute<void>(
                                    builder: (_) => LoadingScreen(
                                      pdfBytes: _bytes!,
                                      fileName: _fileName ?? 'document.pdf',
                                    ),
                                  ),
                                );
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: kTeal,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          disabledBackgroundColor: kTeal.withValues(alpha: 0.4),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: const Text(
                          'Upload & Analyze',
                          style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Camera scan path (Sprint 2): no PDF needed - photograph
                    // the paper document; text is recognized on-device.
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: OutlinedButton.icon(
                        onPressed: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => const ScanScreen(),
                          ),
                        ),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: _dark ? kTealGlow : kTeal,
                          side: BorderSide(color: _dark ? kTealGlow : kTeal),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        icon: const Icon(Icons.photo_camera_outlined, size: 18),
                        label: const Text(
                          'No PDF? Scan the paper with your camera',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.lock_outline, size: 13, color: _dark ? kTextHintDark : kTextHintLight),
                        const SizedBox(width: 4),
                        Text(
                          'Private · Saved only on this phone, never shared',
                          style: TextStyle(
                            fontSize: 11,
                            color: _dark ? kTextHintDark : kTextHintLight,
                          ),
                        ),
                      ],
                    ),
                      const SizedBox(height: 20),
                      _JourneySection(dark: _dark),
                      _RecentDocuments(
                        // Keyed on the active person too: switching profile
                        // must re-filter the list, not just re-read it.
                        key: ValueKey('$_libraryVersion:${_activePerson?.id ?? 'all'}'),
                        dark: _dark,
                        onManage: _openPeople,
                        activePerson: _activePerson,
                      ),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _stepTiles() {
    const steps = [
      ('1', 'Your diagnosis', 'In words a friend would use'),
      ('2', 'Your medications', 'What each pill does and why'),
      ('3', 'Warning signs', 'When to call 911 vs your doctor'),
      ('4', 'Ask anything', 'AI chat from your document'),
    ];
    return steps.map((s) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: _dark
                ? kTeal.withValues(alpha: 0.15)
                : kTealPale.withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 24,
                height: 24,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _dark ? kTealGlow.withValues(alpha: 0.15) : kTealPale,
                  shape: BoxShape.circle,
                ),
                child: Text(
                  s.$1,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: _dark ? kTealLight : kTeal,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      s.$2,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      s.$3,
                      style: TextStyle(
                        fontSize: 11.5,
                        color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }

  static String _kb(int b) {
    if (b < 1024) return '$b B';
    return '${(b / 1024).toStringAsFixed(1)} KB';
  }
}

/// Recovery Journey + quests on the landing page. Hidden until the patient
/// has ANY progress - a brand-new user sees a clean landing, not an empty
/// progress card asking to be filled.
class _JourneySection extends StatefulWidget {
  const _JourneySection({required this.dark});

  final bool dark;

  @override
  State<_JourneySection> createState() => _JourneySectionState();
}

class _JourneySectionState extends State<_JourneySection> {
  Set<String>? _stars;
  GameStats? _stats;
  List<SavedDocument> _docs = const [];

  /// Which document's journey is showing; null until the list loads.
  /// Defaults to the newest document - the one the patient is living with.
  String? _selectedDocId;

  @override
  void initState() {
    super.initState();
    GameStore.load().then((s) {
      if (mounted) setState(() => _stats = s);
    });
    _loadDocsAndStars();
  }

  /// Load the saved-document list, run the one-time legacy-star migration
  /// (old global stars belong to the OLDEST document - the only one that
  /// existed when they were earned), then load stars for the selection.
  Future<void> _loadDocsAndStars() async {
    final docs = await DocumentStore.list(); // newest first
    if (docs.isNotEmpty) {
      await SectionStarStore.migrateLegacy(docs.last.id);
    }
    if (!mounted) return;
    final selected = _selectedDocId ?? (docs.isEmpty ? null : docs.first.id);
    final stars = selected == null
        ? <String>{}
        : await SectionStarStore.load(selected);
    if (!mounted) return;
    setState(() {
      _docs = docs;
      _selectedDocId = selected;
      _stars = stars;
    });
  }

  Future<void> _pickDoc(String docId) async {
    final stars = await SectionStarStore.load(docId);
    if (!mounted) return;
    setState(() {
      _selectedDocId = docId;
      _stars = stars;
    });
  }

  /// Landing-card puzzle entry: the landing page has no loaded document, so we
  /// reopen a saved analysis and launch the puzzle from its extraction.
  /// One saved document opens directly; several show a picker so the
  /// patient chooses which document to practice on (not just the newest).
  /// Zero API calls - the analysis is already on the phone.
  Future<void> _playPuzzle() async {
    final docs = await DocumentStore.list();
    if (docs.isEmpty || !mounted) return;
    var pickedId = docs.first.id;
    if (docs.length > 1) {
      final choice = await showModalBottomSheet<String>(
        context: context,
        showDragHandle: true,
        builder: (ctx) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(20, 4, 20, 8),
                child: Text('Practice which document?',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ),
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final d in docs)
                      ListTile(
                        leading: const Icon(Icons.description_outlined),
                        title: Text(d.diagnosis,
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(d.fileName,
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        onTap: () => Navigator.pop(ctx, d.id),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
      if (choice == null || !mounted) return;
      pickedId = choice;
    }
    final loaded = await DocumentStore.load(pickedId);
    if (loaded == null || !mounted) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Could not open your last document for the puzzle.'),
        ));
      }
      return;
    }
    final (result, _) = loaded;
    if (!mounted) return;
    await Navigator.push<void>(
      context,
      MaterialPageRoute<void>(
        builder: (_) => PuzzleScreen(
          extraction:
              (result['extraction'] as Map?)?.cast<String, dynamic>() ?? const {},
          diagnosisExplanation: '${result['diagnosis_explanation'] ?? ''}',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final stars = _stars;
    final stats = _stats;
    if (stars == null || stats == null) return const SizedBox.shrink();
    final hasProgress =
        stars.isNotEmpty || stats.xp > 0 || stats.quizzesCompleted > 0;
    if (!hasProgress) return const SizedBox.shrink();
    final dark = widget.dark;
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        children: [
          RecoveryJourneyCard(
            stars: stars,
            stats: stats,
            dark: dark,
            // Reading stars and quests are per-document; with more than one
            // saved analysis the patient picks which journey to look at.
            docPicker: _docs.length > 1
                ? _JourneyDocPicker(
                    docs: _docs,
                    selectedId: _selectedDocId,
                    dark: dark,
                    onPick: _pickDoc,
                  )
                : null,
          ),
          if (_docs.isNotEmpty) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: dark ? kTealGlow : kTeal,
                  side: BorderSide(color: dark ? kTealGlow : kTeal),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: _playPuzzle,
                icon: const Icon(Icons.extension_outlined, size: 18),
                label: const Text('Play the medicine puzzle'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Dropdown naming which saved document's journey the card is showing.
/// Rendered by the journey card under its title; only exists when the
/// patient has more than one saved analysis.
class _JourneyDocPicker extends StatelessWidget {
  const _JourneyDocPicker({
    required this.docs,
    required this.selectedId,
    required this.dark,
    required this.onPick,
  });

  final List<SavedDocument> docs;
  final String? selectedId;
  final bool dark;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonHideUnderline(
      child: DropdownButton<String>(
        value: selectedId,
        isExpanded: true,
        isDense: true,
        icon: Icon(Icons.keyboard_arrow_down_rounded,
            size: 18, color: dark ? kTealGlow : kTeal),
        style: TextStyle(
          fontSize: 12.5,
          fontWeight: FontWeight.w600,
          color: dark ? kTextPrimaryDark : kTextPrimaryLight,
        ),
        dropdownColor: dark ? kCardDark : kSurfaceLight,
        onChanged: (id) {
          if (id != null) onPick(id);
        },
        items: [
          for (final d in docs)
            DropdownMenuItem(
              value: d.id,
              child: Text(
                d.diagnosis.isEmpty ? d.fileName : d.diagnosis,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
        ],
      ),
    );
  }
}

/// On-device library (decision D-6): past analyses reopen instantly from
/// phone storage - no re-upload, no pipeline quota. Long-press to delete.
class _RecentDocuments extends StatefulWidget {
  const _RecentDocuments({
    super.key,
    required this.dark,
    required this.onManage,
    required this.activePerson,
  });

  final bool dark;

  /// Opens the people library. Passed down so this widget owns no navigation.
  final VoidCallback onManage;

  /// Whose documents to show. Null is the built-in "All" view, which shows
  /// every document including unassigned ones.
  final Person? activePerson;

  @override
  State<_RecentDocuments> createState() => _RecentDocumentsState();
}

class _RecentDocumentsState extends State<_RecentDocuments> {
  List<SavedDocument> _docs = const [];
  List<Person> _people = const [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final all = await DocumentStore.list();
    final people = await PersonStore.list();
    final active = widget.activePerson;
    // "All" shows everything, including unassigned. A named profile shows only
    // that person's documents - seeing a relative's medications while you
    // believe you are looking at your own is the mix-up profiles exist to
    // prevent.
    final docs = active == null
        ? all
        : all.where((d) => d.personId == active.id).toList();
    if (mounted) {
      setState(() {
        _docs = docs;
        _people = people;
      });
    }
  }

  Future<void> _open(SavedDocument doc) async {
    final loaded = await DocumentStore.load(doc.id);
    if (loaded == null || !mounted) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open that document.')),
        );
      }
      return;
    }
    final (result, pdf) = loaded;
    // A library reopen is NOT the live scan session: clear any in-memory
    // scan pages so the "add more pages" affordance cannot mix documents.
    context.read<DischargeProvider>().scanPages.clear();
    ScanSessionStore.clear();
    // Setting the provider result flips _HomeGate straight to the results
    // screen - same path a fresh analysis takes, zero API calls.
    context.read<DischargeProvider>().setResult(
          result,
          pdfBytes: pdf,
          fileName: doc.fileName,
          docId: doc.id,
        );
  }

  Future<void> _confirmDelete(SavedDocument doc) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this document?'),
        content: Text('"${doc.fileName}" will be removed from this phone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: kMedDiscontinued),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (yes == true) {
      await DocumentStore.delete(doc.id);
      await _refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final dark = widget.dark;
    // With profile filtering, an empty list is no longer only "nothing saved
    // yet" - it can mean "nothing saved for THIS person", which silently
    // renders as a blank space and reads like the documents were lost.
    if (_docs.isEmpty) {
      if (widget.activePerson == null) return const SizedBox.shrink();
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: dark ? kSurfaceDark : kSurfaceLight,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: dark ? kBorderDark : kBorderLight),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'No documents for ${widget.activePerson!.name} yet',
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Upload one above, or file an existing document under them.',
              style: TextStyle(
                fontSize: 13,
                height: 1.5,
                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
              ),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: widget.onManage,
              icon: const Icon(Icons.library_add_outlined, size: 18),
              label: const Text('File an existing document'),
              style: OutlinedButton.styleFrom(
                foregroundColor: dark ? kTealGlow : kTeal,
                side: BorderSide(color: dark ? kBorderDark : kBorderLight),
              ),
            ),
          ],
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                widget.activePerson == null
                    ? 'ALL SAVED DOCUMENTS'
                    : '${widget.activePerson!.name.toUpperCase()}\'S DOCUMENTS',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.6,
                  color: dark ? kTealGlow : kTeal,
                ),
              ),
            ),
            TextButton(
              onPressed: widget.onManage,
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Text(
                'Manage',
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: dark ? kTealGlow : kTeal,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        for (final doc in _docs)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Material(
              color: dark ? kCardDark : kSurfaceLight,
              borderRadius: BorderRadius.circular(14),
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => _open(doc),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 4, 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: (dark ? kTealGlow : kTeal).withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          doc.hasPdf
                              ? Icons.picture_as_pdf_outlined
                              : Icons.document_scanner_outlined,
                          size: 20,
                          color: dark ? kTealGlow : kTeal,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              doc.diagnosis.isEmpty ? doc.fileName : doc.diagnosis,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w700,
                                height: 1.3,
                                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                              ),
                            ),
                            const SizedBox(height: 5),
                            // Whose document, and when. The person chip is the
                            // point of the redesign: with one phone holding
                            // several family members' summaries, the owner has
                            // to be readable without opening anything.
                            Wrap(
                              spacing: 6,
                              runSpacing: 4,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                _OwnerChip(
                                  name: _ownerName(doc),
                                  known: _people.any((p) => p.id == doc.personId),
                                  dark: dark,
                                ),
                                Text(
                                  _friendlyDate(doc.savedAt),
                                  style: TextStyle(
                                    fontSize: 11.5,
                                    color: dark
                                        ? kTextSecondaryDark
                                        : kTextSecondaryLight,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      // Explicit overflow menu. The previous design hid delete
                      // behind a long press, which nobody discovers and which
                      // is a hostile gesture for a destructive action.
                      PopupMenuButton<String>(
                        icon: Icon(Icons.more_vert,
                            size: 20,
                            color: dark ? kTextSecondaryDark : kTextSecondaryLight),
                        onSelected: (choice) {
                          if (choice == 'open') _open(doc);
                          if (choice == 'move') _moveDoc(doc);
                          if (choice == 'delete') _confirmDelete(doc);
                        },
                        itemBuilder: (_) => [
                          const PopupMenuItem(
                            value: 'open',
                            child: ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              leading: Icon(Icons.open_in_new, size: 20),
                              title: Text('Open'),
                            ),
                          ),
                          const PopupMenuItem(
                            value: 'move',
                            child: ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              leading: Icon(Icons.drive_file_move_outline, size: 20),
                              title: Text('Move to person'),
                            ),
                          ),
                          const PopupMenuItem(
                            value: 'delete',
                            child: ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              leading: Icon(Icons.delete_outline,
                                  size: 20, color: kMedDiscontinued),
                              title: Text('Delete',
                                  style: TextStyle(color: kMedDiscontinued)),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        Text(
          'Stored only on this phone',
          style: TextStyle(
            fontSize: 10.5,
            color: dark ? kTextHintDark : kTextHintLight,
          ),
        ),
      ],
    );
  }

  /// Display name for a document's owner, including the two cases where the
  /// stored person id no longer resolves.
  String _ownerName(SavedDocument doc) {
    if (doc.personId == null) return 'Unassigned';
    for (final p in _people) {
      if (p.id == doc.personId) return p.name;
    }
    return 'Unassigned';
  }

  /// Move one document to another person, or to Unassigned.
  Future<void> _moveDoc(SavedDocument doc) async {
    if (_people.isEmpty) {
      widget.onManage();
      return;
    }
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
            ..._people.map((p) => ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(p.name),
                  subtitle: Text(p.relationship.label),
                  onTap: () => Navigator.pop(ctx, p.id),
                )),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.folder_open),
              title: const Text('Unassigned'),
              onTap: () => Navigator.pop(ctx, ''),
            ),
          ],
        ),
      ),
    );
    if (target == null) return;
    // Same rule as the people screen: taking a document off one person and
    // giving it to another is a move, so confirm when it already has an owner.
    if (doc.personId != null && doc.personId != target && mounted) {
      final fromName = _ownerName(doc);
      final toName = target.isEmpty
          ? 'Unassigned'
          : _people.firstWhere((p) => p.id == target).name;
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Move this document?'),
          content: Text(
            'It is filed under $fromName. Moving it to $toName removes it '
            'from there.',
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
    await DocumentStore.assignPerson(doc.id, target.isEmpty ? null : target);
    await _refresh();
  }

  static String _friendlyDate(DateTime d) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final that = DateTime(d.year, d.month, d.day);
    if (that == today) return 'today';
    if (that == today.subtract(const Duration(days: 1))) return 'yesterday';
    return '${d.month}/${d.day}/${d.year}';
  }
}

class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({
    required this.color,
    this.strokeWidth = 1.5,
    this.radius = 12,
  });

  final Color color;
  final double strokeWidth;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(
      Rect.fromLTWH(strokeWidth / 2, strokeWidth / 2, size.width - strokeWidth, size.height - strokeWidth),
      Radius.circular(radius),
    );
    final path = Path()..addRRect(r);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    _drawDashedPath(canvas, path, paint, dash: 6, gap: 4);
  }

  void _drawDashedPath(Canvas canvas, Path path, Paint paint, {required double dash, required double gap}) {
    for (final metric in path.computeMetrics()) {
      double d = 0;
      while (d < metric.length) {
        final next = d + dash;
        final extract = metric.extractPath(d, next.clamp(0, metric.length));
        canvas.drawPath(extract, paint);
        d = next + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedBorderPainter oldDelegate) {
    return oldDelegate.color != color ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.radius != radius;
  }
}

/// Small chip naming who a saved document belongs to.
///
/// Unassigned is styled differently rather than hidden: it is a real state
/// with a real fix (Move to person), and quietly blending it in would leave
/// documents unfiled forever.
class _OwnerChip extends StatelessWidget {
  const _OwnerChip({
    required this.name,
    required this.known,
    required this.dark,
  });

  final String name;

  /// False for the Unassigned bucket, including a document whose person was
  /// deleted after it was filed.
  final bool known;

  final bool dark;

  @override
  Widget build(BuildContext context) {
    final color = known ? (dark ? kTealGlow : kTeal) : kMedChanged;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(known ? Icons.person : Icons.help_outline, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            name,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
