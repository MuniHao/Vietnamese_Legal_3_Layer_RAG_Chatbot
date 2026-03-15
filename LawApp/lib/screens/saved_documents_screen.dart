import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';
import '../models/models.dart';
import '../utils/app_colors.dart';
import 'document_viewer_screen.dart';

class SavedDocumentsScreen extends StatefulWidget {
  const SavedDocumentsScreen({super.key});

  @override
  State<SavedDocumentsScreen> createState() => _SavedDocumentsScreenState();
}

class _SavedDocumentsScreenState extends State<SavedDocumentsScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  late TabController _tabController;

  // Saved Documents
  List<SavedDocument> _savedDocuments = [];
  bool _loadingSaved = false;

  // Collections
  List<Collection> _collections = [];
  bool _loadingCollections = false;
  Map<int, List<CollectionDocument>> _collectionDocuments = {};
  Map<int, bool> _loadingCollectionDocs = {};

  // Tags
  List<String> _allTags = [];
  bool _loadingTags = false;
  Map<String, List<Map<String, dynamic>>> _tagDocuments = {};
  Map<String, bool> _loadingTagDocs = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadSavedDocuments();
    _loadCollections();
    _loadAllTags();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadSavedDocuments() async {
    setState(() => _loadingSaved = true);
    try {
      final response = await _apiService.getSavedDocuments();
      final docs = (response['documents'] as List)
          .map((json) => SavedDocument.fromJson(json))
          .toList();
      setState(() {
        _savedDocuments = docs;
        _loadingSaved = false;
      });
    } catch (e) {
      setState(() => _loadingSaved = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi tải văn bản đã lưu: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _loadCollections() async {
    setState(() => _loadingCollections = true);
    try {
      final collections = await _apiService.getCollections();
      setState(() {
        _collections = collections.map((json) => Collection.fromJson(json)).toList();
        _loadingCollections = false;
      });
    } catch (e) {
      setState(() => _loadingCollections = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi tải bộ sưu tập: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _loadCollectionDocuments(int collectionId) async {
    setState(() => _loadingCollectionDocs[collectionId] = true);
    try {
      final response = await _apiService.getCollectionDocuments(
        collectionId: collectionId,
      );
      final docs = (response['documents'] as List)
          .map((json) => CollectionDocument.fromJson(json))
          .toList();
      setState(() {
        _collectionDocuments[collectionId] = docs;
        _loadingCollectionDocs[collectionId] = false;
      });
    } catch (e) {
      setState(() => _loadingCollectionDocs[collectionId] = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi tải văn bản: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _loadAllTags() async {
    setState(() => _loadingTags = true);
    try {
      final tags = await _apiService.getAllTags();
      setState(() {
        _allTags = tags;
        _loadingTags = false;
      });
    } catch (e) {
      setState(() => _loadingTags = false);
    }
  }

  Future<void> _loadTagDocuments(String tagName) async {
    setState(() => _loadingTagDocs[tagName] = true);
    try {
      final response = await _apiService.getDocumentsByTag(tagName: tagName);
      setState(() {
        _tagDocuments[tagName] = List<Map<String, dynamic>>.from(response['documents']);
        _loadingTagDocs[tagName] = false;
      });
    } catch (e) {
      setState(() => _loadingTagDocs[tagName] = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi tải văn bản: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _deleteCollection(int collectionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.backgroundGray,
        title: const Text(
          'Xác nhận xóa',
          style: TextStyle(color: AppColors.textWhite),
        ),
        content: const Text(
          'Bạn có chắc chắn muốn xóa bộ sưu tập này?',
          style: TextStyle(color: AppColors.textWhite),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text(
              'Hủy',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.errorColor),
            child: const Text(
              'Xóa',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _apiService.deleteCollection(collectionId);
        await _loadCollections();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Đã xóa bộ sưu tập')),
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
  }

  void _showCreateCollectionDialog() {
    final nameController = TextEditingController();
    final descriptionController = TextEditingController();
    String selectedColor = '#2196F3';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: AppColors.backgroundGray,
          title: const Text(
            'Tạo bộ sưu tập mới',
            style: TextStyle(color: AppColors.textWhite),
          ),
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
              child: const Text(
                'Hủy',
                style: TextStyle(color: AppColors.textWhite),
              ),
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
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.backgroundLightGray),
              child: const Text(
                'Tạo',
                style: TextStyle(color: AppColors.textWhite),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      appBar: AppBar(
        title: const Text(
          'Văn bản đã lưu',
          style: TextStyle(color: AppColors.textWhite),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textWhite),
          onPressed: () => context.go('/chat'),
          tooltip: 'Quay lại',
        ),
        backgroundColor: AppColors.backgroundBlack,
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.textWhite,
          unselectedLabelColor: AppColors.textGray,
          indicatorColor: AppColors.textWhite,
          tabs: const [
            Tab(icon: Icon(Icons.favorite), text: 'Yêu thích'),
            Tab(icon: Icon(Icons.folder), text: 'Bộ sưu tập'),
            Tab(icon: Icon(Icons.label), text: 'Tags'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSavedDocumentsTab(),
          _buildCollectionsTab(),
          _buildTagsTab(),
        ],
      ),
    );
  }

  Widget _buildSavedDocumentsTab() {
    if (_loadingSaved) {
      return const Center(
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
        ),
      );
    }

    if (_savedDocuments.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.favorite_border, size: 64, color: AppColors.textGray),
            const SizedBox(height: 16),
            const Text(
              'Chưa có văn bản yêu thích',
              style: TextStyle(color: AppColors.textGray),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadSavedDocuments,
      child: ListView.builder(
        itemCount: _savedDocuments.length,
        itemBuilder: (context, index) {
          final doc = _savedDocuments[index];
          return ListTile(
            leading: const Icon(Icons.description, color: AppColors.textWhite),
            title: Text(
              doc.title,
              style: const TextStyle(color: AppColors.textWhite),
            ),
            subtitle: Text(
              'Lưu ngày: ${_formatDate(doc.savedAt)}',
              style: const TextStyle(fontSize: 12, color: AppColors.textGray),
            ),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: AppColors.textWhite),
              onPressed: () async {
                try {
                  await _apiService.unsaveDocument(doc.documentId);
                  await _loadSavedDocuments();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Đã bỏ lưu')),
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
            ),
            onTap: () {
              context.push('/document-viewer/${doc.documentId}');
            },
          );
        },
      ),
    );
  }

  Widget _buildCollectionsTab() {
    if (_loadingCollections) {
      return const Center(
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
        ),
      );
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            onPressed: _showCreateCollectionDialog,
            icon: const Icon(Icons.add, color: AppColors.textWhite),
            label: const Text(
              'Tạo bộ sưu tập mới',
              style: TextStyle(color: AppColors.textWhite),
            ),
            style: ElevatedButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              backgroundColor: AppColors.backgroundGray,
            ),
          ),
        ),
        Expanded(
          child: _collections.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.folder_outlined, size: 64, color: AppColors.textGray),
                      const SizedBox(height: 16),
                      const Text(
                        'Chưa có bộ sưu tập',
                        style: TextStyle(color: AppColors.textGray),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _collections.length,
                  itemBuilder: (context, index) {
                    final collection = _collections[index];
                    final isExpanded = _collectionDocuments.containsKey(collection.id);
                    final isLoading = _loadingCollectionDocs[collection.id] ?? false;

                    return ExpansionTile(
                      leading: Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: collection.color != null
                              ? Color(int.parse(collection.color!.replaceFirst('#', '0xFF')))
                              : Colors.blue,
                          shape: BoxShape.circle,
                        ),
                      ),
                      title: Text(
                        collection.name,
                        style: const TextStyle(color: AppColors.textWhite),
                      ),
                      subtitle: Text(
                        '${collection.documentCount} văn bản',
                        style: const TextStyle(color: AppColors.textGray),
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.delete_outline, size: 20, color: AppColors.textWhite),
                            onPressed: () => _deleteCollection(collection.id),
                          ),
                        ],
                      ),
                      onExpansionChanged: (expanded) {
                        if (expanded && !isExpanded) {
                          _loadCollectionDocuments(collection.id);
                        }
                      },
                      children: [
                        if (isLoading)
                          const Padding(
                            padding: EdgeInsets.all(16),
                            child: Center(child: CircularProgressIndicator()),
                          )
                        else if (isExpanded)
                          ...(_collectionDocuments[collection.id] ?? []).map((doc) {
                            return ListTile(
                              leading: const Icon(Icons.description, size: 20, color: AppColors.textWhite),
                              title: Text(
                                doc.title,
                                style: const TextStyle(color: AppColors.textWhite),
                              ),
                              subtitle: doc.notes != null
                                  ? Text(
                                      'Ghi chú: ${doc.notes}',
                                      style: const TextStyle(fontSize: 12, color: AppColors.textGray),
                                    )
                                  : null,
                              onTap: () {
                                context.push('/document-viewer/${doc.id}');
                              },
                            );
                          }).toList(),
                      ],
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildTagsTab() {
    if (_loadingTags) {
      return const Center(
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
        ),
      );
    }

    if (_allTags.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.label_outline, size: 64, color: AppColors.textGray),
            const SizedBox(height: 16),
            const Text(
              'Chưa có tags',
              style: TextStyle(color: AppColors.textGray),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: _allTags.length,
      itemBuilder: (context, index) {
        final tag = _allTags[index];
        final isExpanded = _tagDocuments.containsKey(tag);
        final isLoading = _loadingTagDocs[tag] ?? false;

        return ExpansionTile(
          leading: const Icon(Icons.label, color: AppColors.textWhite),
          title: Text(
            tag,
            style: const TextStyle(color: AppColors.textWhite),
          ),
          subtitle: Text(
            '${_tagDocuments[tag]?.length ?? 0} văn bản',
            style: const TextStyle(color: AppColors.textGray),
          ),
          onExpansionChanged: (expanded) {
            if (expanded && !isExpanded) {
              _loadTagDocuments(tag);
            }
          },
          children: [
            if (isLoading)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(
                  child: CircularProgressIndicator(
                    valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                  ),
                ),
              )
            else if (isExpanded)
              ...(_tagDocuments[tag] ?? []).map((doc) {
                return ListTile(
                  leading: const Icon(Icons.description, size: 20, color: AppColors.textWhite),
                  title: Text(
                    doc['title'] ?? '',
                    style: const TextStyle(color: AppColors.textWhite),
                  ),
                  subtitle: Text(
                    doc['doc_number'] ?? doc['doc_type'] ?? '',
                    style: const TextStyle(fontSize: 12, color: AppColors.textGray),
                  ),
                  onTap: () {
                    context.push('/document-viewer/${doc['id']}');
                  },
                );
              }).toList(),
          ],
        );
      },
    );
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year}';
  }
}
