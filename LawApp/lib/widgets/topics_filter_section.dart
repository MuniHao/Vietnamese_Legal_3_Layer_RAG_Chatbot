import 'package:flutter/material.dart';
import 'topics_search_bar.dart';
import 'topics_filter_dropdown.dart';
import '../utils/app_colors.dart';

class TopicsFilterSection extends StatelessWidget {
  final TextEditingController searchController;
  final String searchQuery;
  final Function(String) onSearchChanged;
  final int? selectedTopicId;
  final int? selectedCategoryId;
  final List<Map<String, dynamic>> topics;
  final List<Map<String, dynamic>> allCategories;
  final Function(int?) onTopicChanged;
  final Function(int?) onCategoryChanged;
  final VoidCallback onClearFilters;

  const TopicsFilterSection({
    super.key,
    required this.searchController,
    required this.searchQuery,
    required this.onSearchChanged,
    required this.selectedTopicId,
    required this.selectedCategoryId,
    required this.topics,
    required this.allCategories,
    required this.onTopicChanged,
    required this.onCategoryChanged,
    required this.onClearFilters,
  });

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final horizontalPadding = screenWidth * 0.05;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: horizontalPadding,
        vertical: 12,
      ),
      decoration: BoxDecoration(
        color: AppColors.backgroundBlack,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 2,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Search Bar
          TopicsSearchBar(
            controller: searchController,
            searchQuery: searchQuery,
            onChanged: onSearchChanged,
          ),
          const SizedBox(height: 12),
          // Filter Row
          Row(
            children: [
              // Filter by Topic - 1.5x width (flex: 4.5 ≈ 5)
              Flexible(
                flex: 5,
                child: TopicsFilterDropdown(
                  selectedValue: selectedTopicId,
                  items: topics,
                  hintText: 'Tất cả chủ đề',
                  icon: Icons.folder,
                  iconColor: Colors.blue.shade700,
                  onChanged: onTopicChanged,
                ),
              ),
              const SizedBox(width: 4),
              // Filter by Category - 1.5x width (flex: 4.5 ≈ 5)
              Flexible(
                flex: 5,
                child: TopicsFilterDropdown(
                  selectedValue: selectedCategoryId,
                  items: allCategories,
                  hintText: 'Tất cả đề mục',
                  icon: Icons.folder,
                  iconColor: Colors.green.shade700,
                  onChanged: onCategoryChanged,
                ),
              ),
              const SizedBox(width: 4),
              // Clear Filters Button - Always visible, fixed position
              IconButton(
                icon: const Icon(Icons.clear_all, size: 18),
                tooltip: 'Xóa bộ lọc',
                onPressed: onClearFilters,
                constraints: const BoxConstraints(
                  minWidth: 32,
                  minHeight: 32,
                ),
                padding: EdgeInsets.zero,
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.errorColor.withOpacity(0.2),
                  foregroundColor: AppColors.errorColor,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

