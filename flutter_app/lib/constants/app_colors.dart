import 'package:flutter/material.dart';

/// Brand colours taken from the React "Dark blue" default theme (config/themes.ts).
class AppColors {
  AppColors._();
  static const Color accent = Color(0xFF00008B);
  static const Color highlight = Color(0xFFF59E0B);
  static const Color background = Color(0xFFF4F5F7);
  static const Color surface = Colors.white;
  static const Color border = Color(0xFFE2E5EA);
  static const Color textPrimary = Color(0xFF1B2433);
  static const Color textMuted = Color(0xFF6B7585);
  static const Color success = Color(0xFF16A34A);
  static const Color warning = Color(0xFFD97706);
  static const Color danger = Color(0xFFDC2626);
  static const Color info = Color(0xFF2563EB);

  static const List<Color> chart = [
    Color(0xFF00008B), Color(0xFFF59E0B), Color(0xFF14B8A6),
    Color(0xFFEC4899), Color(0xFF8B5CF6), Color(0xFF94A3B8),
  ];

  /// Colour for status words used across the app (PENDING, APPROVED, PAID ...).
  static Color forStatus(String? s) {
    switch ((s ?? '').toUpperCase()) {
      case 'APPROVED':
      case 'PAID':
      case 'PRESENT':
      case 'DONE':
      case 'COMPLETED':
      case 'RESOLVED':
      case 'CLOSED':
      case 'ACCEPTED':
      case 'SELECTED':
      case 'AVAILABLE':
      case 'FINALIZED':
      case 'VERIFIED':
      case 'ACTIVE':
        return success;
      case 'PENDING':
      case 'IN_PROGRESS':
      case 'HALF_DAY':
      case 'PENDING_REVIEW':
      case 'DRAFT':
      case 'ON_HOLD':
      case 'SHORTLISTED':
      case 'ASSIGNED':
      case 'OPEN':
      case 'UNPAID':
        return warning;
      case 'REJECTED':
      case 'ABSENT':
      case 'CANCELLED':
      case 'FAILED':
      case 'LOST':
      case 'DECLINED':
      case 'INACTIVE':
      case 'URGENT':
        return danger;
      default:
        return info;
    }
  }
}
