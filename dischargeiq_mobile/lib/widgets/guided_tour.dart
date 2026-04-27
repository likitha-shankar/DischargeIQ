import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

/// Global keys for spotlight targets — attach to widgets on [ResultsScreen].
class TourKeys {
  static final GlobalKey tabBar = GlobalKey(debugLabel: 'tourTabBar');
  static final GlobalKey diagnosis = GlobalKey(debugLabel: 'tourDiagnosis');
  static final GlobalKey medications = GlobalKey(debugLabel: 'tourMedications');
  static final GlobalKey appointments = GlobalKey(debugLabel: 'tourAppointments');
  static final GlobalKey warnings = GlobalKey(debugLabel: 'tourWarnings');
  static final GlobalKey dischargeCheck = GlobalKey(debugLabel: 'tourDischargeCheck');
  static final GlobalKey chat = GlobalKey(debugLabel: 'tourChat');
}

class _TourStep {
  const _TourStep({
    required this.title,
    required this.body,
    this.tabIndex,
    required this.targetKey,
  });

  final String title;
  final String body;
  final int? tabIndex;
  final GlobalKey targetKey;
}

final List<_TourStep> _kSteps = [
  _TourStep(
    title: 'Swipe between sections',
    body:
        'These tabs organize everything from your discharge — start with What happened.',
    tabIndex: 0,
    targetKey: TourKeys.tabBar,
  ),
  _TourStep(
    title: 'Your diagnosis, simplified',
    body:
        'Plain language explanation of what happened during your hospital stay. No medical jargon.',
    tabIndex: 0,
    targetKey: TourKeys.diagnosis,
  ),
  _TourStep(
    title: 'Every medication explained',
    body:
        'Tap any medication to see why you were prescribed it, linked to your specific diagnosis.',
    tabIndex: 1,
    targetKey: TourKeys.medications,
  ),
  _TourStep(
    title: 'Three-tier warning guide',
    body:
        'Know exactly when to call 911, go to the ER, or just call your doctor.',
    tabIndex: 3,
    targetKey: TourKeys.warnings,
  ),
  _TourStep(
    title: 'Discharge quality check',
    body:
        'AI simulates a confused patient to find gaps in your discharge doc — unique to DischargeIQ.',
    tabIndex: 5,
    targetKey: TourKeys.dischargeCheck,
  ),
  _TourStep(
    title: 'Ask anything',
    body:
        'Type any question in plain language. Answers come only from your document — nothing made up.',
    tabIndex: null,
    targetKey: TourKeys.chat,
  ),
];

/// Dim overlay with rounded-rect cutout ([CustomPainter] draws full-screen dim
/// minus an eroded rounded rectangle so the target stays visually clear).
class SpotlightPainter extends CustomPainter {
  SpotlightPainter({required this.hole, required this.dimColor});

  final RRect hole;
  final Color dimColor;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Path()..addRect(Rect.fromLTWH(0, 0, size.width, size.height));
    final cut = Path()..addRRect(hole);
    final overlay = Path.combine(PathOperation.difference, background, cut);
    canvas.drawPath(overlay, Paint()..color = dimColor);
    canvas.drawRRect(
      hole,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = kTealGlow,
    );
  }

  @override
  bool shouldRepaint(covariant SpotlightPainter oldDelegate) {
    return oldDelegate.hole != hole || oldDelegate.dimColor != dimColor;
  }
}

/// Shows the 6-step overlay; call from [ResultsScreen] after first analysis.
void showGuidedTourOverlay({
  required BuildContext context,
  required TabController tabController,
  required VoidCallback onFinished,
}) {
  late OverlayEntry entry;
  entry = OverlayEntry(
    builder: (ctx) => _GuidedTourOverlay(
      tabController: tabController,
      onClose: () {
        entry.remove();
        onFinished();
      },
    ),
  );
  Overlay.of(context).insert(entry);
}

class _GuidedTourOverlay extends StatefulWidget {
  const _GuidedTourOverlay({
    required this.tabController,
    required this.onClose,
  });

  final TabController tabController;
  final VoidCallback onClose;

  @override
  State<_GuidedTourOverlay> createState() => _GuidedTourOverlayState();
}

class _GuidedTourOverlayState extends State<_GuidedTourOverlay> {
  int _step = 0;

  static const _dim = Color(0xB804342C);

  Future<void> _applyTabForStep(int stepIndex) async {
    final tab = _kSteps[stepIndex].tabIndex;
    if (tab != null && widget.tabController.index != tab) {
      widget.tabController.animateTo(tab);
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _applyTabForStep(0));
  }

  RRect _holeFor(Size overlaySize) {
    const pad = 8.0;
    final key = _kSteps[_step].targetKey;
    final ctx = key.currentContext;
    if (ctx == null) {
      final w = overlaySize.width;
      final h = overlaySize.height;
      return RRect.fromRectAndRadius(
        Rect.fromLTWH(16, h * 0.25, w - 32, h * 0.35),
        const Radius.circular(12),
      );
    }
    final box = ctx.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) {
      return RRect.fromRectAndRadius(
        Rect.fromLTWH(16, 100, overlaySize.width - 32, 120),
        const Radius.circular(12),
      );
    }
    final topLeft = box.localToGlobal(Offset.zero);
    final rect = Rect.fromLTWH(
      topLeft.dx - pad,
      topLeft.dy - pad,
      box.size.width + pad * 2,
      box.size.height + pad * 2,
    );
    return RRect.fromRectAndRadius(rect, const Radius.circular(12));
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      type: MaterialType.transparency,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          final hole = _holeFor(size);
          final holeCenter = hole.center;
          final tooltipBelow = holeCenter.dy < size.height / 2;

          return Stack(
            children: [
              Positioned.fill(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () {},
                  child: CustomPaint(
                    painter: SpotlightPainter(hole: hole, dimColor: _dim),
                  ),
                ),
              ),
              Positioned(
                left: 16,
                right: 16,
                top: tooltipBelow ? hole.bottom + 16 : null,
                bottom: tooltipBelow ? null : size.height - hole.top + 24,
                child: Center(
                  child: _TourTooltipCard(
                    stepIndex: _step,
                    title: _kSteps[_step].title,
                    body: _kSteps[_step].body,
                    onSkip: widget.onClose,
                    onNext: () async {
                      if (_step >= _kSteps.length - 1) {
                        widget.onClose();
                      } else {
                        setState(() => _step++);
                        await _applyTabForStep(_step);
                      }
                    },
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _TourTooltipCard extends StatelessWidget {
  const _TourTooltipCard({
    required this.stepIndex,
    required this.title,
    required this.body,
    required this.onSkip,
    required this.onNext,
  });

  final int stepIndex;
  final String title;
  final String body;
  final VoidCallback onSkip;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final last = stepIndex >= _kSteps.length - 1;
    return Container(
      width: 240,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: kTealGlow),
        boxShadow: const [
          BoxShadow(
            color: Color(0x3304342C),
            blurRadius: 32,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Step ${stepIndex + 1} of 6',
            style: const TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w500,
              color: kTeal,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: kTextPrimaryLight,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            body,
            style: const TextStyle(
              fontSize: 11,
              height: 1.5,
              color: kTextSecondaryLight,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: Row(
                  children: List.generate(6, (i) {
                    return Container(
                      width: 7,
                      height: 7,
                      margin: const EdgeInsets.only(right: 4),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i == stepIndex ? kTeal : kTealPale,
                      ),
                    );
                  }),
                ),
              ),
              TextButton(
                onPressed: onSkip,
                style: TextButton.styleFrom(
                  foregroundColor: kTextHintLight,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text('Skip', style: TextStyle(fontSize: 10)),
              ),
              ElevatedButton(
                onPressed: onNext,
                style: ElevatedButton.styleFrom(
                  backgroundColor: kTeal,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: Text(
                  last ? 'Finish ✓' : 'Next →',
                  style: const TextStyle(fontSize: 10),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
