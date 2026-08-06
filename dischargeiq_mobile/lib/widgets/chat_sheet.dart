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
import 'package:dischargeiq_mobile/services/read_aloud.dart';
import 'package:dischargeiq_mobile/services/voice_input.dart';
import 'package:dischargeiq_mobile/services/voice_intent.dart';
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
///
/// Returns the results-tab index the patient asked to have read out loud
/// ("read me my medications"), or null when they simply closed the sheet.
///
/// The tab arrives as the sheet's POP RESULT rather than through a callback
/// fired mid-dismiss: an earlier version popped from inside the sheet and
/// then invoked a callback, which left the modal barrier on screen as a black
/// overlay when the pop raced the sheet's own teardown. Letting the caller act
/// after the route has fully closed removes the race entirely.
Future<int?> showChatSheet(
  BuildContext context,
  Map<String, dynamic> result,
) {
  return showModalBottomSheet<int>(
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
    this.fromDocument,
    this.sourcePage,
  });

  final bool fromPatient;
  final String text;
  final bool failed;

  /// The question that produced a failed answer - powers the Retry chip.
  final String? retryQuestion;

  /// Server grounding verdict. True: answered from the patient's own
  /// document. False: general guidance the document did not contain. Null
  /// while streaming or on old servers - no badge is shown rather than a
  /// guessed one, because a wrong trust label is worse than none.
  final bool? fromDocument;

  /// Source page in the original PDF, when the server attributed one.
  final int? sourcePage;
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

  /// Microphone state. _micAvailable is null until the recognizer is probed,
  /// and the button stays hidden while unknown or unavailable - a mic that
  /// cannot work must never be offered.
  bool? _micAvailable;
  bool _listening = false;

  /// Read answers out loud as they arrive. Follows the app-wide read-aloud
  /// setting, and is toggled per conversation by the speaker button, so
  /// someone who prefers to read in silence turns it off once.
  bool _speakAnswers = false;

  /// Index of the message currently being spoken, for the stop affordance.
  int? _speakingIndex;

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
    // Both are best-effort: the sheet is fully usable by typing and reading
    // if either the recognizer or the speech engine is unavailable.
    VoiceInput.prepare().then((ok) {
      if (mounted) setState(() => _micAvailable = ok);
    });
    ReadAloud.enabled().then((on) {
      if (mounted) setState(() => _speakAnswers = on);
    });
    ReadAloud.onDone = () {
      if (mounted) setState(() => _speakingIndex = null);
    };
  }

  /// Start or stop dictation. Partial results fill the field as the patient
  /// speaks; the final result sends automatically, so a patient who cannot
  /// read the screen never has to find the send button.
  Future<void> _toggleMic() async {
    if (_listening) {
      await VoiceInput.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }
    // Never listen and talk at once - the recognizer would hear the app.
    await _stopSpeaking();
    final started = await VoiceInput.listen(
      onResult: (text, isFinal) {
        if (!mounted) return;
        _ctrl.text = text;
        _ctrl.selection = TextSelection.collapsed(offset: text.length);
        if (isFinal) {
          setState(() => _listening = false);
          if (text.trim().isNotEmpty) _send(text, spoken: true);
        }
      },
    );
    if (!mounted) return;
    if (!started) {
      setState(() => _micAvailable = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Voice is not available on this phone. You can type '
            'your question instead.'),
      ));
      return;
    }
    setState(() => _listening = true);
  }

  Future<void> _stopSpeaking() async {
    await ReadAloud.stop();
    if (mounted) setState(() => _speakingIndex = null);
  }

  /// Speak one answer bubble, replacing anything already being spoken.
  Future<void> _speakMessage(int index) async {
    await ReadAloud.stop();
    if (!mounted) return;
    setState(() => _speakingIndex = index);
    await ReadAloud.speak(_messages[index].text);
  }

  @override
  void dispose() {
    // Leaving the sheet must silence both directions - a mic left open or a
    // voice still reading after the patient closed the chat is alarming.
    VoiceInput.cancel();
    ReadAloud.stop();
    ReadAloud.onDone = null;
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// [spoken] marks a question that arrived by microphone, which always gets
  /// a spoken answer back regardless of the read-aloud setting.
  Future<void> _send(String raw, {bool spoken = false}) async {
    final q = raw.trim();
    if (q.isEmpty || _sending) return;

    // Spoken commands are handled locally and never reach the chat endpoint:
    // "read me my medications" is navigation, not a question, and sending it
    // to a grounded model would waste a call and answer the wrong thing.
    final intent = parseVoiceIntent(q);
    if (intent.kind == VoiceIntentKind.stopSpeaking) {
      _ctrl.clear();
      await _stopSpeaking();
      return;
    }
    if (intent.kind == VoiceIntentKind.readSection) {
      _ctrl.clear();
      await _handleReadSection(intent, q);
      return;
    }

    setState(() {
      _sending = true;
      _messages.add(_ChatMessage(fromPatient: true, text: q));
    });
    _ctrl.clear();
    _autoscroll();
    try {
      final streamedText = await _sendStreaming(q);
      if (!streamedText) await _sendBlocking(q);
      // Read the answer out loud when read-aloud is on. A spoken question
      // always gets a spoken answer, whatever the setting says - someone who
      // just talked to the app is not looking at the screen.
      if (mounted && (_speakAnswers || spoken)) {
        final last = _messages.length - 1;
        if (last >= 0 && !_messages[last].fromPatient && !_messages[last].failed) {
          await _speakMessage(last);
        }
      }
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

  /// Take the patient to the tab they asked for and read it aloud.
  ///
  /// The sheet closes first so the content is actually visible while it is
  /// being read - a voice reading a page hidden behind a sheet helps nobody.
  /// The exchange is still recorded in the transcript so the conversation
  /// reads coherently when they come back.
  Future<void> _handleReadSection(VoiceIntent intent, String asked) async {
    final label = intent.sectionLabel ?? 'that section';
    // Captured BEFORE any await: this can run from a speech-plugin callback,
    // where the element behind `context` may already be gone by the time the
    // awaits finish. Looking the navigator up afterwards is what produced the
    // stuck black barrier.
    final navigator = Navigator.of(context);
    setState(() {
      _messages.add(_ChatMessage(fromPatient: true, text: asked));
      _messages.add(_ChatMessage(
        fromPatient: false,
        text: 'Opening $label and reading it out loud.',
      ));
    });
    await VoiceInput.cancel();
    await ReadAloud.stop();
    // The tab travels back as the pop result; the results screen reads it
    // once this route is fully gone.
    navigator.pop(intent.tabIndex);
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
          // stripped) - replace the accumulated stream with it, now with the
          // grounding verdict the interim deltas could not carry.
          text = '${event['reply'] ?? text}';
          setState(() {
            final bubble = _ChatMessage(
              fromPatient: false,
              text: text,
              fromDocument: event['from_document'] is bool
                  ? event['from_document'] as bool
                  : null,
              sourcePage:
                  event['source_page'] is int ? event['source_page'] as int : null,
            );
            if (bubbleIndex < 0) {
              _messages.add(bubble);
              bubbleIndex = _messages.length - 1;
            } else {
              _messages[bubbleIndex] = bubble;
            }
          });
          _autoscroll();
          continue;
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
      _messages.add(_ChatMessage(
        fromPatient: false,
        text: '${data['reply'] ?? ''}',
        fromDocument:
            data['from_document'] is bool ? data['from_document'] as bool : null,
        sourcePage: data['source_page'] is int ? data['source_page'] as int : null,
      ));
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
                // Grounding badge: the trust signal the server already
                // computes. "From your document" is the product's core
                // promise made visible per answer; the amber variant flags
                // general guidance so it can never masquerade as the
                // patient's own paperwork.
                if (!m.fromPatient && !m.failed && m.fromDocument != null) ...[
                  const SizedBox(height: 6),
                  Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(
                      m.fromDocument!
                          ? Icons.verified_outlined
                          : Icons.info_outline,
                      size: 13,
                      color: m.fromDocument! ? kTealMid : kMedChanged,
                    ),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        m.fromDocument!
                            ? (m.sourcePage != null
                                ? 'From your document · page ${m.sourcePage}'
                                : 'From your document')
                            : 'General guidance - confirm with your care team',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: m.fromDocument! ? kTealMid : kMedChanged,
                        ),
                      ),
                    ),
                  ]),
                ],
                // Speaker control on every answer: stop what is playing, or
                // hear an answer that arrived while read-aloud was off. The
                // patient can always choose silence - nothing auto-plays that
                // they cannot stop in one tap.
                if (!m.fromPatient && !m.failed) ...[
                  const SizedBox(height: 6),
                  InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () => _speakingIndex == i
                        ? _stopSpeaking()
                        : _speakMessage(i),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        Icon(
                          _speakingIndex == i
                              ? Icons.stop_circle_outlined
                              : Icons.volume_up_outlined,
                          size: 15,
                          color: dark ? kTealGlow : kTeal,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _speakingIndex == i ? 'Stop' : 'Listen',
                          style: TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w600,
                            color: dark ? kTealGlow : kTeal,
                          ),
                        ),
                      ]),
                    ),
                  ),
                ],
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
          // Microphone: hidden entirely when the recognizer is unavailable,
          // rather than offered and then failing.
          if (_micAvailable == true) ...[
            SizedBox(
              width: 46,
              height: 46,
              child: IconButton(
                tooltip: _listening ? 'Stop listening' : 'Ask out loud',
                onPressed: _sending ? null : _toggleMic,
                icon: Icon(
                  _listening ? Icons.stop_circle_outlined : Icons.mic_none_rounded,
                  size: 24,
                  color: _listening
                      ? kMedChanged
                      : (dark ? kTealGlow : kTeal),
                ),
              ),
            ),
            const SizedBox(width: 2),
          ],
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
                hintText: _listening
                    ? 'Listening...'
                    : 'Ask in plain language...',
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
