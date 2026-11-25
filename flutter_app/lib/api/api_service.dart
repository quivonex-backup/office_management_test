import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../services/storage_service.dart';
import '../utils/app_logger.dart';
import '../utils/error_handler.dart';
import 'api_exception.dart';
import 'api_interceptor.dart';
import 'api_request.dart';
import 'api_response.dart';
import 'api_url.dart';

/// THE ONLY CLASS THAT TALKS TO THE SERVER (port of React core/http.ts).
/// Every API in this backend is POST. For every request it:
///  1. adds `Authorization: Bearer <access>` (except on public paths),
///  2. adds `organization_id` ONLY when the user belongs to several organizations and picked one,
///  3. on 401 calls refresh-token ONCE (shared by parallel calls), saves BOTH new tokens, retries once,
///  4. turns {status, message, data, errors} into an [ApiResult] that never throws,
///  5. turns network problems / timeouts into a plain message.
class ApiService {
  ApiService._() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiUrls.baseUrl,
      connectTimeout: AppConfig.connectTimeout,
      sendTimeout: AppConfig.sendTimeout,
      receiveTimeout: AppConfig.receiveTimeout,
      validateStatus: (_) => true,
      headers: {'Accept': 'application/json'},
    ));
    _dio.interceptors.add(ApiInterceptor(accessToken: () => _access));
  }
  static final ApiService instance = ApiService._();

  late final Dio _dio;
  final StorageService _store = StorageService.instance;

  String? _access;
  String? _refresh;
  bool _persist = true;

  /// Set only for users in several organizations who picked one.
  int? activeOrgId;

  /// Called when the session can no longer be refreshed -> go to Login.
  void Function()? onSessionExpired;

  // ------------------------------------------------------------ tokens
  Future<void> loadTokens() async {
    _access = await _store.readSecure(StorageService.kAccess);
    _refresh = await _store.readSecure(StorageService.kRefresh);
    _persist = true;
  }

  bool get hasTokens => (_access ?? '').isNotEmpty && (_refresh ?? '').isNotEmpty;

  /// [persist] only on login (Remember me). A refresh keeps the mode the login chose.
  Future<void> setTokens(String access, String refresh, {bool? persist}) async {
    _access = access;
    _refresh = refresh;
    if (persist != null) _persist = persist;
    if (_persist) {
      await _store.writeSecure(StorageService.kAccess, access);
      await _store.writeSecure(StorageService.kRefresh, refresh);
    } else {
      await _store.deleteSecure(StorageService.kAccess);
      await _store.deleteSecure(StorageService.kRefresh);
    }
  }

  Future<void> clearTokens() async {
    _access = null;
    _refresh = null;
    await _store.deleteSecure(StorageService.kAccess);
    await _store.deleteSecure(StorageService.kRefresh);
    await _store.remove(StorageService.kOrg);
  }

  // ------------------------------------------------------------ helpers
  bool _wantsOrg(String path) =>
      activeOrgId != null && !ApiUrls.noOrgIdPrefixes.any((p) => path.startsWith(p));
  bool _isPublic(String path) => ApiUrls.publicPaths.contains(path);
  Options _opts(String path, {ResponseType? responseType}) => Options(
        responseType: responseType,
      );

  Future<void> _expire() async {
    await clearTokens();
    onSessionExpired?.call();
  }

  // ------------------------------------------------------------ refresh (one at a time)
  Future<bool>? _refreshing;

  Future<bool> _refreshOnce(String? failedAccess) {
    final running = _refreshing;
    if (running != null) return running;
    final f = _doRefresh(failedAccess).whenComplete(() => _refreshing = null);
    _refreshing = f;
    return f;
  }

  Future<bool> _doRefresh(String? failedAccess) async {
    // somebody else may have refreshed while we waited
    if ((_access ?? '').isNotEmpty && _access != failedAccess) return true;
    if ((_refresh ?? '').isEmpty) {
      await _expire();
      return false;
    }
    try {
      final res = await _dio.post<dynamic>(ApiUrls.refresh, data: RefreshTokenRequest(_refresh!).toJson());
      final b = res.data;
      if (b is Map && b['status'] == true && b['data'] is Map) {
        final d = b['data'] as Map;
        if (d['access'] != null && d['refresh'] != null) {
          await setTokens(d['access'].toString(), d['refresh'].toString()); // BOTH are new
          return true;
        }
      }
    } on DioException {
      return false; // network problem: keep tokens, let the call fail
    } catch (_) {
      return false;
    }
    await _expire();
    return false;
  }

  Future<ApiResult<dynamic>> _run(String path, Future<Response<dynamic>> Function() send) async {
    try {
      final used = _access;
      var res = await send();
      if (res.statusCode == 401 && !_isPublic(path)) {
        if (await _refreshOnce(used)) {
          res = await send();
          if (res.statusCode == 401) await _expire();
        }
      }
      return parseEnvelope(res.statusCode ?? 0, res.data);
    } on DioException catch (e) {
      return ApiResult.failure(ErrorHandler.fromDio(e, ApiUrls.baseUrl));
    } catch (e) {
      AppLogger.e('unexpected error for $path', e);
      return ApiResult.failure('Something went wrong in the app ($e).');
    }
  }

  // ------------------------------------------------------------ public API
  final Map<String, Future<ApiResult<dynamic>>> _inflight = {};
  static final RegExp _readPath = RegExp(r'/(list|detail)/$|my-(profile|organizations)/$');

  /// JSON POST. Identical read calls already on their way share one request.
  Future<ApiResult<dynamic>> post(String path, [Map<String, dynamic> body = const {}]) {
    Future<ApiResult<dynamic>> send() => _run(path, () {
          final data = _wantsOrg(path) ? {...body, 'organization_id': activeOrgId} : body;
          return _dio.post<dynamic>(path, data: data, options: _opts(path));
        });
    if (!_readPath.hasMatch(path)) return send();
    final key = '${activeOrgId ?? ''}|$path|${jsonEncode(body)}';
    final running = _inflight[key];
    if (running != null) return running;
    // NOTE: block body on purpose. An arrow body would return the removed future itself, and
    // whenComplete waits for a returned future -> the call would wait on itself forever.
    final p = send().whenComplete(() {
      _inflight.remove(key);
    });
    _inflight[key] = p;
    return p;
  }

  /// Typed convenience: POST a request model.
  Future<ApiResult<dynamic>> postRequest(String path, ApiRequest request) => post(path, request.toJson());

  /// Multipart POST. List values repeat the key; null skipped; bool -> "true"/"false".
  Future<ApiResult<dynamic>> postForm(
    String path, {
    Map<String, dynamic> fields = const {},
    List<UploadFile> files = const [],
  }) {
    return _run(path, () async {
      final form = FormData();
      void add(String k, dynamic v) {
        if (v == null) return;
        form.fields.add(MapEntry(k, v.toString()));
      }

      fields.forEach((k, v) {
        if (v is List) {
          for (final x in v) {
            add(k, x);
          }
        } else {
          add(k, v);
        }
      });
      if (_wantsOrg(path)) add('organization_id', activeOrgId);
      for (final f in files) {
        final part = f.bytes != null
            ? MultipartFile.fromBytes(f.bytes!, filename: f.name)
            : await MultipartFile.fromFile(f.path!, filename: f.name);
        form.files.add(MapEntry(f.field, part));
      }
      return _dio.post<dynamic>(path, data: form, options: _opts(path));
    });
  }

  /// POST that answers with a FILE (payslip PDF, Excel). Success -> data is a [BlobFile].
  Future<ApiResult<BlobFile>> postBlob(String path, [Map<String, dynamic> body = const {}, String fallbackName = 'download.pdf']) async {
    Future<Response<dynamic>> send() => _dio.post<dynamic>(
          path,
          data: _wantsOrg(path) ? {...body, 'organization_id': activeOrgId} : body,
          options: _opts(path, responseType: ResponseType.bytes),
        );
    try {
      final used = _access;
      var res = await send();
      if (res.statusCode == 401 && await _refreshOnce(used)) res = await send();
      final bytes = (res.data as List<int>?) ?? <int>[];
      final type = (res.headers.value('content-type') ?? '').toLowerCase();
      final code = res.statusCode ?? 0;
      if (code >= 200 && code < 300 && !type.contains('json')) {
        final cd = res.headers.value('content-disposition') ?? '';
        final m = RegExp('filename\\*?=(?:UTF-8\'\')?"?([^";]+)"?', caseSensitive: false).firstMatch(cd);
        final name = m != null ? Uri.decodeComponent(m.group(1)!) : fallbackName;
        return ApiResult<BlobFile>(ok: true, status: code, message: '', data: BlobFile(bytes, name));
      }
      try {
        final j = jsonDecode(utf8.decode(bytes));
        if (j is Map) {
          return ApiResult<BlobFile>.failure((j['message'] ?? j['detail'] ?? 'Request failed ($code).').toString(), status: code);
        }
      } catch (_) {}
      return ApiResult<BlobFile>.failure('Request failed ($code).', status: code);
    } on DioException catch (e) {
      return ApiResult<BlobFile>.failure(ErrorHandler.fromDio(e, ApiUrls.baseUrl));
    } catch (e) {
      return ApiResult<BlobFile>.failure('Cannot reach the server. Check your internet connection.');
    }
  }
}
