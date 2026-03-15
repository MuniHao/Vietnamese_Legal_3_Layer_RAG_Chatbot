import 'package:flutter/material.dart';
import 'document_item.dart';
import '../utils/app_colors.dart';

class CategoryCard extends StatelessWidget {
  final Map<String, dynamic> category;
  final int topicId;
  final bool isExpanded;
  final List<Map<String, dynamic>> documents;
  final List<Map<String, dynamic>> filteredDocuments;
  final bool isLoading;
  final VoidCallback onToggle;
  final Function(Map<String, dynamic>) onDocumentTap;

  const CategoryCard({
    super.key,
    required this.category,
    required this.topicId,
    required this.isExpanded,
    required this.documents,
    required this.filteredDocuments,
    required this.isLoading,
    required this.onToggle,
    required this.onDocumentTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(
        left: 24,
        right: 0,
        top: 4,
        bottom: 2,
      ),
      decoration: BoxDecoration(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        children: [
          // Đề mục header
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(6),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 10,
              ),
              decoration: BoxDecoration(
                color: Colors.transparent,
                borderRadius: BorderRadius.circular(6),
              ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.folder,
                      color: Color(0xFF2E8B57), // Green for categories
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        category['title'] ?? 'N/A',
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textWhite,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Icon(
                      isExpanded ? Icons.expand_less : Icons.expand_more,
                      color: AppColors.textWhite,
                      size: 18,
                    ),
                  ],
                ),
            ),
          ),
          // Văn bản - Level 3
          if (isExpanded) ...[
            if (isLoading)
              const Padding(
                padding: EdgeInsets.all(20.0),
                child: Center(
                  child: CircularProgressIndicator(
                    valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                  ),
                ),
              )
            else if (filteredDocuments.isEmpty)
              const Padding(
                padding: EdgeInsets.all(20.0),
                child: Center(
                  child: Text(
                    'Không có văn bản',
                    style: TextStyle(
                      color: AppColors.textGray,
                      fontSize: 14,
                    ),
                  ),
                ),
              )
            else
              ...filteredDocuments.map((document) {
                return DocumentItem(
                  document: document,
                  onTap: () => onDocumentTap(document),
                );
              }),
          ],
        ],
      ),
    );
  }
}

