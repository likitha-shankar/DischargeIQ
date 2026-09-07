import 'dart:convert';
import 'dart:typed_data';

import 'package:dischargeiq_mobile/config.dart';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show MediaType;

/// POST multipart PDF to `/analyze`.
class ApiService {
  ApiService({String? baseUrl}) : _base = baseUrl ?? ApiConfig.baseUrl;

  final String _base;

  /// Bearer header for every call, or empty when no key is configured.
  ///
  /// The backend skips the check entirely when it has no `DISCHARGEIQ_API_KEY`
  /// (local dev), so sending nothing is correct there. Spread this into the
  /// headers of every request - a call that omits it gets a 401 from any
  /// deployment that requires the key.
  static Map<String, String> get _authHeaders =>
      ApiConfig.apiKey.isEmpty ? const {} : {'Authorization': 'Bearer ${ApiConfig.apiKey}'};

  /// Analyse a discharge PDF.
  ///
  /// [audience] is "caregiver" when the document is filed under a young
  /// child, and null otherwise. Sending it lets the backend skip inferring
  /// the reader from the document text: a profile the patient filled in
  /// beats a regular expression over dictated prose.
  Future<Map<String, dynamic>> analyze(
    Uint8List pdfBytes,
    String fileName, {
    String? sessionId,
    String? audience,
  }) async {
    final uri = Uri.parse('$_base/analyze');
    final request = http.MultipartRequest('POST', uri);
    request.headers.addAll(_authHeaders);
    if (sessionId != null) {
      // Lets the loading screen poll GET /progress/{id} for live updates.
      request.headers['X-Discharge-Session-Id'] = sessionId;
    }
    if (audience != null) {
      request.fields['audience'] = audience;
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
          headers: {'Content-Type': 'application/json', ..._authHeaders},
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

  /// POST /media/case - the patient's OWN audio explainer, from their document.
  ///
  /// Distinct from `GET /media/{document_type}`, which serves one recorded
  /// file per condition: every heart-failure patient hears the same words
  /// there. This narrates THIS discharge summary - their drugs, their doses,
  /// their follow-ups.
  ///
  /// Expensive: a script LLM call plus TTS, several seconds per request. The
  /// server keeps nothing, so the caller MUST cache the returned bytes and
  /// must not re-post on a second press of play.
  ///
  /// Returns null - never throws - when the feature is off (404), the payload
  /// has nothing to narrate (422), or generation failed (502). Every one of
  /// those means the same thing to the patient: no player, read the text. An
  /// exception here would take down the tab over an optional extra.
  Future<Uint8List?> caseAudio({
    required String sessionId,
    required Map<String, dynamic> pipelinePayload,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$_base/media/case'),
            headers: {'Content-Type': 'application/json', ..._authHeaders},
            body: jsonEncode({
              'session_id': sessionId,
              'pipeline_payload': pipelinePayload,
            }),
          )
          // Two model calls run server-side; 60s matches /chat's ceiling.
          .timeout(const Duration(seconds: 60));
      if (response.statusCode != 200) {
        // Silent to the patient, visible to whoever is debugging. Returning
        // null with no trace at all made a field failure impossible to tell
        // apart from "the button did nothing", which is what a release build
        // on a real phone looks like from the outside.
        debugPrint('caseAudio: HTTP ${response.statusCode} '
            '(${_caseAudioMeaning(response.statusCode)})');
        return null;
      }
      // A zero-byte 200 would hand the player an empty track that reports a
      // zero duration and sits at "0:00" forever, which reads as a hang.
      if (response.bodyBytes.isEmpty) {
        debugPrint('caseAudio: HTTP 200 but empty body');
        return null;
      }
      return response.bodyBytes;
    } catch (error) {
      // Offline, timeout, malformed response - all degrade to text.
      debugPrint('caseAudio: $error');
      return null;
    }
  }

  /// Plain-English gloss for the statuses this endpoint documents, so a log
  /// line is actionable without opening the route source.
  static String _caseAudioMeaning(int status) => switch (status) {
        401 => 'API key missing or wrong in this build',
        404 => 'CASE_AUDIO_ENABLED is off server-side',
        422 => 'payload had nothing to narrate',
        502 => 'script or TTS generation failed - quota or network',
        _ => 'unexpected',
      };

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
        ..headers.addAll(_authHeaders)
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
  /// [audience] carries the same reader hint as [analyze] - the scan path
  /// must not lose caregiver voice just because the document arrived as text.
  Future<Map<String, dynamic>> analyzeText(
    String text, {
    String? sessionId,
    String? audience,
  }) =>
      _postJson(
          '/analyze/text',
          {'text': text, if (audience != null) 'audience': audience},
          timeoutSeconds: 300,
          sessionId: sessionId);

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
    String? audience,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$_base/analyze/image'));
    request.headers.addAll(_authHeaders);
    if (sessionId != null) {
      request.headers['X-Discharge-Session-Id'] = sessionId;
    }
    if (audience != null) {
      // Same reader hint as analyze(): filed-under-a-child beats inference.
      request.fields['audience'] = audience;
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
  /// `focusDomains` are the quiz domains behind the patient's chosen learning
  /// goals; each gets a second question at the expense of an unchosen domain.
  /// Empty keeps the even one-per-domain spread.
  Future<Map<String, dynamic>> generateQuiz({
    required String sessionId,
    required Map<String, dynamic> extraction,
    List<String> focusDomains = const [],
  }) =>
      _postJson('/quiz/generate', {
        'session_id': sessionId,
        'extraction': extraction,
        'focus_domains': focusDomains,
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
            ..._authHeaders,
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
