import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  List<ChatSession> _sessions = [];
  List<ChatMessage> _currentMessages = [];
  String? _currentConversationId;
  bool _isLoading = false;
  bool _isSending = false;
  String? _error;

  List<ChatSession> get sessions => _sessions;
  List<ChatMessage> get currentMessages => _currentMessages;
  String? get currentConversationId => _currentConversationId;
  bool get isLoading => _isLoading;
  bool get isSending => _isSending;
  String? get error => _error;

  Future<void> loadChatSessions() async {
    _setLoading(true);
    _clearError();

    try {
      _sessions = await _apiService.getChatSessions();
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> loadChatMessages(int sessionId) async {
    _setLoading(true);
    _clearError();

    try {
      _currentMessages = await _apiService.getChatMessages(sessionId);
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> selectTopic(String topic) async {
    // When user selects a topic, show a prompt question instead of sending message directly
    final promptMessage = ChatMessage(
      sender: 'assistant',
      messageText: 'Bạn cần giải quyết vấn đề gì liên quan đến chủ đề "$topic"?',
      createdAt: DateTime.now(),
    );
    
    _currentMessages.add(promptMessage);
    notifyListeners();
  }

  Future<void> sendMessage(String message) async {
    _setSending(true);
    _clearError();

    try {
      final request = ChatRequest(
        message: message,
        conversationId: _currentConversationId,
      );
      
      final response = await _apiService.sendMessage(request);
      
      // Update conversation ID
      _currentConversationId = response.conversationId;
      
      // Add user message
      final userMessage = ChatMessage(
        sender: 'user',
        messageText: message,
        createdAt: DateTime.now(),
      );
      _currentMessages.add(userMessage);
      
      // Add assistant response
      final assistantMessage = ChatMessage(
        sender: 'assistant',
        messageText: response.response,
        createdAt: DateTime.now(),
        confidence: response.confidence,
      );
      _currentMessages.add(assistantMessage);
      
      notifyListeners();
      
      // Reload sessions to update message count
      await loadChatSessions();
      
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setSending(false);
    }
  }

  Future<void> sendMessageStream(String message) async {
    _setSending(true);
    _clearError();

    try {
      final request = ChatRequest(
        message: message,
        conversationId: _currentConversationId,
      );
      
      // Add user message first
      final userMessage = ChatMessage(
        sender: 'user',
        messageText: message,
        createdAt: DateTime.now(),
      );
      _currentMessages.add(userMessage);
      
      // Create initial assistant message with "Đang xử lý..." that will be replaced as chunks arrive
      final initialTime = DateTime.now();
      _currentMessages.add(ChatMessage(
        sender: 'assistant',
        messageText: 'Đang xử lý câu hỏi...',
        createdAt: initialTime,
        isProcessing: true,
      ));
      
      notifyListeners();
      
      // Stream response
      String fullResponse = '';
      List<Map<String, dynamic>> sources = [];
      double? confidence;
      String? conversationId;
      
      await for (final chunk in _apiService.sendMessageStream(request)) {
        final type = chunk['type'] as String?;
        
        if (type == 'chunk') {
          final content = chunk['content'] as String? ?? '';
          fullResponse += content;
          // Replace the last message (assistant message) with updated content
          // Remove "Đang xử lý..." and isProcessing flag when first chunk arrives
          if (_currentMessages.isNotEmpty) {
            _currentMessages[_currentMessages.length - 1] = ChatMessage(
              sender: 'assistant',
              messageText: fullResponse,
              createdAt: initialTime,
              isProcessing: false,
            );
            notifyListeners();
          }
        } else if (type == 'sources') {
          final content = chunk['content'] as String? ?? '';
          fullResponse += content;
          // Replace the last message with updated content including sources
          if (_currentMessages.isNotEmpty) {
            _currentMessages[_currentMessages.length - 1] = ChatMessage(
              sender: 'assistant',
              messageText: fullResponse,
              createdAt: initialTime,
              isProcessing: false,
            );
            notifyListeners();
          }
        } else if (type == 'done') {
          conversationId = chunk['conversation_id'] as String?;
          sources = (chunk['sources'] as List?)?.cast<Map<String, dynamic>>() ?? [];
          confidence = (chunk['confidence'] as num?)?.toDouble();
          final finalResponse = chunk['full_response'] as String? ?? fullResponse;
          // Replace with final message including confidence
          if (_currentMessages.isNotEmpty) {
            _currentMessages[_currentMessages.length - 1] = ChatMessage(
              sender: 'assistant',
              messageText: finalResponse,
              createdAt: initialTime,
              confidence: confidence,
              isProcessing: false,
            );
            _currentConversationId = conversationId;
            notifyListeners();
          }
        } else if (type == 'error') {
          final errorContent = chunk['content'] as String? ?? 'Có lỗi xảy ra';
          // Replace with error message or add new one if list is empty
          if (_currentMessages.isNotEmpty) {
            _currentMessages[_currentMessages.length - 1] = ChatMessage(
              sender: 'assistant',
              messageText: errorContent,
              createdAt: initialTime,
              isProcessing: false,
            );
          } else {
            _currentMessages.add(ChatMessage(
              sender: 'assistant',
              messageText: errorContent,
              createdAt: initialTime,
              isProcessing: false,
            ));
          }
          notifyListeners();
          if (chunk['done'] == true) {
            break;
          }
        }
      }
      
      // Reload sessions to update message count
      await loadChatSessions();
      
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setSending(false);
    }
  }

  Future<void> createNewSession(String title) async {
    _setLoading(true);
    _clearError();

    try {
      final session = await _apiService.createChatSession(title);
      _sessions.insert(0, session);
      _currentMessages.clear();
      _currentConversationId = null;
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  void startNewChat() {
    _currentMessages.clear();
    _currentConversationId = null;
    notifyListeners();
  }

  void selectSession(ChatSession session) {
    _currentMessages.clear();
    _currentConversationId = null;
    loadChatMessages(session.sessionId);
  }

  Future<void> updateSessionTitle(int sessionId, String newTitle) async {
    _setLoading(true);
    _clearError();

    try {
      final updatedSession = await _apiService.updateChatSessionTitle(sessionId, newTitle);
      
      // Update the session in the list
      final index = _sessions.indexWhere((s) => s.sessionId == sessionId);
      if (index != -1) {
        _sessions[index] = updatedSession;
        notifyListeners();
      }
      
      // Reload sessions to ensure consistency
      await loadChatSessions();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> deleteSession(int sessionId) async {
    _setLoading(true);
    _clearError();

    try {
      await _apiService.deleteChatSession(sessionId);
      
      // Remove the session from the list
      _sessions.removeWhere((s) => s.sessionId == sessionId);
      
      // If the deleted session was the current one, clear current messages
      if (_currentConversationId != null) {
        // Check if we need to clear current messages
        // This is a simple check - you might want to track current session ID separately
        _currentMessages.clear();
        _currentConversationId = null;
      }
      
      notifyListeners();
      
      // Reload sessions to ensure consistency
      await loadChatSessions();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void _setSending(bool sending) {
    _isSending = sending;
    notifyListeners();
  }

  void _setError(String error) {
    _error = error;
    notifyListeners();
  }

  void _clearError() {
    _error = null;
    notifyListeners();
  }

  void clearError() {
    _clearError();
  }
}

