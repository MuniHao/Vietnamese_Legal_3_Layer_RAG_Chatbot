import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../utils/app_colors.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkAuthStatus();
  }

  Future<void> _checkAuthStatus() async {
    // Đảm bảo splash screen hiển thị ít nhất 2 giây
    final minimumDisplayTime = Future.delayed(const Duration(seconds: 2));
    
    final authProvider = context.read<AuthProvider>();
    final authCheck = authProvider.checkAuthStatus();
    
    // Chờ cả hai: auth check và minimum display time
    await Future.wait([authCheck, minimumDisplayTime]);
    
    if (mounted) {
      // Navigation will be handled by GoRouter redirect
      context.go('/chat');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // App logo/icon
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: AppColors.backgroundGray,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.3),
                    blurRadius: 10,
                    offset: const Offset(0, 5),
                  ),
                ],
              ),
              child: const Icon(
                Icons.gavel,
                size: 60,
                color: AppColors.textWhite,
              ),
            ),
            
            const SizedBox(height: 30),
            
            // App name
            const Text(
              'Law App',
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: AppColors.textWhite,
              ),
            ),
            
            const SizedBox(height: 10),
            
            // App description
            const Text(
              'AI-powered legal consultation',
              style: TextStyle(
                fontSize: 16,
                color: AppColors.textGray,
              ),
            ),
            
            const SizedBox(height: 50),
            
            // Loading indicator
            const CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
            ),
            
            const SizedBox(height: 20),
            
            const Text(
              'Đang tải...',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textGray,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
