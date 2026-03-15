import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/models.dart';

class ApiService {
  // ⚠️ QUAN TRỌNG: Nhập IP của MÁY MAC (server), KHÔNG phải IP của thiết bị Android
  // Thiết bị Android sẽ kết nối ĐẾN máy Mac này, nên cần IP của máy Mac
  // 
  // Cách tìm IP máy Mac (server):
  // - Mac/Linux: chạy lệnh: ifconfig | grep "inet " | grep -v 127.0.0.1
  // - Windows: chạy lệnh: ipconfig và tìm "IPv4 Address"
  // 
  // Ví dụ: Nếu máy Mac có IP là 192.168.1.2, thì nhập '192.168.1.2'
  // Set null để dùng mặc định (10.0.2.2 cho emulator, localhost cho iOS)
  static const String? overrideHostIp = '192.168.1.10'; // IP của máy Mac làm server
  
  // Auto-detect platform and use appropriate base URL
  // For web: use localhost
  // For Android emulator: use 10.0.2.2 (special IP that maps to host's localhost)
  // For Android physical device: use overrideHostIp or default to 10.0.2.2
  // For iOS simulator: use localhost (works on iOS)
  // For physical device: use your machine's IP address (e.g., 192.168.1.x)
  static String get baseUrl {
    final host = overrideHostIp ?? _getDefaultHost();
    return 'http://$host:8000';
  }
  
  static String _getDefaultHost() {
    if (kIsWeb) {
      // Web platform
      return '127.0.0.1';
    } else if (Platform.isAndroid) {
      // Android emulator or device
      // 10.0.2.2 is the special IP that Android emulator uses to access host machine's localhost
      // For physical device, set overrideHostIp to your machine's IP
      return '10.0.2.2';
    } else if (Platform.isIOS) {
      // iOS simulator or device
      return '127.0.0.1';
    } else {
      // Other platforms (macOS, Linux, Windows)
      return '127.0.0.1';
    }
  }
  
  static const String _tokenKey = 'auth_token';
  
  final Dio _dio = Dio();
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  ApiService() {
    _dio.options.baseUrl = ApiService.baseUrl;
    _dio.options.connectTimeout = const Duration(seconds: 30);
    _dio.options.receiveTimeout = const Duration(seconds: 180); // 3 minutes for chat responses
    
    // Add interceptor for authentication
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: _tokenKey);
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode == 401) {
            // Token expired, clear storage
            await _storage.delete(key: _tokenKey);
          }
          handler.next(error);
        },
      ),
    );
  }

  // Authentication endpoints
  Future<Token> login(LoginRequest request) async {
    try {
      final response = await _dio.post('/api/auth/login', data: request.toJson());
      return Token.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<User> register(RegisterRequest request) async {
    try {
      final response = await _dio.post('/api/auth/register', data: request.toJson());
      return User.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<User> getCurrentUser() async {
    try {
      final response = await _dio.get('/api/auth/me');
      return User.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> updatePreferences({
    String? region,
    List<String>? focusTopics,
    String? language,
  }) async {
    try {
      await _dio.put('/api/auth/preferences', data: {
        if (region != null) 'region': region,
        if (focusTopics != null) 'focus_topics': focusTopics,
        if (language != null) 'language': language,
      });
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<User> updateUserProfile({
    String? fullName,
    String? phone,
  }) async {
    try {
      final response = await _dio.put('/api/auth/profile', data: {
        if (fullName != null) 'full_name': fullName,
        if (phone != null) 'phone': phone,
      });
      return User.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Chat endpoints
  Future<ChatResponse> sendMessage(ChatRequest request) async {
    try {
      // Use longer timeout for chat endpoint (Ollama can take 1-2 minutes)
      final response = await _dio.post(
        '/api/chat',
        data: request.toJson(),
        options: Options(
          receiveTimeout: const Duration(seconds: 180), // 3 minutes
          sendTimeout: const Duration(seconds: 30),
        ),
      );
      return ChatResponse.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Streaming chat endpoint
  // Note: Currently using Gemini API (non-streaming), simulating streaming by sending full response as chunks
  Stream<Map<String, dynamic>> sendMessageStream(ChatRequest request) async* {
    try {
      final token = await _storage.read(key: _tokenKey);
      
      // Use Gemini endpoint (faster than local Llama)
      final response = await _dio.post(
        '/api/chat/gemini',  // Changed from '/api/chat/stream' to '/api/chat/gemini'
        data: request.toJson(),
        options: Options(
          headers: token != null ? {'Authorization': 'Bearer $token'} : {},
          receiveTimeout: const Duration(seconds: 180),
          sendTimeout: const Duration(seconds: 30),
        ),
      );

      // Gemini endpoint returns ChatResponse (non-streaming)
      // Simulate streaming by sending response in chunks for better UX
      final chatResponse = ChatResponse.fromJson(response.data);
      final responseText = chatResponse.response;
      
      // Split response into smaller chunks and stream them with delay for natural typing effect
      const chunkSize = 20; // Smaller chunks for smoother, word-by-word appearance
      for (int i = 0; i < responseText.length; i += chunkSize) {
        final chunk = responseText.substring(
          i, 
          (i + chunkSize < responseText.length) ? i + chunkSize : responseText.length
        );
        
        yield {
          'type': 'chunk',
          'content': chunk,
          'done': false,
        };
        
        // Delay to simulate natural typing speed (40-80ms per chunk)
        await Future.delayed(const Duration(milliseconds: 80));
      }
      
      // Send sources and final metadata
      yield {
        'type': 'done',
        'sources': chatResponse.sources,
        'confidence': chatResponse.confidence,
        'conversation_id': chatResponse.conversationId,
        'full_response': responseText,
      };
      
    } catch (e) {
      debugPrint('Chat error: $e');
      yield {
        'type': 'error',
        'content': _handleError(e),
        'done': true,
      };
    }
  }

  Future<List<ChatSession>> getChatSessions() async {
    try {
      final response = await _dio.get('/api/chat/sessions');
      return (response.data as List)
          .map((json) => ChatSession.fromJson(json))
          .toList();
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<ChatMessage>> getChatMessages(int sessionId) async {
    try {
      final response = await _dio.get('/api/chat/sessions/$sessionId/messages');
      return (response.data as List)
          .map((json) => ChatMessage.fromJson(json))
          .toList();
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<ChatSession> createChatSession(String title) async {
    try {
      final response = await _dio.post('/api/chat/sessions', data: {'title': title});
      return ChatSession.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<ChatSession> updateChatSessionTitle(int sessionId, String title) async {
    try {
      final response = await _dio.put('/api/chat/sessions/$sessionId', data: {'title': title});
      return ChatSession.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> deleteChatSession(int sessionId) async {
    try {
      await _dio.delete('/api/chat/sessions/$sessionId');
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Document endpoints
  Future<Document> getDocumentById(int documentId) async {
    try {
      final response = await _dio.get('/api/documents/$documentId');
      return Document.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Topics and Categories endpoints
  Future<List<Map<String, dynamic>>> getTopics() async {
    try {
      final response = await _dio.get('/api/topics');
      return List<Map<String, dynamic>>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<Map<String, dynamic>>> getCategoriesByTopic(int topicId) async {
    try {
      final response = await _dio.get('/api/topics/$topicId/categories');
      return List<Map<String, dynamic>>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<Map<String, dynamic>>> getDocumentsByCategory(int categoryId) async {
    try {
      final response = await _dio.get('/api/categories/$categoryId/documents');
      return List<Map<String, dynamic>>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Saved Documents endpoints
  Future<void> saveDocument(int documentId) async {
    try {
      await _dio.post('/api/documents/$documentId/save');
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> unsaveDocument(int documentId) async {
    try {
      await _dio.delete('/api/documents/$documentId/save');
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<bool> isDocumentSaved(int documentId) async {
    try {
      final response = await _dio.get('/api/documents/$documentId/is-saved');
      return response.data['saved'] ?? false;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getSavedDocuments({int skip = 0, int limit = 100}) async {
    try {
      final response = await _dio.get('/api/documents/saved', queryParameters: {
        'skip': skip,
        'limit': limit,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Collections endpoints
  Future<Map<String, dynamic>> createCollection({
    required String name,
    String? description,
    String? color,
  }) async {
    try {
      final response = await _dio.post('/api/collections', data: {
        'name': name,
        if (description != null) 'description': description,
        if (color != null) 'color': color,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<Map<String, dynamic>>> getCollections() async {
    try {
      final response = await _dio.get('/api/collections');
      return List<Map<String, dynamic>>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getCollection(int collectionId) async {
    try {
      final response = await _dio.get('/api/collections/$collectionId');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> updateCollection({
    required int collectionId,
    String? name,
    String? description,
    String? color,
  }) async {
    try {
      final response = await _dio.put('/api/collections/$collectionId', data: {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
        if (color != null) 'color': color,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> deleteCollection(int collectionId) async {
    try {
      await _dio.delete('/api/collections/$collectionId');
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> addDocumentToCollection({
    required int collectionId,
    required int documentId,
    String? notes,
  }) async {
    try {
      await _dio.post(
        '/api/collections/$collectionId/documents/$documentId',
        queryParameters: notes != null ? {'notes': notes} : null,
      );
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> removeDocumentFromCollection({
    required int collectionId,
    required int documentId,
  }) async {
    try {
      await _dio.delete('/api/collections/$collectionId/documents/$documentId');
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getCollectionDocuments({
    required int collectionId,
    int skip = 0,
    int limit = 100,
  }) async {
    try {
      final response = await _dio.get(
        '/api/collections/$collectionId/documents',
        queryParameters: {
          'skip': skip,
          'limit': limit,
        },
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Tags endpoints
  Future<void> addTagToDocument({
    required int documentId,
    required String tagName,
  }) async {
    try {
      await _dio.post('/api/documents/$documentId/tags', data: {
        'tag_name': tagName,
      });
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> removeTagFromDocument({
    required int documentId,
    required String tagName,
  }) async {
    try {
      await _dio.delete('/api/documents/$documentId/tags/$tagName');
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<Map<String, dynamic>>> getDocumentTags(int documentId) async {
    try {
      final response = await _dio.get('/api/documents/$documentId/tags');
      return List<Map<String, dynamic>>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<String>> getAllTags() async {
    try {
      final response = await _dio.get('/api/tags');
      return List<String>.from(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getDocumentsByTag({
    required String tagName,
    int skip = 0,
    int limit = 100,
  }) async {
    try {
      final response = await _dio.get(
        '/api/tags/$tagName/documents',
        queryParameters: {
          'skip': skip,
          'limit': limit,
        },
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Export & Share endpoints
  Future<Response> exportDocument({
    required int documentId,
    required String format, // 'pdf', 'docx', 'doc'
  }) async {
    try {
      final response = await _dio.get(
        '/api/documents/$documentId/export',
        queryParameters: {'format': format},
        options: Options(
          responseType: ResponseType.bytes,
          followRedirects: true,
          receiveTimeout: const Duration(seconds: 60), // Longer timeout for file download
        ),
      );
      
      // Verify response has data
      if (response.data == null || (response.data as List).isEmpty) {
        throw Exception('File không có dữ liệu');
      }
      
      return response;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getShareLink(int documentId) async {
    try {
      final response = await _dio.get('/api/documents/$documentId/share');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Token management
  Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null;
  }

  // Error handling
  String _handleError(dynamic error) {
    if (error is DioException) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
          return 'Kết nối mạng không ổn định. Vui lòng thử lại.';
        case DioExceptionType.receiveTimeout:
          return 'Hệ thống đang xử lý câu hỏi, vui lòng đợi thêm một chút hoặc thử lại sau.';
        case DioExceptionType.badResponse:
          final statusCode = error.response?.statusCode;
          final message = error.response?.data?['detail'] ?? 'Có lỗi xảy ra';
          
          switch (statusCode) {
            case 400:
              return 'Dữ liệu không hợp lệ: $message';
            case 401:
              return 'Email hoặc mật khẩu không đúng';
            case 403:
              return 'Bạn không có quyền thực hiện hành động này';
            case 404:
              return 'Không tìm thấy dữ liệu';
            case 500:
              return 'Lỗi máy chủ. Vui lòng thử lại sau.';
            default:
              return message;
          }
        case DioExceptionType.cancel:
          return 'Yêu cầu đã bị hủy';
        case DioExceptionType.connectionError:
          return 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng.';
        default:
          return 'Có lỗi xảy ra. Vui lòng thử lại.';
      }
    }
    return 'Có lỗi không xác định xảy ra. Vui lòng thử lại.';
  }
}

