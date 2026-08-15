// Part of results_screen.dart - split for the 500-line rule.
// Same library: private classes and library imports are shared.
part of 'results_screen.dart';

/// Morning weight, the single number that predicts readmission in heart
/// failure. Local-only, and it says so.
class _WeightCard extends StatelessWidget {
  const _WeightCard({
    required this.weights,
    required this.change,
    required this.onLog,
  });

  final List<WeightEntry> weights;
  final double? change;
  final VoidCallback onLog;

  @override
  Widget build(BuildContext context) {
    final c = SectionColors.of(context);
    final recent = weights.take(7).toList().reversed.toList();

    return SectionCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: SectionMiniLabel('Morning weight')),
              if (change != null)
                Text(
                  '${change! >= 0 ? '+' : ''}${change!.toStringAsFixed(1)} lb',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: change! >= 3 ? sdWarn : c.accent,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (recent.isEmpty)
            Text(
              'Weigh yourself each morning, before breakfast, in the same '
              'clothes. Three pounds up in a day is the number to act on.',
              style: TextStyle(fontSize: 13, height: 1.55, color: c.textSub),
            )
          else ...[
            SizedBox(
              height: 46,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  for (var i = 0; i < recent.length; i++)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2.5),
                        child: Container(
                          height: _barHeight(recent, i),
                          decoration: BoxDecoration(
                            color: i == recent.length - 1
                                ? sdTeal
                                : const Color(0xFFC9E4D9),
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(4),
                              bottom: Radius.circular(2),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  recent.last.pounds.toStringAsFixed(1),
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    letterSpacing: -0.5,
                    color: c.text,
                  ),
                ),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    'lb today · ${recent.length} ${recent.length == 1 ? 'reading' : 'readings'} logged',
                    style: TextStyle(fontSize: 11.5, color: c.textMute),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            height: 44,
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: c.accent,
                side: BorderSide(color: c.accent),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(sdRadiusInner),
                ),
              ),
              onPressed: onLog,
              icon: const Icon(Icons.monitor_weight_outlined, size: 18),
              label: Text(
                recent.isEmpty ? 'Log your first weight' : "Log today's weight",
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.lock_outline, size: 13, color: c.textMute),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  'Kept on this phone only.',
                  style: TextStyle(fontSize: 10.5, color: c.textMute),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Scaled against the range in view so a 2 lb swing is visible, with a
  /// floor so a flat week does not render as nothing.
  static double _barHeight(List<WeightEntry> w, int i) {
    final vals = w.map((e) => e.pounds).toList();
    final lo = vals.reduce((a, b) => a < b ? a : b);
    final hi = vals.reduce((a, b) => a > b ? a : b);
    final span = (hi - lo).abs();
    if (span < 0.5) return 34;
    return 16 + ((vals[i] - lo) / span) * 28;
  }
}

class _WeightDialog extends StatefulWidget {
  const _WeightDialog();

  @override
  State<_WeightDialog> createState() => _WeightDialogState();
}

class _WeightDialogState extends State<_WeightDialog> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final v = double.tryParse(_controller.text.trim());
    if (v == null || v < 40 || v > 900) {
      setState(() => _error = 'Enter your weight in pounds, e.g. 176.4');
      return;
    }
    Navigator.pop(context, v);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text("Today's weight"),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _controller,
            autofocus: true,
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              suffixText: 'lb',
              errorText: _error,
              border: const OutlineInputBorder(),
            ),
            onSubmitted: (_) => _submit(),
          ),
          const SizedBox(height: 10),
          const Text(
            'Before breakfast, in the same clothes, on the same scale.',
            style: TextStyle(fontSize: 12, height: 1.45),
          ),
        ],
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}
