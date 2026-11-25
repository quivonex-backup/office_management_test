import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData light([Color accent = AppColors.accent]) {
    final scheme = ColorScheme.fromSeed(seedColor: accent, primary: accent, brightness: Brightness.light)
        .copyWith(secondary: AppColors.highlight);
    return _base(scheme, AppColors.background, Colors.white);
  }

  static ThemeData dark([Color accent = const Color(0xFF5B8CFF)]) {
    final scheme = ColorScheme.fromSeed(seedColor: accent, primary: accent, brightness: Brightness.dark)
        .copyWith(secondary: const Color(0xFFF5B942));
    return _base(scheme, const Color(0xFF0F141C), const Color(0xFF171E29));
  }

  static ThemeData _base(ColorScheme scheme, Color bg, Color card) {
    final radius = BorderRadius.circular(12);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.primary,
        foregroundColor: scheme.onPrimary,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.6)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: card,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        border: OutlineInputBorder(borderRadius: radius),
        enabledBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: scheme.outlineVariant)),
        focusedBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: scheme.primary, width: 1.6)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: radius),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: radius),
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: scheme.secondary,
        foregroundColor: Colors.black,
      ),
      listTileTheme: const ListTileThemeData(contentPadding: EdgeInsets.symmetric(horizontal: 14)),
      snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, shape: RoundedRectangleBorder(borderRadius: radius)),
    );
  }
}
