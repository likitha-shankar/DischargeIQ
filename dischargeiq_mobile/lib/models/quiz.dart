/// models/quiz.dart
///
/// Client-side models for the teach-back quiz loop (Sprint 3).
/// Mirrors the backend contracts in dischargeiq/models/quiz.py and
/// dischargeiq/api/schemas.py:
///   POST /quiz/generate → QuizQuestion list (the frozen set for this session)
///   POST /quiz/score    → QuizScoreResult (score, domain breakdown, delta)
///
/// The client keeps the full questions (including correct_index) in memory and
/// sends back only the grading key + answers for scoring — the endpoints are
/// stateless by design so they work on any backend instance.
library;

class QuizQuestion {
  const QuizQuestion({
    required this.question,
    required this.options,
    required this.correctIndex,
    required this.domain,
    required this.explanation,
  });

  final String question;
  final List<String> options;
  final int correctIndex;
  final String domain;
  final String explanation;

  factory QuizQuestion.fromJson(Map<String, dynamic> json) => QuizQuestion(
        question: '${json['question'] ?? ''}',
        options: [for (final o in (json['options'] as List? ?? [])) '$o'],
        correctIndex: (json['correct_index'] as num?)?.toInt() ?? 0,
        domain: '${json['domain'] ?? 'diagnosis'}',
        explanation: '${json['explanation'] ?? ''}',
      );

  /// Grading key entry sent to POST /quiz/score.
  Map<String, dynamic> toKeyJson() => {
        'domain': domain,
        'correct_index': correctIndex,
      };
}

class QuizScoreResult {
  const QuizScoreResult({
    required this.phase,
    required this.score,
    required this.total,
    required this.percent,
    required this.domainScores,
    required this.failedDomains,
    this.comprehensionDelta,
  });

  final String phase;
  final int score;
  final int total;
  final double percent;

  /// {"medications": {"correct": 1, "total": 2}, ...}
  final Map<String, Map<String, int>> domainScores;
  final List<String> failedDomains;

  /// percent(post) - percent(pre); null on pre phases or when the backend
  /// has no database to look up the stored baseline.
  final double? comprehensionDelta;

  factory QuizScoreResult.fromJson(Map<String, dynamic> json) {
    final rawDomains = json['domain_scores'] as Map<String, dynamic>? ?? {};
    return QuizScoreResult(
      phase: '${json['phase'] ?? 'pre'}',
      score: (json['score'] as num?)?.toInt() ?? 0,
      total: (json['total'] as num?)?.toInt() ?? 0,
      percent: (json['percent'] as num?)?.toDouble() ?? 0.0,
      domainScores: {
        for (final e in rawDomains.entries)
          e.key: {
            'correct': ((e.value as Map)['correct'] as num?)?.toInt() ?? 0,
            'total': ((e.value as Map)['total'] as num?)?.toInt() ?? 0,
          },
      },
      failedDomains: [
        for (final d in (json['failed_domains'] as List? ?? [])) '$d'
      ],
      comprehensionDelta: (json['comprehension_delta'] as num?)?.toDouble(),
    );
  }
}

/// Patient-friendly labels and icons per comprehension domain.
const Map<String, String> kDomainLabels = {
  'diagnosis': 'What happened',
  'medications': 'Your medications',
  'follow_up': 'Follow-up visits',
  'activity': 'Activity & diet',
  'red_flags': 'Warning signs',
};
