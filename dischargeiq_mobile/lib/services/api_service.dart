import 'dart:convert';
import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:http/http.dart' as http;

/// POST multipart PDF to `/analyze`.
class ApiService {
  ApiService({String? baseUrl}) : _base = baseUrl ?? ApiConfig.baseUrl;

  final String _base;

  Future<Map<String, dynamic>> analyze(Uint8List pdfBytes, String fileName) async {
    final uri = Uri.parse('$_base/analyze');
    final request = http.MultipartRequest('POST', uri);
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        pdfBytes,
        filename: fileName,
      ),
    );
    final streamed = await request.send().timeout(const Duration(seconds: 180));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, response.body);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException(0, 'Invalid JSON');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> chat({
    required String message,
    required String sessionId,
    required Map<String, dynamic> pipelineContext,
  }) async {
    final uri = Uri.parse('$_base/chat');
    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'message': message,
            'session_id': sessionId,
            'pipeline_context': pipelineContext,
          }),
        )
        .timeout(const Duration(seconds: 60));
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, response.body);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException(0, 'Invalid JSON');
    }
    return decoded;
  }

  /// POST /analyze/text — run the pipeline on camera-scanned text (Sprint 2).
  /// The photo never leaves the phone: ML Kit recognizes text on-device and
  /// only the text is sent. Pipeline can take minutes → long timeout.
  Future<Map<String, dynamic>> analyzeText(String text) =>
      _postJson('/analyze/text', {'text': text}, timeoutSeconds: 300);

  /// POST /quiz/generate — the frozen teach-back question set for a session.
  /// `extraction` is the `extraction` field of the /analyze response.
  Future<Map<String, dynamic>> generateQuiz({
    required String sessionId,
    required Map<String, dynamic> extraction,
  }) =>
      _postJson('/quiz/generate', {
        'session_id': sessionId,
        'extraction': extraction,
      }, timeoutSeconds: 90);

  /// POST /quiz/score — score one phase (pre/post).
  /// `questionKeys` come from QuizQuestion.toKeyJson(), in presentation order.
  Future<Map<String, dynamic>> scoreQuiz({
    required String sessionId,
    required String phase,
    required List<Map<String, dynamic>> questionKeys,
    required List<int> answers,
  }) =>
      _postJson('/quiz/score', {
        'session_id': sessionId,
        'phase': phase,
        'question_keys': questionKeys,
        'answers': answers,
      });

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, dynamic> body, {
    int timeoutSeconds = 60,
  }) async {
    final response = await http
        .post(
          Uri.parse('$_base$path'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(Duration(seconds: timeoutSeconds));
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, response.body);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException(0, 'Invalid JSON');
    }
    return decoded;
  }
}

class ApiException implements Exception {
  const ApiException(this.statusCode, this.body);
  final int statusCode;
  final String body;

  @override
  String toString() => 'ApiException($statusCode)';
}
