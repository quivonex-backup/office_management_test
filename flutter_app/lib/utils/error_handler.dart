import 'package:dio/dio.dart';

/// One place that turns failures into short, user-friendly sentences.
class ErrorHandler {
  ErrorHandler._();

  /// A request that never got an HTTP answer (offline, timeout, DNS, CORS...).
  static String fromDio(DioException e, String baseUrl) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'The server took too long to respond. Please try again.';
      case DioExceptionType.connectionError:
        return 'Cannot reach the server at $baseUrl. Check your internet connection and that the backend is running.';
      case DioExceptionType.cancel:
        return 'The request was cancelled.';
      default:
        return 'Network problem: ${e.message ?? 'unknown error'}';
    }
  }

  /// Used only when the server answered with an error but sent no message of its own.
  static String forStatus(int status) {
    switch (status) {
      case 400:
        return 'The request was not accepted. Please check the details and try again.';
      case 401:
        return 'Your session has expired. Please log in again.';
      case 403:
        return 'You do not have permission to do this.';
      case 404:
        return 'That item could not be found.';
      case 413:
        return 'The file is too large.';
      case 429:
        return 'Too many requests. Please wait a moment.';
      default:
        return status >= 500 ? 'The server had a problem ($status). Please try again later.' : 'Request failed ($status).';
    }
  }
}
