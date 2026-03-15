import 'package:flutter/material.dart';
import 'category_card.dart';
import '../utils/app_colors.dart';

class TopicCard extends StatelessWidget {
  final Map<String, dynamic> topic;
  final Key? cardKey;
  final bool isExpanded;
  final List<Map<String, dynamic>> categories;
  final List<Map<String, dynamic>> filteredCategories;
  final bool isLoadingCategories;
  final Map<int, List<Map<String, dynamic>>> documentsByCategory;
  final Map<int, List<Map<String, dynamic>>> filteredDocumentsByCategory;
  final Map<int, bool> expandedCategories;
  final VoidCallback onToggle;
  final Function(int, int) onCategoryToggle;
  final Function(Map<String, dynamic>) onDocumentTap;

  const TopicCard({
    super.key,
    required this.topic,
    this.cardKey,
    required this.isExpanded,
    required this.categories,
    required this.filteredCategories,
    required this.isLoadingCategories,
    required this.documentsByCategory,
    required this.filteredDocumentsByCategory,
    required this.expandedCategories,
    required this.onToggle,
    required this.onCategoryToggle,
    required this.onDocumentTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      key: cardKey,
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          // Chủ đề - Level 1
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(8),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 14,
              ),
              decoration: BoxDecoration(
                color: Colors.transparent,
                borderRadius: BorderRadius.circular(8),
              ),
                child: Row(
                  children: [
                    Icon(
                      isExpanded ? Icons.folder_open : Icons.folder,
                      color: const Color(0xFF2E5AAC), // Blue for topics
                      size: 24,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        topic['title'] ?? 'N/A',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textWhite,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Icon(
                      isExpanded ? Icons.expand_less : Icons.expand_more,
                      color: AppColors.textWhite,
                      size: 20,
                    ),
                  ],
                ),
              ),
            ),
            // Đề mục - Level 2
            if (isExpanded) ...[
              if (isLoadingCategories)
                const Padding(
                  padding: EdgeInsets.all(20.0),
                  child: Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                    ),
                  ),
                )
              else
                ...filteredCategories.map((category) {
                  final categoryId = category['id'] as int;
                  final isCategoryExpanded = expandedCategories[categoryId] ?? false;
                  final documents = documentsByCategory[categoryId] ?? [];
                  final filteredDocuments = filteredDocumentsByCategory[categoryId] ?? [];

                  return CategoryCard(
                    category: category,
                    topicId: topic['id'] as int,
                    isExpanded: isCategoryExpanded,
                    documents: documents,
                    filteredDocuments: filteredDocuments,
                    isLoading: false,
                    onToggle: () => onCategoryToggle(categoryId, topic['id'] as int),
                    onDocumentTap: onDocumentTap,
                  );
                }),
            ],
          ],
        ),
    );
  }
}

