import 'package:intl/intl.dart';

import '../constants/app_constants.dart';

/// Date/time parsing and display (the API sends `yyyy-MM-dd`, `HH:mm[:ss]` and ISO timestamps).
class DateFormatter {
  DateFormatter._();
  static final DateFormat _api = DateFormat(AppConstants.apiDateFormat);
  static final DateFormat _date = DateFormat(AppConstants.dateFormat);
  static final DateFormat _dateTime = DateFormat(AppConstants.dateTimeFormat);

  static DateTime? parse(dynamic v) => v == null ? null : DateTime.tryParse(v.toString());

  /// For request bodies: `2025-03-01`.
  static String api(DateTime d) => _api.format(d);

  /// `2025-03-01` -> `01 Mar 2025`; unparsable text is returned unchanged.
  static String date(dynamic v) {
    final d = parse(v);
    return d == null ? (v?.toString() ?? '') : _date.format(d);
  }

  static String dateTime(dynamic v) {
    final d = parse(v);
    return d == null ? (v?.toString() ?? '') : _dateTime.format(d.toLocal());
  }

  /// `09:30:00` -> `09:30 AM`
  static String time(dynamic v) {
    final s = v?.toString() ?? '';
    final m = RegExp(r'^(\d{1,2}):(\d{2})').firstMatch(s);
    if (m == null) return s;
    final h = int.parse(m.group(1)!);
    final suffix = h >= 12 ? 'PM' : 'AM';
    final h12 = h % 12 == 0 ? 12 : h % 12;
    return '${h12.toString().padLeft(2, '0')}:${m.group(2)} $suffix';
  }

  /// `9,30` -> `09:30` (request bodies).
  static String apiTime(int h, int m) => '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
}
