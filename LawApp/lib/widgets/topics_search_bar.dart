import 'package:flutter/material.dart';
import '../utils/app_colors.dart';

class TopicsSearchBar extends StatelessWidget {
  final TextEditingController controller;
  final String searchQuery;
  final Function(String) onChanged;

  const TopicsSearchBar({
    super.key,
    required this.controller,
    required this.searchQuery,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      onChanged: (value) => onChanged(value),
      decoration: InputDecoration(
        hintText: 'Tìm kiếm theo chủ đề, đề mục, tên văn bản...',
        hintStyle: const TextStyle(color: AppColors.textGray),
        prefixIcon: const Icon(Icons.search, color: AppColors.textWhite),
        suffixIcon: searchQuery.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.clear, color: AppColors.textWhite),
                onPressed: () {
                  controller.clear();
                  onChanged('');
                },
              )
            : null,
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
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      style: const TextStyle(fontSize: 15, color: AppColors.textWhite),
    );
  }
}

