import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

/// Shows the first few items of a list and hides the rest behind one tap.
///
/// CDC plain-language guidance for patient materials notes that readers with
/// limited health literacy "may not comfortably process more than 5 pieces of
/// information at a time". Real discharge documents routinely exceed that:
/// the MTSamples corpus reaches 16 medications on a single summary, which
/// renders as an unbroken wall of cards.
///
/// Capping the VISIBLE COUNT rather than the word count matters here. A flat
/// per-tab word budget would truncate a patient's actual prescriptions, which
/// is unacceptable - every medicine has to remain reachable. This hides
/// nothing permanently; it only decides what is on screen first.
class CappedList extends StatefulWidget {
  const CappedList({
    super.key,
    required this.children,
    required this.itemNoun,
    this.initialCount = 5,
  });

  /// The full list. Every item stays reachable behind the toggle.
  final List<Widget> children;

  /// Plural noun for the button, e.g. "medicines", "warning signs".
  final String itemNoun;

  /// How many to show before collapsing. Defaults to the CDC figure of 5.
  final int initialCount;

  @override
  State<CappedList> createState() => _CappedListState();
}

class _CappedListState extends State<CappedList> {
  bool _showAll = false;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final total = widget.children.length;

    // Below the threshold there is nothing to hide, and a toggle over a short
    // list is just another control to read.
    if (total <= widget.initialCount) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: widget.children,
      );
    }

    final hidden = total - widget.initialCount;
    final visible =
        _showAll ? widget.children : widget.children.take(widget.initialCount).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ...visible,
        const SizedBox(height: 4),
        // Full-width tap target: this is read one-handed, often by someone
        // tired or in pain.
        SizedBox(
          width: double.infinity,
          child: TextButton.icon(
            onPressed: () => setState(() => _showAll = !_showAll),
            icon: Icon(
              _showAll ? Icons.expand_less : Icons.expand_more,
              size: 20,
              color: dark ? kTealGlow : kTeal,
            ),
            label: Text(
              _showAll
                  ? 'Show fewer'
                  : 'Show all $total ${widget.itemNoun} ($hidden more)',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: dark ? kTealGlow : kTeal,
              ),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor:
                  dark ? kTeal.withValues(alpha: 0.12) : kTealPale.withValues(alpha: 0.5),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
}
