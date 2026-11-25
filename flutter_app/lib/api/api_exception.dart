import 'package:dio/dio.dart';

import '../utils/error_handler.dart';

/// Centralized API error type. The ApiService never throws to screens; it returns an
/// ApiResult. This class exists for places that prefer exceptions (e.g. `dataOrThrow`).
class ApiException implements Exception {
  final String message;
  final int status;
  final Map<String, List<String>> errors;
  const ApiException(this.message, {this.status = 0, this.errors = const {}});

  bool get isUnauthorized => status == 401;
  bool get isNetwork => status == 0;

  @override
  String toString() => message;

  /// Turns a Dio failure (no HTTP answer at all) into a plain message.
  static ApiException fromDio(DioException e, String baseUrl) => ApiException(ErrorHandler.fromDio(e, baseUrl));
}
