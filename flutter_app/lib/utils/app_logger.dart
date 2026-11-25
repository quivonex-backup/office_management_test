import 'package:flutter/foundation.dart';

/// Tiny logger. Never pass tokens or passwords to it.
class AppLogger {
  AppLogger._();
  static void d(String message) {
    if (kDebugMode) debugPrint('[om] $message');
  }

  static void e(String message, [Object? error]) {
    if (kDebugMode) debugPrint('[om][error] $message${error != null ? ' -> $error' : ''}');
  }
}
