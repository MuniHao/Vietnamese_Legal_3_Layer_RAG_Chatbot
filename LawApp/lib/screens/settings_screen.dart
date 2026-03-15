import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../utils/app_colors.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isEditingProfile = false;
  

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _loadUserData() {
    final authProvider = context.read<AuthProvider>();
    final user = authProvider.currentUser;
    
    if (user != null) {
      _fullNameController.text = user.fullName;
      _phoneController.text = user.phone ?? '';
    }
  }

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    final authProvider = context.read<AuthProvider>();
    await authProvider.updateUserProfile(
      fullName: _fullNameController.text.trim(),
      phone: _phoneController.text.trim().isNotEmpty ? _phoneController.text.trim() : null,
    );

    if (mounted) {
      setState(() {
        _isEditingProfile = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Đã cập nhật thông tin cá nhân'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundBlack,
      appBar: AppBar(
        title: const Text(
          'Cài đặt',
          style: TextStyle(color: AppColors.textWhite),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textWhite),
          onPressed: () => context.go('/chat'),
        ),
        backgroundColor: AppColors.backgroundBlack,
        elevation: 0,
      ),
      body: Consumer<AuthProvider>(
        builder: (context, authProvider, _) {
          final user = authProvider.currentUser;
          
          if (user == null) {
            return const Center(
              child: Text(
                'Không thể tải thông tin người dùng',
                style: TextStyle(color: AppColors.textWhite),
              ),
            );
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // User info section
                  Card(
                    color: AppColors.backgroundGray,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                'Thông tin tài khoản',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textWhite,
                                ),
                              ),
                              IconButton(
                                icon: Icon(
                                  _isEditingProfile ? Icons.close : Icons.edit,
                                  color: AppColors.textWhite,
                                ),
                                onPressed: () {
                                  setState(() {
                                    _isEditingProfile = !_isEditingProfile;
                                    if (!_isEditingProfile) {
                                      // Reset to original values
                                      _fullNameController.text = user.fullName;
                                      _phoneController.text = user.phone ?? '';
                                    }
                                  });
                                },
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          if (_isEditingProfile) ...[
                            TextFormField(
                              controller: _fullNameController,
                              style: const TextStyle(color: AppColors.textWhite),
                              decoration: InputDecoration(
                                labelText: 'Họ và tên',
                                labelStyle: const TextStyle(color: AppColors.textGray),
                                prefixIcon: const Icon(Icons.person, color: AppColors.textWhite),
                                filled: true,
                                fillColor: AppColors.backgroundLightGray,
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
                              ),
                              validator: (value) {
                                if (value == null || value.isEmpty) {
                                  return 'Vui lòng nhập họ và tên';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: 16),
                            TextFormField(
                              controller: _phoneController,
                              style: const TextStyle(color: AppColors.textWhite),
                              keyboardType: TextInputType.phone,
                              decoration: InputDecoration(
                                labelText: 'Số điện thoại',
                                labelStyle: const TextStyle(color: AppColors.textGray),
                                prefixIcon: const Icon(Icons.phone, color: AppColors.textWhite),
                                filled: true,
                                fillColor: AppColors.backgroundLightGray,
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
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: _saveProfile,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.backgroundLightGray,
                                ),
                                child: const Text(
                                  'Lưu thông tin',
                                  style: TextStyle(color: AppColors.textWhite),
                                ),
                              ),
                            ),
                          ] else ...[
                            ListTile(
                              leading: const Icon(Icons.person, color: AppColors.textWhite),
                              title: const Text(
                                'Họ và tên',
                                style: TextStyle(color: AppColors.textWhite),
                              ),
                              subtitle: Text(
                                user.fullName,
                                style: const TextStyle(color: AppColors.textGray),
                              ),
                              contentPadding: EdgeInsets.zero,
                            ),
                            ListTile(
                              leading: const Icon(Icons.email, color: AppColors.textWhite),
                              title: const Text(
                                'Email',
                                style: TextStyle(color: AppColors.textWhite),
                              ),
                              subtitle: Text(
                                user.email,
                                style: const TextStyle(color: AppColors.textGray),
                              ),
                              contentPadding: EdgeInsets.zero,
                            ),
                            ListTile(
                              leading: const Icon(Icons.phone, color: AppColors.textWhite),
                              title: const Text(
                                'Số điện thoại',
                                style: TextStyle(color: AppColors.textWhite),
                              ),
                              subtitle: Text(
                                user.phone ?? 'Chưa có',
                                style: const TextStyle(color: AppColors.textGray),
                              ),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Actions section
                  Card(
                    color: AppColors.backgroundGray,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Hành động',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textWhite,
                            ),
                          ),
                          const SizedBox(height: 16),
                          
                          ListTile(
                            leading: const Icon(Icons.favorite, color: AppColors.textWhite),
                            title: const Text(
                              'Văn bản đã lưu',
                              style: TextStyle(color: AppColors.textWhite),
                            ),
                            subtitle: const Text(
                              'Yêu thích, Bộ sưu tập, Tags',
                              style: TextStyle(color: AppColors.textGray),
                            ),
                            onTap: () => context.go('/saved-documents'),
                            contentPadding: EdgeInsets.zero,
                            trailing: const Icon(Icons.chevron_right, color: AppColors.textWhite),
                          ),
                          
                          const SizedBox(height: 8),
                          
                          ListTile(
                            leading: const Icon(Icons.logout, color: AppColors.errorColor),
                            title: const Text(
                              'Đăng xuất',
                              style: TextStyle(color: AppColors.errorColor),
                            ),
                            onTap: () => _showLogoutDialog(),
                            contentPadding: EdgeInsets.zero,
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 32),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.backgroundGray,
        title: const Text(
          'Đăng xuất',
          style: TextStyle(color: AppColors.textWhite),
        ),
        content: const Text(
          'Bạn có chắc chắn muốn đăng xuất?',
          style: TextStyle(color: AppColors.textWhite),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text(
              'Hủy',
              style: TextStyle(color: AppColors.textWhite),
            ),
          ),
          TextButton(
            onPressed: () async {
              Navigator.of(context).pop();
              await context.read<AuthProvider>().logout();
              if (context.mounted) {
                context.go('/login');
              }
            },
            child: const Text(
              'Đăng xuất',
              style: TextStyle(color: AppColors.errorColor),
            ),
          ),
        ],
      ),
    );
  }
}

