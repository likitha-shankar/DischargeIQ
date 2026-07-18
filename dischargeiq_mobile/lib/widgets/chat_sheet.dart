/// widgets/chat_sheet.dart
///
/// Grounded chat UI (the "Ask" button on results): a tall draggable sheet
/// with proper message bubbles, starter question chips, a typing indicator,
/// and patient-friendly failure copy. Answers come only from the uploaded
/// document - the header says so, and the backend enforces it.
/// Extracted from results_screen.dart (500-line rule) and rebuilt for the
/// Task 3.5 polish pass.
library;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/screens/results_screen.dart' show PatientText;
import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:flutter/material.dart';

/// Starter questions - shown until the first message is sent. Wording
/// matches the five comprehension domains so answers are always in-document.
const _kStarterQuestions = [
  'What is my main condition?',
  'How do I take my medicines?',
  'When should I call the doctor?',
  'What should I avoid doing?',
];

/// Open the chat sheet for one analysis result.
Future<void> showChatSheet(BuildContext context, Map<String, dynamic> result) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _ChatSheet(result: result),
  );
}

class _ChatMessage {
  const _ChatMessage({
    required this.fromPatient,
    required this.text,
    this.failed = false,
    this.retryQuestion,
  });

  final bool fromPatient;
  final String text;
  final bool failed;

  /// The question that produced a failed answer - powers the Retry chip.
  final String? retryQuestion;
}

class _ChatSheet extends StatefulWidget {
  const _ChatSheet({required this.result});

  final Map<String, dynamic> result;

  @override
  State<_ChatSheet> createState() => _ChatSheetState();
}

/// Chat history per session, kept for the app's lifetime so closing and
/// reopening the sheet does not wipe the conversation. In-memory only -
/// chat content never touches disk or server storage.
final Map<String, List<_ChatMessage>> _chatHistoryBySession = {};

class _ChatSheetState extends State<_ChatSheet> {
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  late final List<_ChatMessage> _messages =
      _chatHistoryBySession.putIfAbsent(_sessionId, () => []);
  bool _sending = false;

  bool get _dark => Theme.of(context).brightness == Brightness.dark;

  /// One stable session per result so backend chat history joins up with
  /// the analyze session (the old sheet minted a new id per message).
  String get _sessionId =>
      '${widget.result['pdf_session_id'] ?? DateTime.now().millisecondsSinceEpoch}';

  @override
  void initState() {
    super.initState();
    // Reopened with prior history: land at the latest message.
    if (_messages.isNotEmpty) _autoscroll();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send(String raw) async {
    final q = raw.trim();
    if (q.isEmpty || _sending) return;
    setState(() {
      _sending = true;
      _messages.add(_ChatMessage(fromPatient: true, text: q));
    });
    _ctrl.clear();
    _autoscroll();
    try {
      final streamedText = await _sendStreaming(q);
      if (!streamedText) await _sendBlocking(q);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatMessage(
          fromPatient: false,
          failed: true,
          retryQuestion: q,
          text: 'I could not answer just now. Your written summary in the '
              'tabs has the same information.',
        ));
      });
    } finally {
      if (mounted) setState(() => _sending = false);
      _autoscroll();
    }
  }

  /// Stream the answer live from /chat/stream, growing one assistant bubble
  /// as deltas arrive. Returns true when any answer text was shown; false
  /// signals the caller to retry via the blocking endpoint (which re-sends
  /// the full pipeline context for evicted sessions and older servers).
  Future<bool> _sendStreaming(String q) async {
    var bubbleIndex = -1;
    var text = '';
    try {
      await for (final event in ApiService()
          .chatStream(message: q, sessionId: _sessionId)) {
        if (!mounted) return true;
        if (event['delta'] is String) {
          text += event['delta'] as String;
        } else if (event['done'] == true) {
          // Final reply is the server-cleaned full text (grounding suffix
          // stripped) - replace the accumulated stream with it.
          text = '${event['reply'] ?? text}';
        } else if (event.containsKey('error')) {
          // Keep partial text if any was shown; otherwise let the caller
          // fall back to the blocking endpoint.
          if (bubbleIndex < 0) return false;
          continue;
        } else {
          continue;
        }
        setState(() {
          final bubble = _ChatMessage(fromPatient: false, text: text);
          if (bubbleIndex < 0) {
            _messages.add(bubble);
            bubbleIndex = _messages.length - 1;
          } else {
            _messages[bubbleIndex] = bubble;
          }
        });
        _autoscroll();
      }
      return bubbleIndex >= 0;
    } catch (_) {
      // Transport-level failure (409 no context, old server, network drop).
      // Partial text already shown is kept; nothing shown means retry.
      return bubbleIndex >= 0;
    }
  }

  /// Original non-streaming path - also the fallback when streaming yields
  /// nothing. Re-sends the full pipeline context so it works even when the
  /// server's per-session cache was evicted.
  Future<void> _sendBlocking(String q) async {
    final data = await ApiService().chat(
      message: q,
      sessionId: _sessionId,
      pipelineContext: widget.result,
    );
    if (!mounted) return;
    setState(() {
      _messages.add(_ChatMessage(fromPatient: false, text: '${data['reply'] ?? ''}'));
    });
  }

  void _autoscroll() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final dark = _dark;
    return DraggableScrollableSheet(
      initialChildSize: 0.78,
      minChildSize: 0.45,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, sheetScroll) => Container(
        decoration: BoxDecoration(
          color: dark ? kSurfaceDark : kBgLight,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Column(
          children: [
            const SizedBox(height: 8),
            Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: dark ? Colors.white24 : Colors.black12,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            _header(dark),
            Divider(height: 1, color: dark ? kBorderDark : kBorderLight),
            Expanded(
              child: _messages.isEmpty ? _starters(dark) : _messageList(dark),
            ),
            _typingRow(dark),
            _inputBar(dark, context),
          ],
        ),
      ),
    );
  }

  Widget _header(bool dark) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 17,
            backgroundColor: dark ? kTeal : kTealPale,
            child: Icon(Icons.chat_bubble_outline,
                size: 18, color: dark ? kTealGlow : kTeal),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Ask about your discharge',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                  ),
                ),
                Text(
                  'Answers come only from your document',
                  style: TextStyle(
                    fontSize: 11,
                    color: dark ? kTextSecondaryDark : kTextSecondaryLight,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Close',
            icon: const Icon(Icons.close, size: 20),
            color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }

  /// Empty state: gentle prompt + one-tap starter questions.
  Widget _starters(bool dark) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'No question is too small. Try one of these:',
            style: TextStyle(
              fontSize: 13.5,
              color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final q in _kStarterQuestions)
                ActionChip(
                  label: Text(q, style: const TextStyle(fontSize: 13)),
                  labelPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  backgroundColor: dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                  side: BorderSide(
                    color: dark ? kTealGlow.withValues(alpha: 0.3) : kTealGlow,
                    width: 0.5,
                  ),
                  labelStyle: TextStyle(color: dark ? kTealGlow : kTeal),
                  onPressed: _sending ? null : () => _send(q),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _messageList(bool dark) {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
      itemCount: _messages.length,
      itemBuilder: (c, i) {
        final m = _messages[i];
        final bubbleColor = m.fromPatient
            ? kTeal
            : m.failed
                ? (dark ? kTier2.withValues(alpha: 0.2) : kTier2Bg)
                // Assistant bubbles: tonal teal tint, no border (2026 revamp).
                : (dark ? kCardDark : kTealPale.withValues(alpha: 0.55));
        final textColor = m.fromPatient
            ? Colors.white
            : m.failed
                ? (dark ? const Color(0xFFF5C97B) : const Color(0xFF92600A))
                : (dark ? kTextPrimaryDark : kTextPrimaryLight);
        return Align(
          alignment: m.fromPatient ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78),
            decoration: BoxDecoration(
              color: bubbleColor,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(20),
                topRight: const Radius.circular(20),
                bottomLeft: Radius.circular(m.fromPatient ? 20 : 6),
                bottomRight: Radius.circular(m.fromPatient ? 6 : 20),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (m.fromPatient || m.failed)
                  SelectableText(
                    m.text,
                    style:
                        TextStyle(fontSize: 14.5, height: 1.4, color: textColor),
                  )
                else
                  // Assistant answers go through the shared patient renderer
                  // so any markdown the model emits looks intentional.
                  PatientText(text: m.text),
                if (m.failed && m.retryQuestion != null) ...[
                  const SizedBox(height: 8),
                  ActionChip(
                    avatar: Icon(Icons.refresh,
                        size: 16, color: dark ? kTealGlow : kTeal),
                    label: const Text('Try again'),
                    labelStyle: TextStyle(
                        fontSize: 12.5, color: dark ? kTealGlow : kTeal),
                    backgroundColor:
                        dark ? kTeal.withValues(alpha: 0.25) : kTealPale,
                    side: BorderSide.none,
                    onPressed: _sending ? null : () => _send(m.retryQuestion!),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _typingRow(bool dark) {
    if (!_sending) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(left: 20, bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: dark ? kTealGlow : kTeal,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            'Reading your document...',
            style: TextStyle(
              fontSize: 12,
              color: dark ? kTextSecondaryDark : kTextSecondaryLight,
            ),
          ),
        ],
      ),
    );
  }

  Widget _inputBar(bool dark, BuildContext context) {
    return Container(
      padding: EdgeInsets.fromLTRB(
          12, 8, 8, 8 + MediaQuery.of(context).viewInsets.bottom),
      // Borderless floating input row - the pill field is its own surface.
      color: dark ? kSurfaceDark : kBgLight,
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _ctrl,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              style: TextStyle(
                  fontSize: 14.5,
                  color: dark ? kTextPrimaryDark : kTextPrimaryLight),
              decoration: InputDecoration(
                hintText: 'Ask in plain language...',
                hintStyle: TextStyle(
                    fontSize: 14,
                    color: dark ? kTextHintDark : kTextHintLight),
                filled: true,
                fillColor:
                    dark ? kCardDark : kTealPale.withValues(alpha: 0.45),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(22),
                  borderSide: BorderSide.none,
                ),
              ),
              onSubmitted: _send,
            ),
          ),
          const SizedBox(width: 8),
          // 48dp circular send target.
          SizedBox(
            width: 46,
            height: 46,
            child: IconButton.filled(
              style: IconButton.styleFrom(
                backgroundColor: kTeal,
                disabledBackgroundColor: kTeal.withValues(alpha: 0.35),
              ),
              tooltip: 'Send',
              onPressed: _sending ? null : () => _send(_ctrl.text),
              icon: const Icon(Icons.arrow_upward_rounded,
                  color: Colors.white, size: 22),
            ),
          ),
        ],
      ),
    );
  }
}
