import 'package:flutter/material.dart';
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

/// Widget để hiển thị iframe trên web platform
class WebIframe extends StatefulWidget {
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
  State<WebIframe> createState() => _WebIframeState();
}

class _WebIframeState extends State<WebIframe> {
  String? _errorMessage;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _checkUrl();
  }

  void _checkUrl() async {
    try {
      // Kiểm tra URL có hợp lệ không
      final uri = Uri.parse(widget.url);
      if (uri.scheme.isEmpty) {
        setState(() {
          _errorMessage = 'URL không hợp lệ';
          _isLoading = false;
        });
        return;
      }

      // Thử fetch để kiểm tra file có tồn tại không
      try {
        final response = await html.HttpRequest.request(
          widget.url,
          method: 'HEAD',
        );
        
        final status = response.status ?? 0;
        if (status >= 400) {
          setState(() {
            _errorMessage = 'Không thể tải file (Status: $status)';
            _isLoading = false;
          });
          return;
        }
      } catch (e) {
        // Nếu HEAD request fail, vẫn thử load trong iframe
        // (một số server không support HEAD)
        // ignore: avoid_print
        print('HEAD request failed, will try loading in iframe: $e');
      }

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Lỗi: $e';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_errorMessage != null) {
      return Container(
        width: widget.width ?? double.infinity,
        height: widget.height ?? 400,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.red.shade50,
          border: Border.all(color: Colors.red.shade300),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, color: Colors.red.shade700, size: 48),
            const SizedBox(height: 16),
            Text(
              'Lỗi khi tải file',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.red.shade900,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage!,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.red.shade800),
            ),
            const SizedBox(height: 16),
            Text(
              'URL: ${widget.url}',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
                fontFamily: 'monospace',
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    if (_isLoading) {
      return Container(
        width: widget.width ?? double.infinity,
        height: widget.height ?? 400,
        alignment: Alignment.center,
        child: const CircularProgressIndicator(),
      );
    }

    // Tạo unique ID cho iframe
    final String iframeId = 'iframe-${DateTime.now().millisecondsSinceEpoch}';
    
    // Tạo iframe element
    final html.IFrameElement iframeElement = html.IFrameElement()
      ..src = widget.url
      ..style.border = 'none'
      ..style.width = widget.width != null ? '${widget.width}px' : '100%'
      ..style.height = widget.height != null ? '${widget.height}px' : '100%'
      ..onError.listen((event) {
        // Handle iframe load error
        if (mounted) {
          setState(() {
            _errorMessage = 'Không thể tải nội dung trong iframe';
          });
        }
      });
    
    // Register iframe với Flutter
    ui_web.platformViewRegistry.registerViewFactory(
      iframeId,
      (int viewId) => iframeElement,
    );
    
    // Return HtmlElementView
    return HtmlElementView(viewType: iframeId);
  }
}

