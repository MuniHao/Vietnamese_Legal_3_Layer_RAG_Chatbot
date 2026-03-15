import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  User? _currentUser;
  bool _isLoading = false;
  String? _error;

  User? get currentUser => _currentUser;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _currentUser != null;

  Future<void> login(String email, String password) async {
    _setLoading(true);
    _clearError();

    try {
      final loginRequest = LoginRequest(email: email, password: password);
      final token = await _apiService.login(loginRequest);
      
      await _apiService.saveToken(token.accessToken);
      await _loadCurrentUser();
      
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> register(String email, String password, String fullName, {String? phone}) async {
    _setLoading(true);
    _clearError();

    try {
      final registerRequest = RegisterRequest(
        email: email,
        password: password,
        fullName: fullName,
        phone: phone,
      );
      
      await _apiService.register(registerRequest);
      
      // Auto login after registration
      await login(email, password);
      
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> logout() async {
    _setLoading(true);
    _clearError(); // Clear error when logging out
    
    try {
      await _apiService.clearToken();
      _currentUser = null;
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> checkAuthStatus() async {
    _setLoading(true);
    _clearError(); // Clear any previous error when checking auth status
    
    try {
      final isLoggedIn = await _apiService.isLoggedIn();
      if (isLoggedIn) {
        await _loadCurrentUser();
      } else {
        // Clear error if not logged in
        _clearError();
      }
    } catch (e) {
      _setError(e.toString());
      await _apiService.clearToken();
    } finally {
      _setLoading(false);
    }
  }

  Future<void> updatePreferences({
    String? region,
    List<String>? focusTopics,
    String? language,
  }) async {
    _setLoading(true);
    _clearError();

    try {
      await _apiService.updatePreferences(
        region: region,
        focusTopics: focusTopics,
        language: language,
      );
      
      // Reload user data to get updated preferences
      await _loadCurrentUser();
      
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> updateUserProfile({
    String? fullName,
    String? phone,
  }) async {
    _setLoading(true);
    _clearError();

    try {
      _currentUser = await _apiService.updateUserProfile(
        fullName: fullName,
        phone: phone,
      );
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  Future<void> _loadCurrentUser() async {
    try {
      _currentUser = await _apiService.getCurrentUser();
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
      _currentUser = null;
    }
  }

  void _setLoading(bool loading) {
    _isLoading = loading;
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

