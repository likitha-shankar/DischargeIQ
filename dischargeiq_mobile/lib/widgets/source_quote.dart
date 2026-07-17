/// widgets/source_quote.dart
///
/// Source citation chip (trust feature, mobile parity with the web UI):
/// shows the verbatim passage of the discharge document a fact was extracted
/// from, straight from Agent 1's SourceSpan provenance (page + exact quote).
/// Collapsed by default - one quiet "From your document" row that expands to
/// the quote. Renders nothing when no span exists (Agent 1 never fabricates
/// provenance, so absence means "not traceable", and we show nothing rather
/// than pretend).
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/material.dart';

class SourceQuote extends StatefulWidget {
  const SourceQuote({super.key, required this.source});

  /// The SourceSpan map from the API: {'page': int, 'text': String}.
  final dynamic source;

  @override
  State<SourceQuote> createState() => _SourceQuoteState();
}

class _SourceQuoteState extends State<SourceQuote> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final src = widget.source;
    if (src is! Map) return const SizedBox.shrink();
    final text = '${src['text'] ?? ''}'.trim();
    if (text.isEmpty) return const SizedBox.shrink();
    final page = (src['page'] as num?)?.toInt();
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = dark ? kTealGlow : kTeal;

    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(6),
            onTap: () => setState(() => _open = !_open),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.format_quote_rounded, size: 14, color: accent),
                  const SizedBox(width: 4),
                  Text(
                    _open ? 'From your document' : 'See where this comes from',
                    style: TextStyle(fontSize: 11.5, color: accent),
                  ),
                  Icon(
                    _open ? Icons.expand_less : Icons.expand_more,
                    size: 14,
                    color: accent,
                  ),
                ],
              ),
            ),
          ),
          if (_open)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(top: 2),
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
              decoration: BoxDecoration(
                color: dark ? kTeal.withValues(alpha: 0.15) : kTealPale.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(8),
                border: Border(
                  left: BorderSide(color: accent, width: 3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '"$text"',
                    style: TextStyle(
                      fontSize: 12.5,
                      height: 1.4,
                      fontStyle: FontStyle.italic,
                      color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                    ),
                  ),
                  if (page != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Page $page of your document',
                      style: TextStyle(
                        fontSize: 10.5,
                        color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                      ),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }
}
