import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';
import '../widgets/topics_filter_section.dart';
import '../widgets/topic_card.dart';
import '../utils/app_colors.dart';
import 'document_viewer_screen.dart';

class TopicsScreen extends StatefulWidget {
  const TopicsScreen({super.key});

  @override
  State<TopicsScreen> createState() => _TopicsScreenState();
}

class _TopicsScreenState extends State<TopicsScreen> {
  final ApiService _apiService = ApiService();
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();
  final Map<int, GlobalKey> _topicKeys = {};
  List<Map<String, dynamic>> _topics = [];
  Map<int, List<Map<String, dynamic>>> _categoriesByTopic = {};
  Map<int, List<Map<String, dynamic>>> _documentsByCategory = {};
  Set<int> _expandedTopics = {};
  Map<int, bool> _expandedCategories = {};
  bool _isLoading = true;
  String? _errorMessage;
  
  // Filter states
  int? _selectedTopicId;
  int? _selectedCategoryId;
  String _searchQuery = '';
  bool _isLoadingSearchData = false;
  
  // Helper function to normalize text for case-insensitive search
  // Handles Vietnamese characters correctly
  String _normalizeText(String text) {
    if (text.isEmpty) return text;
    // Convert to lowercase and trim
    // Dart's toLowerCase() handles Vietnamese characters correctly
    return text.toLowerCase().trim();
  }
  
  // Helper function to check if text contains search query (case-insensitive)
  bool _textContains(String text, String query) {
    if (query.isEmpty) return true;
    final normalizedText = _normalizeText(text);
    final normalizedQuery = _normalizeText(query);
    return normalizedText.contains(normalizedQuery);
  }

  @override
  void initState() {
    super.initState();
    _loadTopics();
    _searchController.addListener(_onSearchChanged);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }
  
  void _onSearchChanged() {
    final newQuery = _normalizeText(_searchController.text);
    final previousQuery = _searchQuery;
    
    setState(() {
      _searchQuery = newQuery;
    });
    
    // If search query is not empty and we haven't loaded all data yet, load it immediately
    // This ensures search can find results in all topics, categories, and documents
    if (newQuery.isNotEmpty && newQuery != previousQuery && !_isLoadingSearchData) {
      _loadAllDataForSearch();
    }
  }
  
  // Load all categories for search functionality
  // Note: We only need to load categories, not documents, since search only filters by topics and categories
  Future<void> _loadAllDataForSearch() async {
    if (_isLoadingSearchData) return; // Already loading
    
    setState(() {
      _isLoadingSearchData = true;
    });
    
    try {
      // Load categories for all topics that haven't been loaded
      final topicsToLoad = _topics.where((topic) {
        final topicId = topic['id'] as int;
        return !_categoriesByTopic.containsKey(topicId);
      }).toList();
      
      // Load all categories in parallel
      await Future.wait(
        topicsToLoad.map((topic) {
          final topicId = topic['id'] as int;
          return _loadCategories(topicId);
        }),
      );
    } finally {
      setState(() {
        _isLoadingSearchData = false;
      });
    }
  }
  
  void _clearFilters() {
    setState(() {
      _selectedTopicId = null;
      _selectedCategoryId = null;
      _searchController.clear();
      _searchQuery = '';
    });
  }

  Future<void> _loadTopics() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final topics = await _apiService.getTopics();
      setState(() {
        _topics = topics;
        // Initialize keys for scroll into view
        for (var topic in topics) {
          _topicKeys[topic['id'] as int] = GlobalKey();
        }
        _isLoading = false;
      });
      
      // Load categories from first few topics to populate filter dropdown
      // This allows showing categories a-d when no topic is selected
      final topicsToLoad = topics.take(10).toList(); // Load from first 10 topics
      for (var topic in topicsToLoad) {
        final topicId = topic['id'] as int;
        _loadCategories(topicId); // Load asynchronously, don't wait
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _loadCategories(int topicId) async {
    if (_categoriesByTopic.containsKey(topicId)) {
      return; // Already loaded
    }

    try {
      final categories = await _apiService.getCategoriesByTopic(topicId);
      setState(() {
        _categoriesByTopic[topicId] = categories;
      });
    } catch (e) {
      print('Error loading categories: $e');
    }
  }

  Future<void> _loadDocuments(int categoryId) async {
    if (_documentsByCategory.containsKey(categoryId)) {
      return; // Already loaded
    }

    try {
      final documents = await _apiService.getDocumentsByCategory(categoryId);
      setState(() {
        _documentsByCategory[categoryId] = documents;
      });
    } catch (e) {
      print('Error loading documents: $e');
    }
  }

  void _toggleTopic(int topicId) {
    setState(() {
      if (_expandedTopics.contains(topicId)) {
        _expandedTopics.remove(topicId);
      } else {
        _expandedTopics.add(topicId);
        _loadCategories(topicId);
        // Auto scroll to expanded topic
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final key = _topicKeys[topicId];
          if (key?.currentContext != null) {
            Scrollable.ensureVisible(
              key!.currentContext!,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOut,
            );
          }
        });
      }
    });
  }

  void _toggleCategory(int categoryId, int topicId) {
    setState(() {
      if (_expandedCategories[categoryId] == true) {
        _expandedCategories[categoryId] = false;
      } else {
        _expandedCategories[categoryId] = true;
        _loadDocuments(categoryId);
      }
    });
  }

  void _openDocument(Map<String, dynamic> document) {
    context.push('/document-viewer/${document['id']}');
  }

  // Get filtered topics based on search and filters
  List<Map<String, dynamic>> _getFilteredTopics() {
    if (_searchQuery.isEmpty && _selectedTopicId == null && _selectedCategoryId == null) {
      return _topics;
    }
    
    return _topics.where((topic) {
      final topicId = topic['id'] as int;
      
      // Filter by selected topic
      if (_selectedTopicId != null && topicId != _selectedTopicId) {
        return false;
      }
      
      // Check if topic title matches search query
      final topicTitle = topic['title'] ?? '';
      bool topicMatchesSearch = _searchQuery.isEmpty || _textContains(topicTitle, _searchQuery);
      
      // Check categories
      final categories = _categoriesByTopic[topicId] ?? [];
      bool hasMatchingCategory = false;
      
      if (_searchQuery.isNotEmpty) {
        for (var category in categories) {
          final categoryId = category['id'] as int;
          
          // Filter by selected category
          if (_selectedCategoryId != null && categoryId != _selectedCategoryId) {
            continue;
          }
          
          // Check if category title matches search
          final categoryTitle = category['title'] ?? '';
          if (_textContains(categoryTitle, _searchQuery)) {
            hasMatchingCategory = true;
            break;
          }
        }
      }
      
      // If filtering by category, only show topics that have that category
      if (_selectedCategoryId != null) {
        final hasSelectedCategory = categories.any((cat) => cat['id'] == _selectedCategoryId);
        if (!hasSelectedCategory) {
          return false;
        }
      }
      
      // Show topic if it matches search in topic title or has matching category
      return topicMatchesSearch || hasMatchingCategory;
    }).toList();
  }
  
  // Get filtered categories for a topic
  List<Map<String, dynamic>> _getFilteredCategories(int topicId) {
    final categories = _categoriesByTopic[topicId] ?? [];
    
    if (_searchQuery.isEmpty && _selectedCategoryId == null) {
      return categories;
    }
    
    return categories.where((category) {
      final categoryId = category['id'] as int;
      
      // Filter by selected category
      if (_selectedCategoryId != null && categoryId != _selectedCategoryId) {
        return false;
      }
      
      // Check if category title matches search query
      if (_searchQuery.isNotEmpty) {
        final categoryTitle = category['title'] ?? '';
        return _textContains(categoryTitle, _searchQuery);
      }
      
      return true; // No search query, show all
    }).toList();
  }
  
  // Get filtered documents for a category
  // Note: Documents are not filtered by search query, all documents are shown
  List<Map<String, dynamic>> _getFilteredDocuments(int categoryId) {
    final documents = _documentsByCategory[categoryId] ?? [];
    // Always return all documents, search only filters topics and categories
    return documents;
  }
  
  // Get all unique categories for filter dropdown
  List<Map<String, dynamic>> _getAllCategories() {
    final allCategories = <Map<String, dynamic>>[];
    
    // If a topic is selected, show only categories from that topic
    if (_selectedTopicId != null) {
      final categories = _categoriesByTopic[_selectedTopicId] ?? [];
      return categories;
    }
    
    // If no topic is selected, show only categories with title starting from a-d
    for (var categories in _categoriesByTopic.values) {
      for (var category in categories) {
        final categoryId = category['id'] as int;
        final title = (category['title'] ?? '').toLowerCase().trim();
        
        // Remove prefix "Đề mục số xx:" if exists
        String cleanTitle = title.replaceAll(RegExp(r'^đề mục số\s+\d+:\s*'), '');
        cleanTitle = cleanTitle.trim();
        
        // Check if title starts with a-d (case insensitive)
        if (cleanTitle.isNotEmpty) {
          final firstChar = cleanTitle[0].toLowerCase();
          if (firstChar.compareTo('a') >= 0 && firstChar.compareTo('d') <= 0) {
            // Check if not already added
            if (!allCategories.any((c) => c['id'] == categoryId)) {
              allCategories.add(category);
            }
          }
        }
      }
    }
    
    return allCategories;
  }

  // Get filtered documents by category map
  Map<int, List<Map<String, dynamic>>> _getFilteredDocumentsByCategory() {
    final filteredMap = <int, List<Map<String, dynamic>>>{};
    for (var categoryId in _documentsByCategory.keys) {
      filteredMap[categoryId] = _getFilteredDocuments(categoryId);
    }
    return filteredMap;
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final horizontalPadding = screenWidth * 0.05;
    final filteredTopics = _getFilteredTopics();
    final allCategories = _getAllCategories();
    final hasActiveFilters = _selectedTopicId != null || 
                            _selectedCategoryId != null || 
                            _searchQuery.isNotEmpty;
    
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      appBar: AppBar(
        title: const Text(
          'BỘ PHÁP ĐIỂN ĐIỆN TỬ',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            color: AppColors.textWhite,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textWhite),
          onPressed: () => context.go('/chat'),
          tooltip: 'Quay lại chat',
        ),
        backgroundColor: AppColors.backgroundBlack,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
              ),
            )
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 64, color: AppColors.errorColor),
                      const SizedBox(height: 16),
                      Text(
                        'Lỗi: $_errorMessage',
                          style: const TextStyle(
                            color: AppColors.errorColor,
                            fontSize: 16,
                          ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadTopics,
                        child: const Text('Thử lại', style: TextStyle(color: AppColors.textWhite)),
                      ),
                    ],
                    ),
                  ),
                )
              : Column(
                            children: [
                    // Search and Filter Section
                    TopicsFilterSection(
                      searchController: _searchController,
                      searchQuery: _searchQuery,
                      onSearchChanged: (value) {
                        setState(() {
                          _searchQuery = value;
                        });
                      },
                      selectedTopicId: _selectedTopicId,
                      selectedCategoryId: _selectedCategoryId,
                      topics: _topics,
                      allCategories: allCategories,
                      onTopicChanged: (value) {
                        setState(() {
                          _selectedTopicId = value;
                          // Reset category filter when topic changes
                          if (value != null) {
                            _selectedCategoryId = null;
                            // Load categories for the selected topic
                            _loadCategories(value);
                          }
                        });
                      },
                      onCategoryChanged: (value) {
                        setState(() {
                          _selectedCategoryId = value;
                        });
                      },
                      onClearFilters: _clearFilters,
                    ),
                    // Loading indicator for search
                    if (_isLoadingSearchData && _searchQuery.isNotEmpty)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        color: AppColors.backgroundGray,
                        child: Row(
                          children: [
                            const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(AppColors.textWhite),
                              ),
                            ),
                            const SizedBox(width: 8),
                            const Text(
                              'Đang tìm kiếm...',
                              style: TextStyle(
                                fontSize: 13,
                                color: AppColors.textWhite,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    // Results count
                    if (hasActiveFilters && !_isLoadingSearchData)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        color: AppColors.backgroundGray,
                        child: Row(
                          children: [
                            const Icon(Icons.filter_list, 
                              size: 16, 
                              color: AppColors.textWhite,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Tìm thấy ${filteredTopics.length} chủ đề',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.textWhite,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    // Topics List
                    Expanded(
                      child: filteredTopics.isEmpty
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(
                                    Icons.search_off,
                                    size: 64,
                                    color: AppColors.textGray,
                                  ),
                                  const SizedBox(height: 16),
                                  const Text(
                                    'Không tìm thấy kết quả',
                                    style: TextStyle(
                                      fontSize: 16,
                                      color: AppColors.textWhite,
                                    ),
                                  ),
                                  if (hasActiveFilters) ...[
                                    const SizedBox(height: 8),
                                    TextButton(
                                      onPressed: _clearFilters,
                                      child: const Text('Xóa bộ lọc', style: TextStyle(color: AppColors.textWhite)),
                                    ),
                                            ],
                                          ],
                                        ),
                            )
                          : ListView.builder(
                              controller: _scrollController,
                              padding: EdgeInsets.symmetric(
                                horizontal: horizontalPadding,
                                vertical: 16,
                              ),
                              itemCount: filteredTopics.length,
                              itemBuilder: (context, index) {
                                final topic = filteredTopics[index];
                                final topicId = topic['id'] as int;
                                final isExpanded = _expandedTopics.contains(topicId);
                                final categories = _categoriesByTopic[topicId] ?? [];
                                final filteredCategories = _getFilteredCategories(topicId);
                                final isLoadingCategories = isExpanded && categories.isEmpty;
                                final filteredDocumentsByCategory = _getFilteredDocumentsByCategory();

                                return TopicCard(
                                  cardKey: _topicKeys[topicId],
                                  topic: topic,
                                  isExpanded: isExpanded,
                                  categories: categories,
                                  filteredCategories: filteredCategories,
                                  isLoadingCategories: isLoadingCategories,
                                  documentsByCategory: _documentsByCategory,
                                  filteredDocumentsByCategory: filteredDocumentsByCategory,
                                  expandedCategories: _expandedCategories,
                                  onToggle: () => _toggleTopic(topicId),
                                  onCategoryToggle: (categoryId, topicId) => _toggleCategory(categoryId, topicId),
                                  onDocumentTap: _openDocument,
                                );
                              },
                            ),
                    ),
                  ],
                    ),
    );
  }
}
