import 'package:flutter/foundation.dart';

/// Build-time settings. Override without editing code:
///   flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000/
///   flutter build apk --dart-define=API_BASE_URL=https://api.example.com/
/// The value must end with "/". Android emulator -> PC localhost is http://10.0.2.2:8000/.
class AppConfig {
  AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://192.168.31.99:8000/');

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration sendTimeout = Duration(seconds: 60);
  static const Duration receiveTimeout = Duration(seconds: 60);

  /// Request logging (method, path, status only - never bodies, headers or tokens).
  static bool get logRequests => kDebugMode;
}
