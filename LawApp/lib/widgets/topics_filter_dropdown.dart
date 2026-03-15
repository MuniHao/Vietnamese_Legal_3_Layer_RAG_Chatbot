import 'package:flutter/material.dart';
import '../utils/app_colors.dart';

class TopicsFilterDropdown extends StatelessWidget {
  final int? selectedValue;
  final List<Map<String, dynamic>> items;
  final String hintText;
  final IconData icon;
  final Color iconColor;
  final Function(int?) onChanged;

  const TopicsFilterDropdown({
    super.key,
    required this.selectedValue,
    required this.items,
    required this.hintText,
    required this.icon,
    required this.iconColor,
    required this.onChanged,
  });

  // Helper function to remove "Chủ đề số xx:" or "Đề mục số xx:" prefix
  String _cleanTitle(String? title) {
    if (title == null || title.isEmpty) return 'N/A';
    
    // Remove "Chủ đề số XX:" pattern
    String cleaned = title.replaceAll(RegExp(r'^Chủ đề số\s+\d+:\s*'), '');
    
    // Remove "Đề mục số XX:" pattern
    cleaned = cleaned.replaceAll(RegExp(r'^Đề mục số\s+\d+:\s*'), '');
    
    return cleaned.trim();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40, // Fixed height to make it shorter
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: AppColors.backgroundGray,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: AppColors.borderLight,
          width: 1,
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<int?>(
          value: selectedValue,
          isExpanded: true,
          style: const TextStyle(
            color: AppColors.textWhite,
            fontSize: 14,
          ),
          dropdownColor: AppColors.backgroundGray,
          itemHeight: 48, // Height of each dropdown item (minimum kMinInteractiveDimension)
          menuMaxHeight: 300, // Max height of dropdown menu
          icon: const Icon(
            Icons.arrow_drop_down,
            color: AppColors.textWhite,
            size: 20,
          ),
          hint: Row(
            children: [
              Icon(icon, size: 18, color: AppColors.textWhite),
              const SizedBox(width: 6),
              Text(
                hintText,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textWhite,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          items: [
            DropdownMenuItem<int?>(
              value: null,
              child: Container(
                height: 48, // Item height matching itemHeight
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                child: Row(
                  children: [
                    Icon(icon, size: 18, color: iconColor),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        hintText,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textWhite,
                        ),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            ...items.map((item) {
              final cleanTitle = _cleanTitle(item['title']);
              return DropdownMenuItem<int?>(
                value: item['id'] as int,
                child: Container(
                  height: 48, // Item height matching itemHeight
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                  child: Row(
                    children: [
                      Icon(icon, size: 18, color: iconColor),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          cleanTitle,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w400,
                            color: AppColors.textWhite,
                          ),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
          ],
          onChanged: onChanged,
        ),
      ),
    );
  }
}

