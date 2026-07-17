import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/providers/discharge_provider.dart';
import 'package:dischargeiq_mobile/providers/theme_provider.dart';
import 'package:dischargeiq_mobile/screens/loading_screen.dart';
import 'package:dischargeiq_mobile/screens/puzzle_screen.dart';
import 'package:dischargeiq_mobile/services/document_store.dart';
import 'package:dischargeiq_mobile/services/game_store.dart';
import 'package:dischargeiq_mobile/services/scan_session_store.dart';
import 'package:dischargeiq_mobile/widgets/garden_widgets.dart';
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

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

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
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'DischargeIQ',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w600,
                            color: _dark ? kTealGlow : kTeal,
                          ),
                        ),
                        Text(
                          'Patient education only',
                          style: TextStyle(
                            fontSize: 10.5,
                            color: _dark ? kTextSecondaryDark : kTextSecondaryLight,
                          ),
                        ),
                      ],
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
                          fontSize: 22,
                          fontWeight: FontWeight.w500,
                          color: _dark ? kTextPrimaryDark : kTextPrimaryLight,
                          height: 1.25,
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
                          radius: 12,
                        ),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: _dark ? kTeal.withValues(alpha: 0.12) : kSurfaceLight,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            children: [
                              Container(
                                width: 40,
                                height: 40,
                                decoration: BoxDecoration(
                                  color: _dark ? kTeal.withValues(alpha: 0.3) : kTealPale,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Icon(
                                  Icons.arrow_upward_rounded,
                                  color: _dark ? kTealGlow : kTeal,
                                  size: 22,
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
                      height: 52,
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
                          disabledBackgroundColor: kTeal.withValues(alpha: 0.4),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text(
                          'Upload & Analyze',
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
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
                            borderRadius: BorderRadius.circular(12),
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
                      _GardenSection(dark: _dark),
                      _RecentDocuments(dark: _dark),
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
            color: _dark ? kTeal.withValues(alpha: 0.15) : kSurfaceLight,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: _dark ? kTealMid.withValues(alpha: 0.2) : kBorderLight,
              width: 0.5,
            ),
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

/// Recovery Garden + quests on the landing page. Hidden until the patient
/// has ANY progress - a brand-new user sees a clean landing, not an empty
/// garden asking to be filled.
class _GardenSection extends StatefulWidget {
  const _GardenSection({required this.dark});

  final bool dark;

  @override
  State<_GardenSection> createState() => _GardenSectionState();
}

class _GardenSectionState extends State<_GardenSection> {
  Set<String>? _stars;
  GameStats? _stats;
  bool _hasSavedDoc = false;

  @override
  void initState() {
    super.initState();
    SectionStarStore.load().then((s) {
      if (mounted) setState(() => _stars = s);
    });
    GameStore.load().then((s) {
      if (mounted) setState(() => _stats = s);
    });
    DocumentStore.list().then((docs) {
      if (mounted) setState(() => _hasSavedDoc = docs.isNotEmpty);
    });
  }

  /// Landing-garden puzzle entry: the garden has no loaded document, so we
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
          RecoveryGardenCard(stars: stars, stats: stats, dark: dark),
          if (_hasSavedDoc) ...[
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

/// On-device library (decision D-6): past analyses reopen instantly from
/// phone storage - no re-upload, no pipeline quota. Long-press to delete.
class _RecentDocuments extends StatefulWidget {
  const _RecentDocuments({required this.dark});

  final bool dark;

  @override
  State<_RecentDocuments> createState() => _RecentDocumentsState();
}

class _RecentDocumentsState extends State<_RecentDocuments> {
  List<SavedDocument> _docs = const [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final docs = await DocumentStore.list();
    if (mounted) setState(() => _docs = docs);
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
    if (_docs.isEmpty) return const SizedBox.shrink();
    final dark = widget.dark;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'YOUR SAVED DOCUMENTS',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.6,
            color: dark ? kTealGlow : kTeal,
          ),
        ),
        const SizedBox(height: 8),
        for (final doc in _docs)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Material(
              color: dark ? kCardDark : kSurfaceLight,
              borderRadius: BorderRadius.circular(10),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _open(doc),
                onLongPress: () => _confirmDelete(doc),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  child: Row(
                    children: [
                      Icon(
                        doc.hasPdf
                            ? Icons.picture_as_pdf_outlined
                            : Icons.document_scanner_outlined,
                        size: 20,
                        color: dark ? kTealGlow : kTeal,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              doc.diagnosis.isEmpty ? doc.fileName : doc.diagnosis,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                              ),
                            ),
                            Text(
                              '${doc.fileName} · ${_friendlyDate(doc.savedAt)}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 11,
                                color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right,
                          size: 18,
                          color: dark ? kTextHintDark : kTextHintLight),
                    ],
                  ),
                ),
              ),
            ),
          ),
        Text(
          'Tap to reopen · Hold to delete · Stored only on this phone',
          style: TextStyle(
            fontSize: 10.5,
            color: dark ? kTextHintDark : kTextHintLight,
          ),
        ),
      ],
    );
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
