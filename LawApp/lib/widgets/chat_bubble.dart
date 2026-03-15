import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:timeago/timeago.dart' as timeago;
import 'package:go_router/go_router.dart';
import '../models/models.dart';
import '../utils/app_colors.dart';

class ChatBubble extends StatelessWidget {
  final ChatMessage message;

  const ChatBubble({
    super.key,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == 'user';
    
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.85,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser ? AppColors.userBubble : Colors.transparent,
                borderRadius: BorderRadius.circular(20).copyWith(
                  bottomLeft: isUser ? const Radius.circular(20) : const Radius.circular(4),
                  bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(20),
                ),
                boxShadow: isUser ? [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.3),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ] : null,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Show loading indicator if message is processing
                  if (message.isProcessing)
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 16,
                          height: 16,
                          child: const CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              AppColors.textWhite,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            message.messageText,
                            style: TextStyle(
                              color: isUser ? AppColors.textDark : AppColors.textBlack,
                              fontSize: 16,
                              height: 1.5,
                              fontFamily: 'Inter',
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ),
                      ],
                    )
                  else
                    _buildRichText(
                      context,
                      message.messageText,
                      isUser: isUser,
                    ),
                  
                  if (!message.isProcessing) ...[
                    const SizedBox(height: 4),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          timeago.format(message.createdAt, locale: 'vi'),
                          style: TextStyle(
                            color: isUser 
                                ? AppColors.textGray 
                                : AppColors.textGray,
                            fontSize: 12,
                            fontFamily: 'Inter',
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _getConfidenceColor(double confidence) {
    if (confidence >= 0.8) return AppColors.successColor;
    if (confidence >= 0.6) return AppColors.warningColor;
    return AppColors.errorColor;
  }

  /// Build rich text with tap handling for links and tables
  Widget _buildRichText(BuildContext context, String text, {required bool isUser}) {
    // Check if text contains markdown tables
    // Pattern: | header | header |\n| --- | --- |\n| data | data |
    final tableRegex = RegExp(
      r'\|[^\n]+\|\s*\n\|[\s\-:]+\|\s*\n(?:\|[^\n]+\|\s*\n?)+',
      multiLine: true,
    );
    final matches = tableRegex.allMatches(text);
    
    if (matches.isEmpty) {
      // No tables, use simple text rendering
      return SelectableText.rich(
        _parseMarkdown(context, text, isUser: isUser),
        style: const TextStyle(
          color: AppColors.textWhite,
          fontSize: 16,
          height: 1.5,
          fontFamily: 'Inter',
        ),
      );
    }
    
    // Has tables, need to split and render mixed content
    final List<Widget> widgets = [];
    int lastIndex = 0;
    
    for (final match in matches) {
      // Add text before table
      if (match.start > lastIndex) {
        final beforeText = text.substring(lastIndex, match.start);
        if (beforeText.trim().isNotEmpty) {
          widgets.add(
            SelectableText.rich(
              _parseMarkdown(context, beforeText, isUser: isUser),
              style: const TextStyle(
                color: AppColors.textWhite,
                fontSize: 16,
                height: 1.5,
                fontFamily: 'Inter',
              ),
            ),
          );
          widgets.add(const SizedBox(height: 12));
        }
      }
      
      // Parse and render table
      final tableText = match.group(0)!;
      final tableWidget = _buildTable(context, tableText, isUser: isUser);
      if (tableWidget != null) {
        widgets.add(tableWidget);
        widgets.add(const SizedBox(height: 12));
      }
      
      lastIndex = match.end;
    }
    
    // Add remaining text after last table
    if (lastIndex < text.length) {
      final afterText = text.substring(lastIndex);
      if (afterText.trim().isNotEmpty) {
        widgets.add(
          SelectableText.rich(
            _parseMarkdown(context, afterText, isUser: isUser),
            style: const TextStyle(
              color: AppColors.textWhite,
              fontSize: 16,
              height: 1.5,
              fontFamily: 'Inter',
            ),
          ),
        );
      }
    }
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }
  
  /// Parse markdown table and build Flutter Table widget
  Widget? _buildTable(BuildContext context, String tableText, {required bool isUser}) {
    final lines = tableText.split('\n').where((line) => line.trim().isNotEmpty).toList();
    if (lines.length < 2) return null;
    
    // Parse header (first line)
    final headerLine = lines[0];
    final headerCells = _parseTableRow(headerLine);
    
    if (headerCells.isEmpty) return null;
    
    // Skip separator line (lines[1] - contains dashes)
    // Parse data rows (starting from line 2)
    final List<List<String>> rows = [];
    for (int i = 2; i < lines.length; i++) {
      final rowCells = _parseTableRow(lines[i]);
      if (rowCells.isNotEmpty) {
        rows.add(rowCells);
      }
    }
    
    // Build table
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.backgroundGray,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.borderLight,
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Table(
          border: TableBorder(
            horizontalInside: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
            verticalInside: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
            top: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
            bottom: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
            left: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
            right: BorderSide(
              color: AppColors.borderLight.withOpacity(0.4),
              width: 1,
            ),
          ),
          columnWidths: Map.fromIterable(
            List.generate(headerCells.length, (index) => index),
            value: (_) => const FlexColumnWidth(1),
          ),
          children: [
            // Header row
            TableRow(
              decoration: BoxDecoration(
                color: AppColors.backgroundLightGray.withOpacity(0.6),
              ),
              children: headerCells.map((cell) {
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  child: Text(
                    cell,
                    style: const TextStyle(
                      color: AppColors.textWhite,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      fontFamily: 'Inter',
                      height: 1.4,
                    ),
                  ),
                );
              }).toList(),
            ),
            // Data rows
            ...rows.asMap().entries.map((entry) {
              final index = entry.key;
              final row = entry.value;
              // Pad row if needed to match header length
              final paddedRow = List<String>.from(row);
              while (paddedRow.length < headerCells.length) {
                paddedRow.add('');
              }
              return TableRow(
                decoration: BoxDecoration(
                  color: index % 2 == 0 
                      ? AppColors.backgroundGray.withOpacity(0.3)
                      : AppColors.backgroundGray,
                ),
                children: paddedRow.take(headerCells.length).map((cell) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    child: Text(
                      cell,
                      style: const TextStyle(
                        color: AppColors.textWhite,
                        fontSize: 15,
                        fontFamily: 'Inter',
                        height: 1.4,
                      ),
                    ),
                  );
                }).toList(),
              );
            }),
          ],
        ),
      ),
    );
  }
  
  /// Parse a table row (split by | and trim)
  List<String> _parseTableRow(String row) {
    return row.split('|')
        .map((cell) => cell.trim())
        .where((cell) => cell.isNotEmpty)
        .toList();
  }

  /// Parse markdown text and convert to TextSpan with formatting
  TextSpan _parseMarkdown(BuildContext context, String text, {required bool isUser}) {
    const textColor = AppColors.textWhite;
    final List<TextSpan> spans = [];
    
    // Process text character by character to handle nested markdown
    int i = 0;
    while (i < text.length) {
      // Check for bold **text**
      if (i < text.length - 1 && text[i] == '*' && text[i + 1] == '*') {
        final endIndex = text.indexOf('**', i + 2);
        if (endIndex != -1) {
          final boldText = text.substring(i + 2, endIndex);
          spans.add(TextSpan(
            text: boldText,
            style: TextStyle(
              color: textColor,
              fontSize: 16,
              fontWeight: FontWeight.bold,
              fontFamily: 'Inter',
            ),
          ));
          i = endIndex + 2;
          continue;
        }
      }
      
      // Check for italic *text* (only if not part of **)
      if (text[i] == '*' && (i == 0 || text[i - 1] != '*') && 
          (i == text.length - 1 || text[i + 1] != '*')) {
        final endIndex = text.indexOf('*', i + 1);
        if (endIndex != -1 && (endIndex == text.length - 1 || text[endIndex + 1] != '*')) {
          final italicText = text.substring(i + 1, endIndex);
          spans.add(TextSpan(
            text: italicText,
            style: TextStyle(
              color: textColor,
              fontSize: 16,
              fontStyle: FontStyle.italic,
              fontFamily: 'Inter',
            ),
          ));
          i = endIndex + 1;
          continue;
        }
      }
      
      // Check for links [text](url)
      if (text[i] == '[') {
        final linkEnd = text.indexOf(']', i);
        if (linkEnd != -1 && linkEnd < text.length - 1 && text[linkEnd + 1] == '(') {
          final urlEnd = text.indexOf(')', linkEnd + 2);
          if (urlEnd != -1) {
            final linkText = text.substring(i + 1, linkEnd);
            final url = text.substring(linkEnd + 2, urlEnd);
            
            // Check if it's a lawchat://document/{id} link
            if (url.startsWith('lawchat://document/')) {
              final documentIdStr = url.replaceFirst('lawchat://document/', '');
              final documentId = int.tryParse(documentIdStr);
              
              if (documentId != null) {
                // Add tap recognizer for navigation
                spans.add(TextSpan(
                  text: linkText,
                  style: const TextStyle(
                    color: AppColors.accentCyan,
                    fontSize: 16,
                    decoration: TextDecoration.underline,
                    fontFamily: 'Inter',
                  ),
                  recognizer: TapGestureRecognizer()
                    ..onTap = () {
                      // Navigate to document viewer
                      context.go('/document-viewer/$documentId');
                    },
                ));
              } else {
                // Invalid document ID, show as regular text
                spans.add(TextSpan(
                  text: linkText,
                  style: const TextStyle(
                    color: textColor,
                    fontSize: 16,
                    fontFamily: 'Inter',
                  ),
                ));
              }
            } else {
              // Regular URL link (external)
              spans.add(TextSpan(
                text: linkText,
                style: const TextStyle(
                  color: AppColors.accentCyan,
                  fontSize: 16,
                  decoration: TextDecoration.underline,
                  fontFamily: 'Inter',
                ),
                recognizer: TapGestureRecognizer()
                  ..onTap = () {
                    // Open external URL (if needed, can use url_launcher)
                    // For now, just show as clickable
                  },
              ));
            }
            i = urlEnd + 1;
            continue;
          }
        }
      }
      
      // Regular text - find the next markdown character
      int nextMarkdown = text.length;
      for (int j = i; j < text.length; j++) {
        if (text[j] == '*' || text[j] == '[') {
          nextMarkdown = j;
          break;
        }
      }
      
      if (nextMarkdown > i) {
        spans.add(TextSpan(
          text: text.substring(i, nextMarkdown),
          style: TextStyle(
            color: textColor,
            fontSize: 16,
            fontFamily: 'Inter',
          ),
        ));
        i = nextMarkdown;
      } else {
        i++;
      }
    }
    
    // If no spans created, return plain text
    if (spans.isEmpty) {
      return TextSpan(
        text: text,
        style: TextStyle(
          color: textColor,
          fontSize: 16,
          fontFamily: 'Inter',
        ),
      );
    }
    
    return TextSpan(children: spans);
  }
}
