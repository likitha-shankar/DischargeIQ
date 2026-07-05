/// screens/quiz_screen.dart
///
/// The gamified teach-back loop (Sprint 3) - the comprehension-lift feature:
///
///   intro → baseline quiz (no feedback) → learning cards → post-quiz
///   (with feedback) → results (score ring, lift banner, domain chips)
///   → mastery path: failed domains force a focused review before retake.
///
/// Measurement protocol (work plan §3a): the SAME frozen question set is used
/// pre and post; post presents them in shuffled order; the baseline shows no
/// correctness feedback so it cannot teach.
///
/// Embedded as the "Test yourself" tab of ResultsScreen. All quiz state lives
/// here; visuals live in widgets/quiz_widgets.dart; scoring is server-side via
/// POST /quiz/score (works offline-tolerant: score errors keep local answers).
library;

import 'dart:math' show Random;

import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/models/quiz.dart';
import 'package:dischargeiq_mobile/services/api_service.dart';
import 'package:dischargeiq_mobile/widgets/quiz_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show HapticFeedback;

enum _Phase { intro, loading, pre, learn, post, results, error }

class QuizBody extends StatefulWidget {
  const QuizBody({super.key, required this.result, required this.sessionId});

  /// Full /analyze response - extraction feeds question generation and the
  /// agent texts feed the learning cards.
  final Map<String, dynamic> result;
  final String sessionId;

  @override
  State<QuizBody> createState() => _QuizBodyState();
}

class _QuizBodyState extends State<QuizBody> {
  final _api = ApiService();

  _Phase _phase = _Phase.intro;
  String _error = '';

  List<QuizQuestion> _questions = [];
  // Presentation order for the post phase - same questions, shuffled (§3a).
  List<int> _postOrder = [];
  int _current = 0;
  List<int?> _preAnswers = [];
  List<int?> _postAnswers = [];
  QuizScoreResult? _preResult;
  QuizScoreResult? _postResult;
  // Mastery path: when set, the learn phase shows only these domains.
  Set<String> _reviewDomains = {};
  int _learnIndex = 0;
  // Consecutive correct answers in the post phase (accuracy streak, no timer).
  int _streak = 0;

  // ── Flow actions ─────────────────────────────────────────────────────────

  Future<void> _start() async {
    setState(() => _phase = _Phase.loading);
    try {
      final resp = await _api.generateQuiz(
        sessionId: widget.sessionId,
        extraction: (widget.result['extraction'] as Map<String, dynamic>? ?? {}),
      );
      final questions = [
        for (final q in (resp['questions'] as List? ?? []))
          QuizQuestion.fromJson(q as Map<String, dynamic>)
      ];
      if (questions.isEmpty) throw const ApiException(0, 'Empty quiz');
      setState(() {
        _questions = questions;
        _preAnswers = List.filled(questions.length, null);
        _postAnswers = List.filled(questions.length, null);
        _postOrder = List.generate(questions.length, (i) => i)..shuffle(Random());
        _current = 0;
        _phase = _Phase.pre;
      });
    } catch (e) {
      setState(() {
        _error = 'Could not create your quiz. Check your connection and try again.';
        _phase = _Phase.error;
      });
    }
  }

  /// Index into _questions for the question currently shown.
  int get _qIndex =>
      _phase == _Phase.post ? _postOrder[_current] : _current;

  List<int?> get _answers =>
      _phase == _Phase.post ? _postAnswers : _preAnswers;

  void _select(int option) {
    // First tap in the post phase locks the answer and drives streak +
    // haptics; a correct pick extends the streak, a miss quietly resets it
    // (non-punitive: no buzz, no lost points).
    if (_phase == _Phase.post && _answers[_qIndex] == null) {
      if (option == _questions[_qIndex].correctIndex) {
        _streak++;
        HapticFeedback.mediumImpact();
      } else {
        _streak = 0;
      }
    } else {
      HapticFeedback.selectionClick();
    }
    setState(() => _answers[_qIndex] = option);
  }

  Future<void> _next() async {
    if (_current < _questions.length - 1) {
      setState(() => _current++);
      return;
    }
    // Last question answered - score this phase.
    final isPre = _phase == _Phase.pre;
    final answers = [for (final a in _answers) a ?? -1];
    QuizScoreResult? scored;
    try {
      final resp = await _api.scoreQuiz(
        sessionId: widget.sessionId,
        phase: isPre ? 'pre' : 'post',
        questionKeys: [for (final q in _questions) q.toKeyJson()],
        answers: answers,
      );
      scored = QuizScoreResult.fromJson(resp);
    } catch (_) {
      // Server unreachable → score locally so the flow never dead-ends.
      scored = _scoreLocally(isPre ? 'pre' : 'post', answers);
    }
    setState(() {
      if (isPre) {
        _preResult = scored;
        _reviewDomains = {};
        _learnIndex = 0;
        _current = 0;
        _phase = _Phase.learn;
      } else {
        _postResult = scored;
        _phase = _Phase.results;
      }
    });
  }

  QuizScoreResult _scoreLocally(String phase, List<int> answers) {
    var score = 0;
    final domains = <String, Map<String, int>>{};
    for (var i = 0; i < _questions.length; i++) {
      final d = _questions[i].domain;
      final bucket = domains.putIfAbsent(d, () => {'correct': 0, 'total': 0});
      bucket['total'] = bucket['total']! + 1;
      if (answers[i] == _questions[i].correctIndex) {
        score++;
        bucket['correct'] = bucket['correct']! + 1;
      }
    }
    return QuizScoreResult(
      phase: phase,
      score: score,
      total: _questions.length,
      percent: (100.0 * score / _questions.length),
      domainScores: domains,
      failedDomains: [
        for (final e in domains.entries)
          if (e.value['correct']! < e.value['total']!) e.key
      ],
      comprehensionDelta: null,
    );
  }

  void _startMasteryReview() {
    setState(() {
      _reviewDomains = {...?_postResult?.failedDomains};
      _learnIndex = 0;
      _phase = _Phase.learn;
    });
  }

  void _startPost() {
    setState(() {
      _postAnswers = List.filled(_questions.length, null);
      _postOrder = List.generate(_questions.length, (i) => i)..shuffle(Random());
      _current = 0;
      _streak = 0;
      _phase = _Phase.post;
    });
  }

  // ── Learning card content, derived from the pipeline result ─────────────

  List<(String domain, String content)> get _learnCards {
    final r = widget.result;
    final ex = r['extraction'] as Map<String, dynamic>? ?? {};
    String joinList(dynamic v) =>
        v is List && v.isNotEmpty ? v.map((e) => '• $e').join('\n') : '';
    final meds = [
      for (final m in (ex['medications'] as List? ?? []))
        '• ${m['name']}${m['dose'] != null ? ' - ${m['dose']}' : ''}'
            '${m['frequency'] != null ? ', ${m['frequency']}' : ''}'
    ].join('\n');
    final appts = [
      for (final a in (ex['follow_up_appointments'] as List? ?? []))
        '• ${a['provider'] ?? a['specialty'] ?? 'Appointment'}'
            '${a['date'] != null ? ' - ${a['date']}' : ''}'
    ].join('\n');

    final all = <(String, String)>[
      ('diagnosis', '${r['diagnosis_explanation'] ?? ''}'),
      ('medications',
          [meds, '${r['medication_rationale'] ?? ''}'].where((s) => s.isNotEmpty).join('\n\n')),
      ('follow_up', appts),
      ('activity',
          [
            joinList(ex['activity_restrictions']),
            joinList(ex['dietary_restrictions']),
            '${r['recovery_trajectory'] ?? ''}'
          ].where((s) => s.isNotEmpty).join('\n\n')),
      ('red_flags',
          [joinList(ex['red_flag_symptoms']), '${r['escalation_guide'] ?? ''}']
              .where((s) => s.isNotEmpty)
              .join('\n\n')),
    ];
    final cards = [
      for (final c in all)
        if (c.$2.trim().isNotEmpty &&
            (_reviewDomains.isEmpty || _reviewDomains.contains(c.$1)))
          c
    ];
    // A failed domain with no card content must not brick the mastery loop.
    return cards.isNotEmpty ? cards : [for (final c in all) if (c.$2.trim().isNotEmpty) c];
  }

  // ── UI ───────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final body = switch (_phase) {
      _Phase.intro => _intro(),
      _Phase.loading => const Center(child: CircularProgressIndicator(color: kTealMid)),
      _Phase.error => _errorView(),
      _Phase.pre || _Phase.post => _quiz(),
      _Phase.learn => _learn(),
      _Phase.results => _results(),
    };
    return SafeArea(
      child: Padding(padding: const EdgeInsets.all(16), child: body),
    );
  }

  Widget _intro() {
    return _CenteredScroll(children: [
      const Icon(Icons.psychology_alt_outlined, size: 56, color: kTealMid),
      const SizedBox(height: 14),
      Text('Test your understanding',
          textAlign: TextAlign.center,
          style: Theme.of(context)
              .textTheme
              .headlineSmall
              ?.copyWith(fontWeight: FontWeight.w800)),
      const SizedBox(height: 10),
      Text(
        'A short quiz about YOUR discharge plan.\n\n'
        '1. Answer 5 quick questions.\n'
        '2. Learn with simple cards.\n'
        '3. Answer again and watch your score climb.',
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5),
      ),
      const SizedBox(height: 22),
      FilledButton.icon(
        style: FilledButton.styleFrom(
            backgroundColor: kTealMid,
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14)),
        onPressed: _start,
        icon: const Icon(Icons.play_arrow_rounded),
        label: const Text('Start the quiz'),
      ),
    ]);
  }

  Widget _errorView() {
    return _CenteredScroll(children: [
      const Icon(Icons.wifi_off_rounded, size: 44, color: kTier2),
      const SizedBox(height: 12),
      Text(_error, textAlign: TextAlign.center),
      const SizedBox(height: 16),
      OutlinedButton(onPressed: _start, child: const Text('Try again')),
    ]);
  }

  Widget _quiz() {
    final isPre = _phase == _Phase.pre;
    final q = _questions[_qIndex];
    final answered = _answers[_qIndex] != null;
    return ListView(
      children: [
        QuizProgressBar(
          current: _current + 1,
          total: _questions.length,
          label: isPre
              ? 'Before you learn - question ${_current + 1} of ${_questions.length}'
              : 'After learning - question ${_current + 1} of ${_questions.length}',
        ),
        // Accuracy streak, post phase only (the baseline gives no feedback).
        if (!isPre && _streak >= 2 && answered) ...[
          const SizedBox(height: 10),
          Align(alignment: Alignment.centerLeft, child: StreakChip(streak: _streak)),
        ],
        const SizedBox(height: 18),
        QuestionCard(
          // Key forces a fresh card per question so option state never leaks.
          key: ValueKey('$_phase-$_qIndex'),
          question: q,
          selectedIndex: _answers[_qIndex],
          revealCorrect: !isPre,
          onSelect: _select,
        ),
        const SizedBox(height: 18),
        FilledButton(
          style: FilledButton.styleFrom(
              backgroundColor: kTealMid,
              padding: const EdgeInsets.symmetric(vertical: 14)),
          onPressed: answered ? _next : null,
          child: Text(_current < _questions.length - 1
              ? 'Next'
              : (isPre ? 'Finish & start learning' : 'See my results')),
        ),
      ],
    );
  }

  Widget _learn() {
    final cards = _learnCards;
    final isReview = _reviewDomains.isNotEmpty;
    final card = cards[_learnIndex.clamp(0, cards.length - 1)];
    final last = _learnIndex >= cards.length - 1;
    return ListView(
      children: [
        QuizProgressBar(
          current: _learnIndex + 1,
          total: cards.length,
          label: isReview
              ? 'Focused review - the parts to master'
              : 'Learning time - card ${_learnIndex + 1} of ${cards.length}',
        ),
        const SizedBox(height: 18),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: kTealMid, width: 1.2),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(kDomainIcons[card.$1] ?? Icons.menu_book_outlined,
                      color: kTealMid),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(kDomainLabels[card.$1] ?? card.$1,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700)),
                  ),
                ]),
                const Divider(height: 20),
                Text(card.$2,
                    style: Theme.of(context)
                        .textTheme
                        .bodyLarge
                        ?.copyWith(height: 1.5)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            if (_learnIndex > 0)
              OutlinedButton(
                onPressed: () => setState(() => _learnIndex--),
                child: const Text('Back'),
              ),
            const Spacer(),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: kTealMid),
              onPressed: () {
                if (!last) {
                  setState(() => _learnIndex++);
                } else {
                  _startPost();
                }
              },
              child: Text(last ? 'I\'m ready - quiz me again' : 'Got it, next'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _results() {
    final pre = _preResult;
    final post = _postResult;
    if (post == null) return const SizedBox.shrink();
    final mastered = post.failedDomains.isEmpty;
    // Celebration gating (research: rare celebrations register as meaningful):
    // confetti only when comprehension improved; a bigger burst for 100%.
    final perfect = post.percent >= 100;
    final improved = pre != null && post.percent > pre.percent;
    final listView = ListView(
      children: [
        const SizedBox(height: 8),
        Center(child: ScoreRing(percent: post.percent)),
        const SizedBox(height: 18),
        if (pre != null)
          LiftBanner(prePercent: pre.percent, postPercent: post.percent),
        const SizedBox(height: 18),
        Text('How you did by topic',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        DomainChips(result: post),
        const SizedBox(height: 22),
        if (mastered)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
                color: kTier3Bg, borderRadius: BorderRadius.circular(12)),
            child: const Row(children: [
              Icon(Icons.emoji_events_outlined, color: kTier3),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'You understood every topic. Share what you learned with your family!',
                  style: TextStyle(color: kTextPrimaryLight, height: 1.35),
                ),
              ),
            ]),
          )
        else
          FilledButton.icon(
            style: FilledButton.styleFrom(
                backgroundColor: kTealMid,
                padding: const EdgeInsets.symmetric(vertical: 14)),
            onPressed: _startMasteryReview,
            icon: const Icon(Icons.replay_rounded),
            label: Text(
                'Review ${post.failedDomains.length == 1 ? 'the tricky topic' : 'the tricky topics'} and try again'),
          ),
        const SizedBox(height: 10),
        Center(
          child: TextButton(
            onPressed: () => setState(() {
              _phase = _Phase.intro;
              _preResult = null;
              _postResult = null;
              _reviewDomains = {};
            }),
            child: const Text('Start over'),
          ),
        ),
      ],
    );
    if (!improved && !perfect) return listView;
    return Stack(children: [
      listView,
      Positioned.fill(child: ConfettiBurst(pieces: perfect ? 110 : 60)),
    ]);
  }
}

class _CenteredScroll extends StatelessWidget {
  const _CenteredScroll({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: children,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
