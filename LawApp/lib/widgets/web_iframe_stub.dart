import 'package:flutter/material.dart';

/// Widget stub cho non-web platforms
class WebIframe extends StatelessWidget {
  final String url;
  final double? width;
  final double? height;

  const WebIframe({
    super.key,
    required this.url,
    this.width,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text('Iframe chỉ hỗ trợ trên web platform'),
    );
  }
}




