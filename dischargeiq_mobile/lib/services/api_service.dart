import 'dart:convert';
import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show MediaType;

/// POST multipart PDF to `/analyze`.
class ApiService {
  ApiService({String? baseUrl}) : _base = baseUrl ?? ApiConfig.baseUrl;

  final String _base;

  Future<Map<String, dynamic>> analyze(
    Uint8List pdfBytes,
    String fileName, {
    String? sessionId,
  }) async {
    final uri = Uri.parse('$_base/analyze');
    final request = http.MultipartRequest('POST', uri);
    if (sessionId != null) {
      // Lets the loading screen poll GET /progress/{id} for live updates.
      request.headers['X-Discharge-Session-Id'] = sessionId;
    }
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

  /// POST /chat/stream - grounded chat with live token streaming (SSE).
  ///
  /// Emits one map per server event: `{'delta': String}` fragments while the
  /// answer generates, then `{'done': true, 'reply': ..., ...}`, or
  /// `{'error': String}` on LLM failure. The server grounds from its cached
  /// per-session context, so no pipeline_context is sent - callers should
  /// fall back to [chat] (which re-sends the full context) when this stream
  /// fails before producing any text.
  Stream<Map<String, dynamic>> chatStream({
    required String message,
    required String sessionId,
  }) async* {
    final client = http.Client();
    try {
      final request = http.Request('POST', Uri.parse('$_base/chat/stream'))
        ..headers['Content-Type'] = 'application/json'
        ..body = jsonEncode({'message': message, 'session_id': sessionId});
      final response =
          await client.send(request).timeout(const Duration(seconds: 60));
      if (response.statusCode != 200) {
        throw ApiException(response.statusCode, '');
      }
      final lines =
          response.stream.transform(utf8.decoder).transform(const LineSplitter());
      await for (final line in lines) {
        if (!line.startsWith('data: ')) continue;
        final decoded = jsonDecode(line.substring(6));
        if (decoded is Map<String, dynamic>) yield decoded;
      }
    } finally {
      client.close();
    }
  }

  /// POST /analyze/text - run the pipeline on camera-scanned text (Sprint 2).
  /// The photo never leaves the phone: ML Kit recognizes text on-device and
  /// only the text is sent. Pipeline can take minutes → long timeout.
  Future<Map<String, dynamic>> analyzeText(String text, {String? sessionId}) =>
      _postJson('/analyze/text', {'text': text},
          timeoutSeconds: 300, sessionId: sessionId);

  /// GET /progress/{sessionId} - live per-agent pipeline progress. Cheap and
  /// safe to poll every couple of seconds while an analysis runs.
  Future<Map<String, dynamic>> getProgress(String sessionId) async {
    final response = await http
        .get(Uri.parse('$_base/progress/$sessionId'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, response.body);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException(0, 'Invalid JSON');
    }
    return decoded;
  }

  /// POST /analyze/image - OPT-IN enhanced cloud read for handwriting the
  /// on-device OCR cannot handle. This is the ONLY call that uploads photos;
  /// the patient explicitly chooses it on the scan screen.
  Future<Map<String, dynamic>> analyzeImages(
    List<String> imagePaths, {
    String? sessionId,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$_base/analyze/image'));
    if (sessionId != null) {
      request.headers['X-Discharge-Session-Id'] = sessionId;
    }
    for (final path in imagePaths) {
      request.files.add(await http.MultipartFile.fromPath(
        'files',
        path,
        contentType: MediaType('image', 'jpeg'),
      ));
    }
    final streamed = await request.send().timeout(const Duration(seconds: 300));
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

  /// POST /quiz/generate - the frozen teach-back question set for a session.
  /// `extraction` is the `extraction` field of the /analyze response.
  Future<Map<String, dynamic>> generateQuiz({
    required String sessionId,
    required Map<String, dynamic> extraction,
  }) =>
      _postJson('/quiz/generate', {
        'session_id': sessionId,
        'extraction': extraction,
      }, timeoutSeconds: 90);

  /// POST /quiz/score - score one phase (pre/post).
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
    String? sessionId,
  }) async {
    final response = await http
        .post(
          Uri.parse('$_base$path'),
          headers: {
            'Content-Type': 'application/json',
            if (sessionId != null) 'X-Discharge-Session-Id': sessionId,
          },
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
