import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../providers/chat_provider.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/quick_suggestions.dart';
import '../utils/app_colors.dart';
import '../models/models.dart';
import 'history_screen.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();
  
  @override
  void initState() {
    super.initState();
    _loadChatSessions();
    _messageController.addListener(() {
      setState(() {}); // Rebuild when text changes to show/hide send button
    });
  }


  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _loadChatSessions() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ChatProvider>().loadChatSessions();
    });
  }

  void _sendMessage() {
    final message = _messageController.text.trim();
    if (message.isEmpty) return;

    _messageController.clear();
    // Use streaming method for real-time response
    context.read<ChatProvider>().sendMessageStream(message);
    
    // Scroll to bottom
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _navigateToHistory() {
    Navigator.of(context).push(
      PageRouteBuilder(
        pageBuilder: (context, animation, secondaryAnimation) => const HistoryScreen(),
        transitionsBuilder: (context, animation, secondaryAnimation, child) {
          // Slide từ bên trái (x = -1.0) vào giữa (x = 0.0)
          const begin = Offset(-1.0, 0.0);
          const end = Offset.zero;
          const curve = Curves.easeInOut;

          var tween = Tween(begin: begin, end: end).chain(
            CurveTween(curve: curve),
          );

          return SlideTransition(
            position: animation.drive(tween),
            child: child,
          );
        },
        reverseTransitionDuration: const Duration(milliseconds: 300),
        transitionDuration: const Duration(milliseconds: 300),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        elevation: 0,
        flexibleSpace: Container(
          decoration: const BoxDecoration(
            gradient: AppColors.appBarGradient,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.history_outlined),
          tooltip: 'Lịch sử chat',
          onPressed: () => _navigateToHistory(),
          color: AppColors.textWhite,
        ),
        title: const Text(
          'LegalMate',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 22,
            letterSpacing: -0.5,
            color: AppColors.textWhite,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline),
            tooltip: 'Chat mới',
            onPressed: () {
              context.read<ChatProvider>().startNewChat();
            },
            color: AppColors.textWhite,
          ),
          IconButton(
            icon: const Icon(Icons.folder_outlined),
            tooltip: 'Xem Topics',
            onPressed: () => context.go('/topics'),
            color: AppColors.textWhite,
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Cài đặt',
            onPressed: () => context.go('/settings'),
            color: AppColors.textWhite,
          ),
        ],
      ),
      body: Column(
        children: [
          // Quick suggestions
          const QuickSuggestions(),
          
          // Chat messages
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, _) {
                if (chatProvider.isLoading && chatProvider.currentMessages.isEmpty) {
                  return const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                    ),
                  );
                }

                if (chatProvider.currentMessages.isEmpty) {
                  return SingleChildScrollView(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        minHeight: MediaQuery.of(context).size.height - 
                                  MediaQuery.of(context).padding.top - 
                                  kToolbarHeight - 
                                  (MediaQuery.of(context).viewInsets.bottom > 0 
                                    ? MediaQuery.of(context).viewInsets.bottom 
                                    : 0),
                      ),
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 32),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                width: 120,
                                height: 120,
                                decoration: BoxDecoration(
                                  gradient: AppColors.primaryGradient,
                                  shape: BoxShape.circle,
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppColors.backgroundGray.withOpacity(0.5),
                                      blurRadius: 20,
                                      offset: const Offset(0, 10),
                                    ),
                                  ],
                                ),
                                child: const Icon(
                                  Icons.balance,
                                  size: 60,
                                  color: AppColors.textWhite,
                                ),
                              ),
                              const SizedBox(height: 32),
                              Text(
                                'Chào mừng đến với LegalMate',
                                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                  color: AppColors.textWhite,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 12),
                              Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 32),
                                child: Text(
                                  'Trợ lý pháp lý AI 24/7 cho mọi người Việt Nam',
                                  textAlign: TextAlign.center,
                                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                                    color: AppColors.textGray,
                                    height: 1.6,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 24),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                                decoration: BoxDecoration(
                                  color: AppColors.backgroundGray,
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: AppColors.borderLight,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const Icon(
                                      Icons.lightbulb_outline,
                                      color: AppColors.accentGold,
                                      size: 20,
                                    ),
                                    const SizedBox(width: 8),
                                    Flexible(
                                      child: Text(
                                        'Chọn một chủ đề bên trên để bắt đầu',
                                        style: const TextStyle(
                                          color: AppColors.textWhite,
                                          fontSize: 14,
                                          fontFamily: 'Inter',
                                        ),
                                        textAlign: TextAlign.center,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                }

                // Auto-scroll when messages change (especially during streaming)
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (_scrollController.hasClients) {
                    // Use jumpTo for smoother streaming experience
                    if (chatProvider.isSending) {
                      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
                    } else {
                      _scrollController.animateTo(
                        _scrollController.position.maxScrollExtent,
                        duration: const Duration(milliseconds: 300),
                        curve: Curves.easeOut,
                      );
                    }
                  }
                });

                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: chatProvider.currentMessages.length,
                  itemBuilder: (context, index) {
                    final message = chatProvider.currentMessages[index];
                    return ChatBubble(message: message);
                  },
                );
              },
            ),
          ),
          
          // Error message
          Consumer<ChatProvider>(
            builder: (context, chatProvider, _) {
              if (chatProvider.error != null) {
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.errorColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: AppColors.errorColor.withOpacity(0.5),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.error_outline_rounded,
                        color: AppColors.errorColor,
                        size: 24,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          chatProvider.error!,
                          style: const TextStyle(
                            color: AppColors.errorColor,
                            fontFamily: 'Inter',
                            fontSize: 14,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(
                          Icons.close_rounded,
                          color: AppColors.errorColor,
                          size: 20,
                        ),
                        onPressed: () => chatProvider.clearError(),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                    ],
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),
          
          // Message input
          SafeArea(
            bottom: true,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.backgroundBlack,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.3),
                    blurRadius: 10,
                    offset: const Offset(0, -2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  // Text input
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: AppColors.backgroundGray,
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(
                          color: AppColors.borderLight,
                          width: 1,
                        ),
                      ),
                      child: TextField(
                        controller: _messageController,
                        style: const TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 15,
                          color: AppColors.textWhite,
                        ),
                        decoration: InputDecoration(
                          hintText: 'Nhập câu hỏi pháp lý của bạn…',
                          hintStyle: const TextStyle(
                            color: AppColors.textGray,
                            fontFamily: 'Inter',
                          ),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 20,
                            vertical: 14,
                          ),
                        ),
                        maxLines: null,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                  ),

                  const SizedBox(width: 8),

                  // Send button - only show when text is entered
                  if (_messageController.text.trim().isNotEmpty)
                    Consumer<ChatProvider>(
                      builder: (context, chatProvider, _) {
                        return Container(
                          decoration: BoxDecoration(
                            gradient: chatProvider.isSending
                                ? null
                                : AppColors.primaryGradient,
                            color: chatProvider.isSending
                                ? AppColors.textGray.withOpacity(0.3)
                                : null,
                            shape: BoxShape.circle,
                            boxShadow: chatProvider.isSending
                                ? null
                                : [
                                    BoxShadow(
                                      color: AppColors.backgroundGray.withOpacity(0.5),
                                      blurRadius: 8,
                                      offset: const Offset(0, 4),
                                    ),
                                  ],
                          ),
                          child: IconButton(
                            icon: chatProvider.isSending
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        AppColors.textWhite,
                                      ),
                                    ),
                                  )
                                : const Icon(
                                    Icons.send_rounded,
                                    color: AppColors.textWhite,
                                  ),
                            onPressed: chatProvider.isSending ? null : _sendMessage,
                            tooltip: 'Gửi',
                          ),
                        );
                      },
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

}
