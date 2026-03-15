import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:io';
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import '../services/api_service.dart';
import '../models/models.dart';
import '../widgets/web_iframe_web.dart' if (dart.library.io) '../widgets/web_iframe_stub.dart';
import '../widgets/mobile_webview_mobile.dart' if (dart.library.html) '../widgets/mobile_webview_stub.dart';

class DocumentViewerScreen extends StatefulWidget {
  final int documentId;

  const DocumentViewerScreen({
    super.key,
    required this.documentId,
  });

  @override
  State<DocumentViewerScreen> createState() => _DocumentViewerScreenState();
}

class _DocumentViewerScreenState extends State<DocumentViewerScreen> {
  final ApiService _apiService = ApiService();
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  Map<String, dynamic>? _document;
  bool _isLoading = true;
  String? _errorMessage;
  bool _useWebView = true;
  bool _isSaved = false;
  List<Map<String, dynamic>> _collections = [];
  List<Map<String, dynamic>> _documentTags = [];
  List<String> _allTags = [];
  bool _loadingCollections = false;

  @override
  void initState() {
    super.initState();
    _loadDocument();
    _checkSavedStatus();
    _loadCollections();
    _loadDocumentTags();
    _loadAllTags();
  }

  Future<void> _loadDocument() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final document = await _apiService.getDocumentById(widget.documentId);
      setState(() {
        _document = {
          'id': document.id,
          'title': document.title,
          'doc_number': document.docNumber,
          'issuing_agency': document.issuingAgency,
          'doc_type': document.docType,
          'effective_date': document.effectiveDate?.toString(),
          'status': document.status,
          'file_url': document.fileUrl,
          'html_content': document.htmlContent,
          'text_content': document.textContent,
        };
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  bool _isPdfFile(String fileUrl) {
    final lowerUrl = fileUrl.toLowerCase();
    return lowerUrl.endsWith('.pdf') && !lowerUrl.endsWith('.pdf.doc');
  }

  bool _isDocxFile(String fileUrl) {
    final lowerUrl = fileUrl.toLowerCase();
    return lowerUrl.endsWith('.docx') ||
        lowerUrl.endsWith('.doc') ||
        lowerUrl.endsWith('.pdf.doc');
  }

  String _getFileViewerUrl(int documentId, String fileUrl) {
    final baseUrl = ApiService.baseUrl;
    if (_isPdfFile(fileUrl)) {
      // For PDF, return direct file URL for Syncfusion viewer
      return '$baseUrl/api/documents/$documentId/file';
    } else if (_isDocxFile(fileUrl)) {
      // For DOC/DOCX, return HTML endpoint
      return '$baseUrl/api/documents/$documentId/file/html';
    }
    return '$baseUrl/api/documents/$documentId/file';
  }
  
  String _getPdfUrl(int documentId) {
    final baseUrl = ApiService.baseUrl;
    return '$baseUrl/api/documents/$documentId/file';
  }

  String _wrapHtmlForWebView(String htmlContent) {
    return '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
  <style>
    * {
      box-sizing: border-box;
    }
    body {
      font-family: "Times New Roman", Arial, sans-serif;
      margin: 0;
      padding: 16px;
      background-color: white;
      color: #000;
      line-height: 1.6;
      font-size: 14px;
    }
    .fulltext {
      width: 100%;
      margin: 0;
      padding: 0;
    }
    .vbInfo {
      margin-bottom: 12px;
    }
    .vbInfo ul {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    .vbInfo li {
      margin-bottom: 4px;
    }
    .vbInfo li.red {
      color: #d32f2f;
    }
    .vbInfo li.green {
      color: #388e3c;
    }
    table {
      border-collapse: collapse;
      margin: 8px 0;
      display: table;
    }
    table[align="left"] {
      float: left !important;
      margin-right: 16px;
      margin-bottom: 8px;
    }
    table[align="right"] {
      float: right !important;
      margin-left: 16px;
      margin-bottom: 8px;
    }
    table[align="center"] {
      margin-left: auto;
      margin-right: auto;
    }
    tbody {
      display: table-row-group;
    }
    tr {
      display: table-row;
    }
    td {
      padding: 5px;
      vertical-align: baseline;
      display: table-cell;
    }
    td[align="center"] {
      text-align: center;
    }
    td[align="left"] {
      text-align: left;
    }
    td[align="right"] {
      text-align: right;
    }
    div {
      margin: 0;
      padding: 0;
    }
    div[style*="clear:both"],
    div[style*="clear: both"] {
      clear: both !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: hidden;
    }
    p {
      margin: 8px 0;
    }
    p[align="center"] {
      text-align: center;
    }
    p[align="left"] {
      text-align: left;
    }
    p[align="right"] {
      text-align: right;
    }
    p[align="justify"] {
      text-align: justify;
    }
    b, strong {
      font-weight: bold;
    }
    i, em {
      font-style: italic;
    }
    a {
      color: #1976d2;
      text-decoration: underline;
    }
    [style] {
      /* Inline styles sẽ được browser parse tự động */
    }
  </style>
</head>
<body>
$htmlContent
</body>
</html>
''';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_document?['title'] ?? 'Văn bản'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            // Quay lại màn hình trước (chat hoặc topics)
            if (context.canPop()) {
              context.pop();
            } else {
              // Nếu không có route trước, quay về chat
              context.go('/chat');
            }
          },
          tooltip: 'Quay lại',
        ),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          // Save button
          IconButton(
            icon: Icon(_isSaved ? Icons.favorite : Icons.favorite_border),
            color: _isSaved ? Colors.red : null,
            onPressed: _showSaveMenu,
            tooltip: 'Lưu văn bản',
          ),
          // Export/Share button
          IconButton(
            icon: const Icon(Icons.more_vert),
            onPressed: _showExportMenu,
            tooltip: 'Xuất & Chia sẻ',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline,
                          size: 64, color: Colors.red.shade300),
                      const SizedBox(height: 16),
                      Text(
                        'Lỗi: $_errorMessage',
                        style: TextStyle(color: Colors.red.shade700),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadDocument,
                        child: const Text('Thử lại'),
                      ),
                    ],
                  ),
                )
              : _document == null
                  ? const Center(child: Text('Không tìm thấy văn bản'))
                  : _buildContent(),
    );
  }

  Widget _buildContent() {
    final fileUrl = _document!['file_url'] as String?;
    final htmlContent = _document!['html_content'] as String?;

    // Có file URL
    if (fileUrl != null && fileUrl.isNotEmpty) {
      final screenWidth = MediaQuery.of(context).size.width;
      final horizontalPadding = screenWidth * 0.04; // 4% mỗi bên
      
      return Column(
        children: [
          // Info card
          Container(
            margin: EdgeInsets.fromLTRB(
              horizontalPadding,
              16,
              horizontalPadding,
              12,
            ),
            child: Card(
              elevation: 1,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(
                  color: Colors.green.shade200,
                  width: 1,
                ),
              ),
              color: Colors.green.shade50,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: _isPdfFile(fileUrl)
                            ? Colors.red.shade100
                            : Colors.blue.shade100,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        _isPdfFile(fileUrl)
                            ? Icons.picture_as_pdf
                            : Icons.description,
                        color: _isPdfFile(fileUrl) ? Colors.red.shade700 : Colors.blue.shade700,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Đang hiển thị từ file',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: Colors.green.shade900,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            fileUrl,
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.green.shade800,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // PDF Viewer or WebView
          Expanded(
            child: _isPdfFile(fileUrl)
                ? _buildPdfViewer() // PDF: full width, no padding
                : Container(
                    margin: EdgeInsets.symmetric(horizontal: horizontalPadding),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: Colors.grey.shade300,
                        width: 1,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.grey.shade200,
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: kIsWeb
                          ? _buildWebViewer(_getFileViewerUrl(
                              widget.documentId, fileUrl))
                          : _buildMobileWebView(_getFileViewerUrl(
                              widget.documentId, fileUrl)),
                    ),
                  ),
          ),
        ],
      );
    }

    // Có HTML content
    if (htmlContent != null && htmlContent.isNotEmpty) {
      final screenWidth = MediaQuery.of(context).size.width;
      final horizontalPadding = screenWidth * 0.04; // 4% mỗi bên
      
      return Column(
        children: [
          // Toggle WebView
          Container(
            margin: EdgeInsets.fromLTRB(
              horizontalPadding,
              16,
              horizontalPadding,
              12,
            ),
            child: Card(
              elevation: 1,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 14,
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.settings_outlined,
                      size: 20,
                      color: Colors.grey.shade700,
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        'WebView (chính xác hơn)',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    Switch(
                      value: _useWebView,
                      onChanged: (value) {
                        setState(() {
                          _useWebView = value;
                        });
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
          // Content
          Expanded(
            child: Container(
              margin: EdgeInsets.symmetric(horizontal: horizontalPadding),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Colors.grey.shade300,
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.grey.shade200,
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: _useWebView
                  ? kIsWeb
                      ? _buildWebViewer(
                          Uri.dataFromString(
                            _wrapHtmlForWebView(htmlContent),
                            mimeType: 'text/html',
                            encoding: Encoding.getByName('utf-8'),
                          ).toString(),
                        )
                      : _buildMobileWebView(
                          Uri.dataFromString(
                            _wrapHtmlForWebView(htmlContent),
                            mimeType: 'text/html',
                            encoding: Encoding.getByName('utf-8'),
                          ).toString(),
                        )
                  : SingleChildScrollView(
                      child: Text(
                        htmlContent,
                        style: const TextStyle(
                          fontSize: 15,
                          height: 1.6,
                        ),
                      ),
                    ),
            ),
          ),
        ],
      );
    }

    // Không có file và không có HTML content
    return Center(
      child: Card(
        margin: const EdgeInsets.all(16),
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.info_outline,
                  size: 64, color: Colors.orange.shade300),
              const SizedBox(height: 16),
              Text(
                'Không có file về văn bản này',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Văn bản này không có file đính kèm hoặc nội dung HTML.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWebViewer(String url) {
    if (kIsWeb) {
      return WebIframe(url: url);
    }
    return _buildMobileWebView(url);
  }

  Widget _buildMobileWebView(String url) {
    if (kIsWeb) {
      return _buildWebViewer(url);
    }
    return MobileWebView(url: url);
  }
  
  Widget _buildPdfViewer() {
    final pdfUrl = _getPdfUrl(widget.documentId);
    
    // Syncfusion PDF viewer works with network URLs
    return FutureBuilder<Map<String, String>>(
      future: _getAuthHeaders(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        
        return SfPdfViewer.network(
          pdfUrl,
          headers: snapshot.data ?? {},
          onDocumentLoadFailed: (PdfDocumentLoadFailedDetails details) {
            // Log error
            print('PDF load failed: ${details.error}');
            print('Description: ${details.description}');
          },
        );
      },
    );
  }
  
  Future<Map<String, String>> _getAuthHeaders() async {
    // Get auth token from secure storage if needed
    final token = await _storage.read(key: 'auth_token');
    if (token != null) {
      return {'Authorization': 'Bearer $token'};
    }
    return {};
  }

  Future<void> _checkSavedStatus() async {
    try {
      final isSaved = await _apiService.isDocumentSaved(widget.documentId);
      if (mounted) {
        setState(() {
          _isSaved = isSaved;
        });
      }
    } catch (e) {
      // User might not be logged in, ignore error
      print('Error checking saved status: $e');
    }
  }

  Future<void> _loadCollections() async {
    try {
      setState(() => _loadingCollections = true);
      final collections = await _apiService.getCollections();
      if (mounted) {
        setState(() {
          _collections = collections;
          _loadingCollections = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loadingCollections = false);
      }
      print('Error loading collections: $e');
    }
  }

  Future<void> _loadDocumentTags() async {
    try {
      final tags = await _apiService.getDocumentTags(widget.documentId);
      if (mounted) {
        setState(() {
          _documentTags = tags;
        });
      }
    } catch (e) {
      print('Error loading tags: $e');
    }
  }

  Future<void> _loadAllTags() async {
    try {
      final tags = await _apiService.getAllTags();
      if (mounted) {
        setState(() {
          _allTags = tags;
        });
      }
    } catch (e) {
      print('Error loading all tags: $e');
    }
  }

  Future<void> _toggleSave() async {
    try {
      if (_isSaved) {
        await _apiService.unsaveDocument(widget.documentId);
        if (mounted) {
          setState(() => _isSaved = false);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Đã bỏ lưu văn bản')),
          );
        }
      } else {
        await _apiService.saveDocument(widget.documentId);
        if (mounted) {
          setState(() => _isSaved = true);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Đã lưu văn bản')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: ${e.toString()}')),
        );
      }
    }
  }

  void _showSaveMenu() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => ListView(
          controller: scrollController,
          padding: const EdgeInsets.all(16),
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Lưu văn bản',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Save to favorites
            ListTile(
              leading: Icon(
                _isSaved ? Icons.favorite : Icons.favorite_border,
                color: _isSaved ? Colors.red : null,
              ),
              title: Text(_isSaved ? 'Đã lưu vào yêu thích' : 'Lưu vào yêu thích'),
              onTap: () {
                _toggleSave();
                Navigator.pop(context);
              },
            ),
            const Divider(),
            // Collections section
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                'Thêm vào bộ sưu tập',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (_loadingCollections)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              )
            else ...[
              ListTile(
                leading: const Icon(Icons.create_new_folder),
                title: const Text('Tạo bộ sưu tập mới'),
                onTap: () {
                  Navigator.pop(context);
                  _showCreateCollectionDialog();
                },
              ),
              ..._collections.map((collection) {
                return ListTile(
                  leading: Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: collection['color'] != null
                          ? Color(int.parse(collection['color'].replaceFirst('#', '0xFF')))
                          : Colors.blue,
                      shape: BoxShape.circle,
                    ),
                  ),
                  title: Text(collection['name']),
                  subtitle: Text('${collection['document_count']} văn bản'),
                  onTap: () {
                    _addToCollection(collection['id']);
                    Navigator.pop(context);
                  },
                );
              }),
            ],
            const Divider(),
            // Tags section
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                'Tags',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ..._documentTags.map((tag) => Chip(
                        label: Text(tag['tag_name']),
                        deleteIcon: const Icon(Icons.close, size: 18),
                        onDeleted: () {
                          _removeTag(tag['tag_name']);
                        },
                      )),
                  ActionChip(
                    avatar: const Icon(Icons.add, size: 18),
                    label: const Text('Thêm tag'),
                    onPressed: () {
                      Navigator.pop(context);
                      _showAddTagDialog();
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16), // Extra padding at bottom
          ],
        ),
      ),
    );
  }

  void _showCreateCollectionDialog() {
    final nameController = TextEditingController();
    final descriptionController = TextEditingController();
    String selectedColor = '#2196F3';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Tạo bộ sưu tập mới'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: 'Tên bộ sưu tập',
                  hintText: 'Ví dụ: Lao động, Đất đai',
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: descriptionController,
                decoration: const InputDecoration(
                  labelText: 'Mô tả (tùy chọn)',
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 16),
              const Text('Màu sắc:'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  '#2196F3', '#F44336', '#4CAF50', '#FF9800', '#9C27B0', '#00BCD4'
                ].map((color) {
                  return GestureDetector(
                    onTap: () {
                      setDialogState(() => selectedColor = color);
                    },
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: Color(int.parse(color.replaceFirst('#', '0xFF'))),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: selectedColor == color ? Colors.black : Colors.transparent,
                          width: 3,
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Hủy'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (nameController.text.trim().isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Vui lòng nhập tên bộ sưu tập')),
                  );
                  return;
                }
                try {
                  await _apiService.createCollection(
                    name: nameController.text.trim(),
                    description: descriptionController.text.trim().isEmpty
                        ? null
                        : descriptionController.text.trim(),
                    color: selectedColor,
                  );
                  await _loadCollections();
                  if (mounted) {
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Đã tạo bộ sưu tập')),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Lỗi: ${e.toString()}')),
                    );
                  }
                }
              },
              child: const Text('Tạo'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _addToCollection(int collectionId) async {
    try {
      await _apiService.addDocumentToCollection(
        collectionId: collectionId,
        documentId: widget.documentId,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Đã thêm vào bộ sưu tập')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: ${e.toString()}')),
        );
      }
    }
  }

  void _showAddTagDialog() {
    final tagController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Thêm tag'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: tagController,
              decoration: const InputDecoration(
                labelText: 'Tên tag',
                hintText: 'Ví dụ: Quan trọng, Cần xem lại',
              ),
              autofocus: true,
            ),
            if (_allTags.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text('Tags đã có:', style: TextStyle(fontSize: 12)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: _allTags
                    .where((tag) => !_documentTags.any((dt) => dt['tag_name'] == tag))
                    .take(10)
                    .map((tag) => ActionChip(
                          label: Text(tag),
                          onPressed: () {
                            tagController.text = tag;
                          },
                        ))
                    .toList(),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Hủy'),
          ),
          ElevatedButton(
            onPressed: () async {
              if (tagController.text.trim().isEmpty) {
                return;
              }
              try {
                await _apiService.addTagToDocument(
                  documentId: widget.documentId,
                  tagName: tagController.text.trim(),
                );
                await _loadDocumentTags();
                await _loadAllTags();
                if (mounted) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Đã thêm tag')),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Lỗi: ${e.toString()}')),
                  );
                }
              }
            },
            child: const Text('Thêm'),
          ),
        ],
      ),
    );
  }

  Future<void> _removeTag(String tagName) async {
    try {
      await _apiService.removeTagFromDocument(
        documentId: widget.documentId,
        tagName: tagName,
      );
      await _loadDocumentTags();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Đã xóa tag')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: ${e.toString()}')),
        );
      }
    }
  }

  void _showExportMenu() {
    final fileUrl = _document?['file_url'] as String?;
    final bool hasPdf = fileUrl != null && _isPdfFile(fileUrl);
    final bool hasDocx = fileUrl != null && _isDocxFile(fileUrl);
    
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Xuất & Chia sẻ',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          // Chỉ hiển thị "Xuất PDF" nếu file là PDF
          if (hasPdf)
            ListTile(
              leading: const Icon(Icons.picture_as_pdf, color: Colors.red),
              title: const Text('Xuất PDF'),
              onTap: () => _exportDocument('pdf'),
            ),
          // Chỉ hiển thị "Xuất DOCX" nếu file là DOCX/DOC
          if (hasDocx)
            ListTile(
              leading: const Icon(Icons.description, color: Colors.blue),
              title: const Text('Xuất DOCX'),
              onTap: () => _exportDocument('docx'),
            ),
          // Nếu không có file hoặc không phải PDF/DOCX, hiển thị thông báo
          if (!hasPdf && !hasDocx && fileUrl == null)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                'Không có file để xuất',
                style: TextStyle(
                  color: Colors.grey,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          // Chia sẻ link luôn hiển thị
          if (hasPdf || hasDocx || fileUrl == null) const Divider(),
          ListTile(
            leading: const Icon(Icons.share),
            title: const Text('Chia sẻ link'),
            onTap: () => _shareDocument(),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Future<void> _exportDocument(String format) async {
    try {
      Navigator.pop(context);
      
      // Show loading
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đang tải file...'),
            duration: Duration(seconds: 2),
          ),
        );
      }

      final response = await _apiService.exportDocument(
        documentId: widget.documentId,
        format: format,
      );

      // Sanitize file name - remove invalid characters
      String title = _document?['title'] ?? 'document';
      // Remove invalid characters for file names: / \ : * ? " < > |
      title = title.replaceAll(RegExp(r'[\/\\:\*\?"<>\|]'), '_');
      // Limit length to avoid path issues
      if (title.length > 100) {
        title = title.substring(0, 100);
      }

      // Save file to temporary directory
      final tempDir = await getTemporaryDirectory();
      final fileName = '${title}_${widget.documentId}.$format';
      final filePath = '${tempDir.path}/$fileName';
      
      // Ensure directory exists
      if (!await tempDir.exists()) {
        await tempDir.create(recursive: true);
      }

      // Write file
      final file = File(filePath);
      await file.writeAsBytes(response.data);

      // Verify file was created
      if (!await file.exists()) {
        throw Exception('File không được tạo thành công');
      }

      // Share file
      await Share.shareXFiles(
        [XFile(filePath)],
        subject: title,
        text: 'Văn bản: $title',
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đã xuất file thành công'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Lỗi xuất file: ${e.toString()}'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }
      print('Export error: $e');
    }
  }

  Future<void> _shareDocument() async {
    try {
      Navigator.pop(context);
      final shareData = await _apiService.getShareLink(widget.documentId);
      final shareUrl = shareData['share_url'] as String;

      await Share.share(
        '${_document?['title'] ?? 'Văn bản'}\n$shareUrl',
        subject: _document?['title'] ?? 'Văn bản',
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi chia sẻ: ${e.toString()}')),
        );
      }
    }
  }
}

