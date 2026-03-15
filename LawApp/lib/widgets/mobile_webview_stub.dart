import 'package:flutter/material.dart';

/// Widget stub cho web platform (WebView không hỗ trợ web)
class MobileWebView extends StatelessWidget {
  final String url;

  const MobileWebView({
    super.key,
    required this.url,
  });

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text('WebView chỉ hỗ trợ trên mobile platforms'),
    );
  }
}




