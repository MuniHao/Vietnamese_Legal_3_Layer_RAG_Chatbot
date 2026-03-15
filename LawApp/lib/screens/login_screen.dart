import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../providers/auth_provider.dart';
import '../utils/app_colors.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _rememberMe = false;
  final _storage = const FlutterSecureStorage();
  static const String _rememberedEmailKey = 'remembered_email';
  static const String _rememberedPasswordKey = 'remembered_password';
  static const String _rememberMeKey = 'remember_me';

  @override
  void initState() {
    super.initState();
    _loadRememberedCredentials();
    // Clear any previous error when entering login screen
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<AuthProvider>().clearError();
      }
    });
  }

  Future<void> _loadRememberedCredentials() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final rememberMe = prefs.getBool(_rememberMeKey) ?? false;
      
      if (rememberMe) {
        final email = prefs.getString(_rememberedEmailKey);
        final password = await _storage.read(key: _rememberedPasswordKey);
        
        if (mounted) {
          setState(() {
            _rememberMe = true;
            if (email != null) {
              _emailController.text = email;
            }
            if (password != null) {
              _passwordController.text = password;
            }
          });
        }
      }
    } catch (e) {
      // Ignore errors when loading credentials
      debugPrint('Error loading remembered credentials: $e');
    }
  }

  Future<void> _saveRememberedCredentials() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      
      if (_rememberMe) {
        await prefs.setBool(_rememberMeKey, true);
        await prefs.setString(_rememberedEmailKey, _emailController.text.trim());
        await _storage.write(
          key: _rememberedPasswordKey,
          value: _passwordController.text,
        );
      } else {
        await prefs.setBool(_rememberMeKey, false);
        await prefs.remove(_rememberedEmailKey);
        await _storage.delete(key: _rememberedPasswordKey);
      }
    } catch (e) {
      debugPrint('Error saving remembered credentials: $e');
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    // Save remembered credentials
    await _saveRememberedCredentials();

    final authProvider = context.read<AuthProvider>();
    await authProvider.login(
      _emailController.text.trim(),
      _passwordController.text,
    );

    if (authProvider.isLoggedIn && mounted) {
      context.go('/chat');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 40),
              
              // Logo and title
              Center(
                child: Column(
                  children: [
                    Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        color: AppColors.backgroundGray,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(
                        Icons.balance,
                        size: 40,
                        color: AppColors.textWhite,
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Đăng nhập',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textWhite,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Chào mừng bạn quay trở lại',
                      style: TextStyle(
                        fontSize: 16,
                        color: AppColors.textGray,
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 40),
              
              // Login form
              Form(
                key: _formKey,
                child: Column(
                  children: [
                    // Email field
                    TextFormField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      style: const TextStyle(color: AppColors.textWhite),
                      decoration: InputDecoration(
                        labelText: 'Email',
                        labelStyle: const TextStyle(color: AppColors.textGray),
                        prefixIcon: const Icon(Icons.email_outlined, color: AppColors.textWhite),
                        hintText: 'Nhập email của bạn',
                        hintStyle: const TextStyle(color: AppColors.textGray),
                        filled: true,
                        fillColor: AppColors.backgroundGray,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.borderLight),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.borderLight),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.textWhite, width: 2),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Vui lòng nhập email';
                        }
                        if (!RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(value)) {
                          return 'Email không hợp lệ';
                        }
                        return null;
                      },
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Password field
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      style: const TextStyle(color: AppColors.textWhite),
                      decoration: InputDecoration(
                        labelText: 'Mật khẩu',
                        labelStyle: const TextStyle(color: AppColors.textGray),
                        prefixIcon: const Icon(Icons.lock_outlined, color: AppColors.textWhite),
                        hintText: 'Nhập mật khẩu của bạn',
                        hintStyle: const TextStyle(color: AppColors.textGray),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility : Icons.visibility_off,
                            color: AppColors.textWhite,
                          ),
                          onPressed: () {
                            setState(() {
                              _obscurePassword = !_obscurePassword;
                            });
                          },
                        ),
                        filled: true,
                        fillColor: AppColors.backgroundGray,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.borderLight),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.borderLight),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.textWhite, width: 2),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Vui lòng nhập mật khẩu';
                        }
                        if (value.length < 6) {
                          return 'Mật khẩu phải có ít nhất 6 ký tự';
                        }
                        return null;
                      },
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Remember me checkbox
                    Row(
                      children: [
                        Checkbox(
                          value: _rememberMe,
                          fillColor: WidgetStateProperty.resolveWith((states) {
                            if (states.contains(WidgetState.selected)) {
                              return AppColors.backgroundGray;
                            }
                            return null;
                          }),
                          checkColor: AppColors.textWhite,
                          onChanged: (value) {
                            setState(() {
                              _rememberMe = value ?? false;
                            });
                          },
                        ),
                        const Text(
                          'Ghi nhớ đăng nhập',
                          style: TextStyle(color: AppColors.textWhite),
                        ),
                      ],
                    ),
                    
                    const SizedBox(height: 24),
                    
                    // Login button
                    Consumer<AuthProvider>(
                      builder: (context, authProvider, _) {
                        return SizedBox(
                          width: double.infinity,
                          height: 50,
                          child: ElevatedButton(
                            onPressed: authProvider.isLoading ? null : _login,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.backgroundGray,
                              foregroundColor: AppColors.textWhite,
                            ),
                            child: authProvider.isLoading
                                ? const SizedBox(
                                    width: 24,
                                    height: 24,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2.5,
                                      valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                                    ),
                                  )
                                : const Text(
                                    'Đăng nhập',
                                    style: TextStyle(fontSize: 16, color: AppColors.textWhite),
                                  ),
                          ),
                        );
                      },
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Error message
                    Consumer<AuthProvider>(
                      builder: (context, authProvider, _) {
                        if (authProvider.error != null) {
                          return Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.errorColor.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AppColors.errorColor.withOpacity(0.5)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: AppColors.errorColor),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    authProvider.error!,
                                    style: const TextStyle(color: AppColors.errorColor),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }
                        return const SizedBox.shrink();
                      },
                    ),
                    
                    const SizedBox(height: 24),
                    
                    // Register link
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          'Chưa có tài khoản? ',
                          style: TextStyle(color: AppColors.textGray),
                        ),
                        TextButton(
                          onPressed: () => context.go('/register'),
                          child: const Text(
                            'Đăng ký ngay',
                            style: TextStyle(color: AppColors.textWhite),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

