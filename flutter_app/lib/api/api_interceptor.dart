import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../utils/app_logger.dart';
import 'api_url.dart';

/// Centralized request/response hook (Dio interceptor).
///  * adds `Authorization: Bearer <access>` to every non-public path,
///  * logs method + path + status in debug builds ONLY - never bodies, headers, passwords or tokens.
/// The 401 -> refresh-token -> retry rule lives in ApiService because it must re-send the request.
class ApiInterceptor extends Interceptor {
  final String? Function() accessToken;
  ApiInterceptor({required this.accessToken});

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = accessToken();
    if (!ApiUrls.publicPaths.contains(options.path) && token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    if (AppConfig.logRequests) AppLogger.d('--> ${options.method} ${options.path}');
    handler.next(options);
  }

  @override
  void onResponse(Response<dynamic> response, ResponseInterceptorHandler handler) {
    if (AppConfig.logRequests) AppLogger.d('<-- ${response.statusCode} ${response.requestOptions.path}');
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (AppConfig.logRequests) AppLogger.d('<-- ERROR ${err.type.name} ${err.requestOptions.path}');
    handler.next(err);
  }
}
