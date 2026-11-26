import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../constants/app_colors.dart';

/// Light purple admin theme (Poppins, white rounded cards, lavender page background).
class AppTheme {
  AppTheme._();

  static ThemeData light([Color accent = AppColors.accent]) {
    final scheme = ColorScheme.fromSeed(seedColor: accent, primary: accent, brightness: Brightness.light).copyWith(
      secondary: AppColors.highlight,
      surface: Colors.white,
      onSurface: AppColors.textPrimary,
      outlineVariant: AppColors.border,
    );
    return _base(scheme, AppColors.background, Colors.white, AppColors.textPrimary);
  }

  static ThemeData dark([Color accent = const Color(0xFFA78BFA)]) {
    final scheme = ColorScheme.fromSeed(seedColor: accent, primary: accent, brightness: Brightness.dark)
        .copyWith(secondary: const Color(0xFFF5B942));
    return _base(scheme, const Color(0xFF14121F), const Color(0xFF1E1B2E), Colors.white);
  }

  static ThemeData _base(ColorScheme scheme, Color bg, Color card, Color text) {
    final radius = BorderRadius.circular(12);
    final dark = scheme.brightness == Brightness.dark;
    final base = ThemeData(brightness: scheme.brightness, useMaterial3: true);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      textTheme: GoogleFonts.poppinsTextTheme(base.textTheme).apply(bodyColor: text, displayColor: text),
      appBarTheme: AppBarTheme(
        backgroundColor: card,
        foregroundColor: text,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        centerTitle: false,
        titleTextStyle: GoogleFonts.poppins(fontSize: 18, fontWeight: FontWeight.w600, color: text),
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        margin: EdgeInsets.zero,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: dark ? Colors.white10 : AppColors.border.withValues(alpha: 0.7)),
        ),
      ),
      drawerTheme: DrawerThemeData(backgroundColor: card, surfaceTintColor: Colors.transparent),
      dividerTheme: DividerThemeData(color: dark ? Colors.white12 : AppColors.border, space: 1),
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
          textStyle: GoogleFonts.poppins(fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48), shape: RoundedRectangleBorder(borderRadius: radius)),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: scheme.primary,
        foregroundColor: scheme.onPrimary,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      chipTheme: ChipThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20))),
      listTileTheme: const ListTileThemeData(contentPadding: EdgeInsets.symmetric(horizontal: 14)),
      snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, shape: RoundedRectangleBorder(borderRadius: radius)),
    );
  }
}
