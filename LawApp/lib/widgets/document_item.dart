import 'package:flutter/material.dart';
import '../utils/app_colors.dart';

class DocumentItem extends StatelessWidget {
  final Map<String, dynamic> document;
  final VoidCallback onTap;

  const DocumentItem({
    super.key,
    required this.document,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(
        left: 32,
        right: 0,
        bottom: 2,
      ),
      decoration: BoxDecoration(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(4),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(4),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 10,
          ),
          child: Row(
            children: [
              const Icon(
                Icons.description,
                size: 20,
                color: AppColors.textWhite,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  document['title'] ?? 'N/A',
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w400,
                    color: AppColors.textWhite,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(
                Icons.chevron_right,
                size: 20,
                color: AppColors.textGray,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

