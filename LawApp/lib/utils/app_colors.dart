import 'package:flutter/material.dart';

/// Bảng màu chủ đạo cho ứng dụng pháp luật
/// Dark Theme: Nền đen, chữ trắng, các màu xám
class AppColors {
  AppColors._();

  // Màu nền (Background) - Dark Theme
  static const Color backgroundBlack = Color(0xFF000000); // Đen
  static const Color backgroundDark = Color(0xFF1A1A1A); // Đen nhạt
  static const Color backgroundGray = Color(0xFF2A2A2A); // Xám đậm
  static const Color backgroundLightGray = Color(0xFF3A3A3A); // Xám vừa
  
  // Màu chữ (Text) - Dark Theme
  static const Color textWhite = Color(0xFFFFFFFF); // Trắng
  static const Color textLightGray = Color(0xFFE0E0E0); // Xám sáng
  static const Color textGray = Color(0xFFB0B0B0); // Xám
  static const Color textDarkGray = Color(0xFF808080); // Xám đậm
  
  // Màu chính (Primary) - Giữ nguyên cho accent
  static const Color primaryNavy = Color(0xFF1E3A8A); // Xanh navy
  static const Color primarySlate = Color(0xFF0F172A); // Xanh than
  
  // Màu phụ (Accent) - Giữ nguyên
  static const Color accentGold = Color(0xFFFACC15); // Vàng ánh kim
  static const Color accentCyan = Color(0xFF22D3EE); // Xanh ngọc
  
  // Màu cho message bubbles - Dark Theme
  static const Color userBubble = Color(0xFF3A3A3A); // Xám đậm cho user
  static const Color aiBubble = Color(0xFF2A2A2A); // Xám cho AI
  static const Color aiBubbleAlt = Color(0xFF1A1A1A); // Đen nhạt thay thế
  
  // Màu phụ trợ - Dark Theme
  static const Color borderLight = Color(0xFF404040); // Viền xám
  static const Color dividerColor = Color(0xFF333333); // Đường phân cách
  static const Color errorColor = Color(0xFFDC2626);
  static const Color successColor = Color(0xFF10B981);
  static const Color warningColor = Color(0xFFF59E0B);
  
  // Legacy colors for backward compatibility (mapped to dark theme)
  static const Color backgroundWhite = backgroundGray; // Map to gray
  static const Color backgroundLight = backgroundDark; // Map to dark
  static const Color textDark = textLightGray; // Map to light gray
  static const Color textBlack = textWhite; // Map to white
  
  // Gradient cho primary
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [backgroundGray, backgroundDark],
  );
  
  // Gradient cho accent
  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [accentGold, Color(0xFFFBBF24)],
  );
  
  // Gradient cho AppBar - Dark Theme
  static const LinearGradient appBarGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [backgroundBlack, backgroundDark],
  );
}

