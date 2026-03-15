import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/chat_provider.dart';
import '../utils/app_colors.dart';

class QuickSuggestions extends StatelessWidget {
  const QuickSuggestions({super.key});

  final List<String> _suggestions = const [
    'Tư vấn đất đai',
    'Ly hôn & hôn nhân',
    'Tranh chấp hợp đồng',
    'Thừa kế',
    'Lao động & tiền lương',
    'Khiếu nại hành chính',
    'Bảo hiểm xã hội',
    'Thuế & tài chính',
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.backgroundBlack,
        border: Border(
          bottom: BorderSide(
            color: AppColors.borderLight,
            width: 1,
          ),
        ),
      ),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: _suggestions.length,
        itemBuilder: (context, index) {
          final suggestion = _suggestions[index];
          return Padding(
            padding: const EdgeInsets.only(right: 10),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () {
                  context.read<ChatProvider>().selectTopic(suggestion);
                },
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.backgroundGray,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: AppColors.borderLight,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _getIconForSuggestion(suggestion),
                        size: 16,
                        color: AppColors.textWhite,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        suggestion,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textWhite,
                          fontFamily: 'Inter',
                        ),
                        softWrap: false,
                        overflow: TextOverflow.visible,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  IconData _getIconForSuggestion(String suggestion) {
    if (suggestion.contains('đất đai')) return Icons.home;
    if (suggestion.contains('hôn nhân') || suggestion.contains('Ly hôn')) return Icons.favorite;
    if (suggestion.contains('hợp đồng')) return Icons.description;
    if (suggestion.contains('Thừa kế')) return Icons.account_balance;
    if (suggestion.contains('Lao động')) return Icons.work;
    if (suggestion.contains('hành chính')) return Icons.gavel;
    if (suggestion.contains('Bảo hiểm')) return Icons.health_and_safety;
    if (suggestion.contains('Thuế')) return Icons.account_balance_wallet;
    return Icons.help_outline;
  }
}

