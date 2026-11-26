import 'dart:typed_data';

import 'package:intl/intl.dart';
import '../api/api_response.dart';
import 'date_formatter.dart';
import 'file_saver/file_saver.dart';

class Fmt {
  Fmt._();

  static String apiDate(DateTime d) => DateFormatter.api(d);
  static String apiTime(int h, int m) => DateFormatter.apiTime(h, m);
  static String date(dynamic v) => DateFormatter.date(v);
  static String dateTime(dynamic v) => DateFormatter.dateTime(v);
  static String time(dynamic v) => DateFormatter.time(v);

  /// Indian-style money: 125000 -> ₹1,25,000.00
  static String money(dynamic v, {int digits = 2}) {
    final n = num.tryParse(v?.toString() ?? '');
    if (n == null) return v?.toString() ?? '';
    return NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: digits).format(n);
  }

  static String number(dynamic v) {
    final n = num.tryParse(v?.toString() ?? '');
    if (n == null) return v?.toString() ?? '';
    return NumberFormat('#,##,##0.##', 'en_IN').format(n);
  }

  /// "IN_PROGRESS" -> "In progress"
  static String label(String? s) {
    if (s == null || s.isEmpty) return '';
    final t = s.replaceAll('_', ' ').toLowerCase();
    return t[0].toUpperCase() + t.substring(1);
  }

  static String initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }
}

/// Reads a nested value: get(map, 'employee.name').
dynamic pick(dynamic map, String path) {
  dynamic cur = map;
  for (final k in path.split('.')) {
    if (cur is Map) {
      cur = cur[k];
    } else {
      return null;
    }
  }
  return cur;
}

/// Server answer -> list of maps (data may be a list, or null).
List<Map<String, dynamic>> asMapList(dynamic data) {
  if (data is List) {
    return data.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
  }
  return const [];
}

Map<String, dynamic> asMap(dynamic data) =>
    data is Map ? Map<String, dynamic>.from(data) : <String, dynamic>{};

/// Android: saves to the temp folder and opens the viewer. Web: starts a browser download.
Future<String?> saveAndOpen(BlobFile file) async {
  try {
    final safe = file.filename.replaceAll(RegExp(r'[^\w.\- ]'), '_');
    return await saveFile(safe, Uint8List.fromList(file.bytes));
  } catch (e) {
    return e.toString();
  }
}
