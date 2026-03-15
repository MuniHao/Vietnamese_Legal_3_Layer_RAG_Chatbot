import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../providers/chat_provider.dart';
import '../models/models.dart';
import '../utils/app_colors.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ChatProvider>().loadChatSessions();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      appBar: AppBar(
        title: const Text(
          'Lịch sử chat',
          style: TextStyle(color: AppColors.textWhite),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textWhite),
          onPressed: () => Navigator.of(context).pop(),
        ),
        backgroundColor: AppColors.backgroundBlack,
        elevation: 0,
      ),
      body: Consumer<ChatProvider>(
        builder: (context, chatProvider, _) {
          if (chatProvider.isLoading) {
            return const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
              ),
            );
          }

          if (chatProvider.sessions.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.history,
                    size: 64,
                    color: AppColors.textGray,
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Chưa có cuộc trò chuyện nào',
                    style: TextStyle(
                      fontSize: 18,
                      color: AppColors.textWhite,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Hãy bắt đầu cuộc trò chuyện đầu tiên',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textGray,
                    ),
                  ),
                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: chatProvider.sessions.length,
            itemBuilder: (context, index) {
              final session = chatProvider.sessions[index];
              return _buildSessionCard(context, session);
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          context.read<ChatProvider>().startNewChat();
          Navigator.of(context).pop();
        },
        backgroundColor: AppColors.backgroundGray,
        child: const Icon(Icons.add, color: AppColors.textWhite),
      ),
    );
  }

  Widget _buildSessionCard(BuildContext context, ChatSession session) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: AppColors.backgroundGray,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppColors.backgroundLightGray,
          child: const Icon(
            Icons.chat_bubble_outline,
            color: AppColors.textWhite,
          ),
        ),
        title: Text(
          session.title,
          style: const TextStyle(
            fontWeight: FontWeight.w500,
            color: AppColors.textWhite,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              timeago.format(session.createdAt, locale: 'vi'),
              style: const TextStyle(
                color: AppColors.textGray,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              '${session.messageCount} tin nhắn',
              style: const TextStyle(
                color: AppColors.textGray,
                fontSize: 12,
              ),
            ),
          ],
        ),
        trailing: PopupMenuButton<String>(
          icon: const Icon(Icons.more_vert, color: AppColors.textGray, size: 20),
          color: AppColors.backgroundGray,
          onSelected: (value) {
            if (value == 'edit') {
              _showRenameDialog(context, session);
            } else if (value == 'delete') {
              _showDeleteDialog(context, session);
            }
          },
          itemBuilder: (BuildContext context) => [
            const PopupMenuItem<String>(
              value: 'edit',
              child: Row(
                children: [
                  Icon(Icons.edit_outlined, color: AppColors.textWhite, size: 20),
                  SizedBox(width: 12),
                  Text(
                    'Sửa tên',
                    style: TextStyle(color: AppColors.textWhite),
                  ),
                ],
              ),
            ),
            const PopupMenuItem<String>(
              value: 'delete',
              child: Row(
                children: [
                  Icon(Icons.delete_outline, color: AppColors.errorColor, size: 20),
                  SizedBox(width: 12),
                  Text(
                    'Xóa đoạn chat',
                    style: TextStyle(color: AppColors.errorColor),
                  ),
                ],
              ),
            ),
          ],
        ),
        onTap: () {
          context.read<ChatProvider>().selectSession(session);
          Navigator.of(context).pop();
        },
      ),
    );
  }

  void _showRenameDialog(BuildContext context, ChatSession session) {
    final controller = TextEditingController(text: session.title);
    
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.backgroundGray,
        title: const Text(
          'Đổi tên đoạn chat',
          style: TextStyle(color: AppColors.textWhite),
        ),
        content: TextField(
          controller: controller,
          style: const TextStyle(color: AppColors.textWhite),
          decoration: InputDecoration(
            hintText: 'Nhập tên mới',
            hintStyle: const TextStyle(color: AppColors.textGray),
            filled: true,
            fillColor: AppColors.backgroundLightGray,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: AppColors.borderLight),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: AppColors.borderLight),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: AppColors.textWhite, width: 2),
            ),
          ),
          autofocus: true,
          maxLength: 255,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text(
              'Hủy',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
          TextButton(
            onPressed: () async {
              final newTitle = controller.text.trim();
              if (newTitle.isNotEmpty && newTitle != session.title) {
                await context.read<ChatProvider>().updateSessionTitle(
                  session.sessionId,
                  newTitle,
                );
                if (dialogContext.mounted) {
                  Navigator.of(dialogContext).pop();
                }
              } else if (newTitle.isEmpty) {
                ScaffoldMessenger.of(dialogContext).showSnackBar(
                  const SnackBar(
                    content: Text('Tên không được để trống'),
                    backgroundColor: AppColors.errorColor,
                  ),
                );
              } else {
                Navigator.of(dialogContext).pop();
              }
            },
            child: const Text(
              'Lưu',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(BuildContext context, ChatSession session) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.backgroundGray,
        title: const Text(
          'Xóa đoạn chat',
          style: TextStyle(color: AppColors.textWhite),
        ),
        content: Text(
          'Bạn có chắc chắn muốn xóa đoạn chat "${session.title}"? Hành động này không thể hoàn tác.',
          style: const TextStyle(color: AppColors.textWhite),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text(
              'Hủy',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
          TextButton(
            onPressed: () async {
              await context.read<ChatProvider>().deleteSession(session.sessionId);
              if (dialogContext.mounted) {
                Navigator.of(dialogContext).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Đã xóa đoạn chat'),
                    backgroundColor: AppColors.backgroundGray,
                  ),
                );
              }
            },
            child: const Text(
              'Xóa',
              style: TextStyle(color: AppColors.errorColor),
            ),
          ),
        ],
      ),
    );
  }
}

