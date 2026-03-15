import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'providers/auth_provider.dart';
import 'providers/chat_provider.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/history_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/topics_screen.dart';
import 'screens/document_viewer_screen.dart';
import 'screens/saved_documents_screen.dart';
import 'utils/app_theme.dart';

void main() {
  runApp(const LawApp());
}

class LawApp extends StatelessWidget {
  const LawApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
      ],
      child: Consumer<AuthProvider>(
        builder: (context, authProvider, _) {
          return MaterialApp.router(
            debugShowCheckedModeBanner: false,
            title: 'LegalMate - Trợ lý pháp lý AI',
            theme: AppTheme.lightTheme,
            routerConfig: _router,
          );
        },
      ),
    );
  }
}

final GoRouter _router = GoRouter(
  initialLocation: '/splash',
  routes: [
    GoRoute(
      path: '/splash',
      builder: (context, state) => const SplashScreen(),
    ),
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/register',
      builder: (context, state) => const RegisterScreen(),
    ),
    GoRoute(
      path: '/chat',
      builder: (context, state) => const ChatScreen(),
    ),
    GoRoute(
      path: '/history',
      builder: (context, state) => const HistoryScreen(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsScreen(),
    ),
    GoRoute(
      path: '/topics',
      builder: (context, state) => const TopicsScreen(),
    ),
    GoRoute(
      path: '/document-viewer/:id',
      builder: (context, state) {
        final idParam = state.pathParameters['id'];
        if (idParam == null) {
          // Redirect to topics if id is missing
          return const TopicsScreen();
        }
        final id = int.tryParse(idParam);
        if (id == null) {
          // Redirect to topics if id is invalid
          return const TopicsScreen();
        }
        return DocumentViewerScreen(documentId: id);
      },
    ),
    GoRoute(
      path: '/saved-documents',
      builder: (context, state) => const SavedDocumentsScreen(),
    ),
  ],
  redirect: (context, state) {
    final authProvider = context.read<AuthProvider>();
    final isLoggedIn = authProvider.isLoggedIn;
    final isLoading = authProvider.isLoading;
    final currentPath = state.uri.path;
    
    // Don't redirect while loading
    if (isLoading) return null;
    
    // Allow access to public routes
    final publicRoutes = ['/login', '/register', '/splash'];
    final isPublicRoute = publicRoutes.contains(currentPath);
    
    // Allow access to document-viewer (can be accessed when logged in)
    final isDocumentViewer = currentPath.startsWith('/document-viewer/');
    
    // Redirect to login if not authenticated and not on public route or document viewer
    if (!isLoggedIn && !isPublicRoute && !isDocumentViewer) {
      return '/login';
    }
    
    // Redirect to chat if authenticated and on splash/login/register
    if (isLoggedIn && (currentPath == '/splash' || currentPath == '/login' || currentPath == '/register')) {
      return '/chat';
    }
    
    return null;
  },
);
