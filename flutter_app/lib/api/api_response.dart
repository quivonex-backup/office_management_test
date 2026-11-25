import '../utils/error_handler.dart';
import 'api_exception.dart';

/// Every API call returns this. It never throws.
/// Backend envelope: { status: bool, message, data, errors }.
class ApiResult<T> {
  final bool ok;

  /// HTTP status (0 = network problem)
  final int status;

  /// Message exactly as the server said it.
  final String message;
  final T? data;

  /// Per-field errors, e.g. { "email": ["Already used."] }; list-style errors land in `items`,
  /// per-item failure reasons found inside `data` land in `reasons`.
  final Map<String, List<String>> errors;

  /// Whole JSON body (scope_applied, summary, user_account ...).
  final Map<String, dynamic> raw;

  const ApiResult({
    required this.ok,
    required this.status,
    required this.message,
    required this.data,
    this.errors = const {},
    this.raw = const {},
  });

  factory ApiResult.failure(String message, {int status = 0}) =>
      ApiResult(ok: false, status: status, message: message, data: null);

  ApiResult<R> map<R>(R? Function(T? data) f) => ApiResult<R>(
        ok: ok, status: status, message: message, data: ok ? f(data) : null, errors: errors, raw: raw);

  /// Per-field error text for inline errors under inputs: { field: "message" }.
  Map<String, String> get fieldErrors => {
        for (final e in errors.entries)
          if (e.key != 'items' && e.key != 'reasons') e.key: e.value.join(' ')
      };

  /// Server message plus the specific reasons it gave, for toasts.
  String get fullMessage {
    final parts = <String>[if (message.isNotEmpty) message];
    for (final k in ['items', 'reasons']) {
      final v = errors[k];
      if (v != null) parts.addAll(v);
    }
    if (parts.length == 1 && fieldErrors.isNotEmpty) parts.addAll(fieldErrors.values);
    return parts.join('\n');
  }

  T dataOrThrow() {
    if (!ok || data == null) throw ApiException(fullMessage, status: status, errors: errors);
    return data as T;
  }

  /// `scope_applied` the list endpoints add (all / team / mine).
  String get scopeApplied => (raw['scope_applied'] ?? 'all').toString();
}

/// Parses the backend envelope. Mirrors parse() in the React http.ts.
ApiResult<dynamic> parseEnvelope(int httpStatus, dynamic body) {
  if (body is Map) {
    final map = Map<String, dynamic>.from(body);
    final hasStatus = map.containsKey('status');
    final ok = hasStatus ? map['status'] == true : httpStatus >= 200 && httpStatus < 300;
    var message = (map['message'] ?? map['detail'] ?? '').toString();
    if (message.isEmpty && !ok) message = ErrorHandler.forStatus(httpStatus);

    final errors = <String, List<String>>{};
    final e = map['errors'];
    if (e is List) {
      final rows = <String>[];
      for (var i = 0; i < e.length; i++) {
        final x = e[i];
        if (x is! Map) {
          if (x != null && x.toString().isNotEmpty) rows.add(x.toString());
          continue;
        }
        final o = Map<String, dynamic>.from(x);
        final label = o['row'] != null ? 'Row ${o['row']}' : 'Item ${i + 1}';
        final detail = o['errors'] is Map ? Map<String, dynamic>.from(o['errors'] as Map) : o;
        final parts = detail.entries
            .where((kv) => kv.key != 'row')
            .map((kv) => '${kv.key.replaceAll('_', ' ')}: ${kv.value is List ? (kv.value as List).join(' ') : kv.value}')
            .toList();
        if (parts.isNotEmpty) rows.add('$label – ${parts.join('; ')}');
      }
      if (rows.isNotEmpty) errors['items'] = rows;
    } else if (e is Map) {
      e.forEach((k, v) {
        if (v is List) {
          errors[k.toString()] = v.map((x) => x.toString()).toList();
        } else if (v != null) {
          errors[k.toString()] = [v.toString()];
        }
      });
    }
    final why = _failureReasons(map['data']);
    if (why.isNotEmpty) errors['reasons'] = why;

    return ApiResult<dynamic>(
      ok: ok,
      status: httpStatus,
      message: message,
      data: hasStatus ? map['data'] : map,
      errors: errors,
      raw: map,
    );
  }
  if (httpStatus >= 200 && httpStatus < 300) {
    return ApiResult<dynamic>(ok: true, status: httpStatus, message: '', data: body);
  }
  return ApiResult<dynamic>.failure('Request failed ($httpStatus).', status: httpStatus);
}

/// Finds {reason|error} on items inside data (up to 3 levels), labelled by the item's name.
List<String> _failureReasons(dynamic data, [int depth = 0, Set<String>? out]) {
  final set = out ?? <String>{};
  if (depth > 3 || data == null) return set.toList();
  if (data is List) {
    for (final x in data) {
      _failureReasons(x, depth + 1, set);
    }
    return set.toList();
  }
  if (data is! Map) return set.toList();
  final o = Map<String, dynamic>.from(data);
  final why = o['reason'] is String ? o['reason'] as String : (o['error'] is String ? o['error'] as String : '');
  if (why.trim().isNotEmpty) {
    String? who;
    for (final k in ['client_name', 'employee_name', 'name', 'title', 'project_name', 'email']) {
      if (o[k] is String && (o[k] as String).isNotEmpty) {
        who = o[k] as String;
        break;
      }
    }
    set.add(who != null ? '$who: ${why.trim()}' : why.trim());
  }
  for (final v in o.values) {
    if (v is Map || v is List) _failureReasons(v, depth + 1, set);
  }
  return set.toList();
}

/// A file returned by the server (payslip PDF, Excel export, offer letter).
class BlobFile {
  final List<int> bytes;
  final String filename;
  const BlobFile(this.bytes, this.filename);
}
