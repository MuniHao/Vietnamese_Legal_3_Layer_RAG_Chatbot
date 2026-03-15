import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Theme chính cho ứng dụng pháp luật
/// Phong cách: Tối giản - Hiện đại - Pháp lý - Thân thiện
class AppTheme {
  AppTheme._();

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      
      // Color Scheme - Dark Theme
      colorScheme: ColorScheme.dark(
        primary: AppColors.textWhite,
        secondary: AppColors.accentGold,
        surface: AppColors.backgroundGray,
        background: AppColors.backgroundBlack,
        error: AppColors.errorColor,
        onPrimary: AppColors.backgroundBlack,
        onSecondary: AppColors.backgroundBlack,
        onSurface: AppColors.textWhite,
        onBackground: AppColors.textWhite,
        onError: AppColors.textWhite,
      ),
      
      // Scaffold
      scaffoldBackgroundColor: AppColors.backgroundBlack,
      
      // AppBar Theme - Dark Theme
      appBarTheme: AppBarTheme(
        elevation: 0,
        centerTitle: false,
        backgroundColor: AppColors.backgroundBlack,
        foregroundColor: AppColors.textWhite,
        iconTheme: const IconThemeData(color: AppColors.textWhite),
        titleTextStyle: const TextStyle(
          color: AppColors.textWhite,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: -0.5,
        ),
      ),
      
      // Typography - Dark Theme
      textTheme: const TextTheme(
        displayLarge: TextStyle(
          fontSize: 32,
          fontWeight: FontWeight.w700,
          color: AppColors.textWhite,
          fontFamily: 'Inter',
          letterSpacing: -1,
        ),
        displayMedium: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w600,
          color: AppColors.textWhite,
          fontFamily: 'Inter',
          letterSpacing: -0.5,
        ),
        displaySmall: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w600,
          color: AppColors.textWhite,
          fontFamily: 'Inter',
        ),
        headlineMedium: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: AppColors.textWhite,
          fontFamily: 'Inter',
        ),
        titleLarge: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: AppColors.textLightGray,
          fontFamily: 'Inter',
        ),
        titleMedium: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w500,
          color: AppColors.textLightGray,
          fontFamily: 'Inter',
        ),
        bodyLarge: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.normal,
          color: AppColors.textWhite,
          fontFamily: 'Inter',
          height: 1.5,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.normal,
          color: AppColors.textLightGray,
          fontFamily: 'Inter',
          height: 1.5,
        ),
        bodySmall: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.normal,
          color: AppColors.textGray,
          fontFamily: 'Inter',
        ),
      ),
      
      // Elevated Button Theme - Dark Theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.backgroundGray,
          foregroundColor: AppColors.textWhite,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
          ),
        ),
      ),
      
      // Text Button Theme - Dark Theme
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.textWhite,
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
          ),
        ),
      ),
      
      // Outlined Button Theme - Dark Theme
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.textWhite,
          side: const BorderSide(color: AppColors.borderLight, width: 1.5),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
          ),
        ),
      ),
      
      // Input Decoration Theme - Dark Theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.backgroundGray,
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
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.errorColor),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: const TextStyle(
          color: AppColors.textGray,
          fontFamily: 'Inter',
        ),
      ),
      
      // Card Theme - Dark Theme
      cardTheme: CardThemeData(
        elevation: 0,
        color: AppColors.backgroundGray,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.borderLight, width: 1),
        ),
      ),
      
      // Chip Theme - Dark Theme
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.backgroundGray,
        selectedColor: AppColors.backgroundLightGray,
        labelStyle: const TextStyle(
          fontFamily: 'Inter',
          fontSize: 14,
          color: AppColors.textWhite,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: AppColors.borderLight),
        ),
      ),
      
      // Icon Theme - Dark Theme
      iconTheme: const IconThemeData(
        color: AppColors.textWhite,
        size: 24,
      ),
      
      // Divider Theme - Dark Theme
      dividerTheme: const DividerThemeData(
        color: AppColors.dividerColor,
        thickness: 1,
        space: 1,
      ),
    );
  }
}

