import '../common/ref.dart';

class ReportFilter {
  final String key, type;
  final String? defaultValue, note;
  final List<MapEntry<String, String>> options; // value -> label
  const ReportFilter({required this.key, required this.type, this.defaultValue, this.note, this.options = const []});

  factory ReportFilter.fromJson(Map<String, dynamic> j) {
    final opts = <MapEntry<String, String>>[];
    for (final o in (j['options'] as List? ?? const [])) {
      if (o is Map) {
        opts.add(MapEntry(o['value'].toString(), (o['label'] ?? o['value']).toString()));
      } else {
        opts.add(MapEntry(o.toString(), o.toString()));
      }
    }
    return ReportFilter(key: (j['key'] ?? '').toString(), type: (j['type'] ?? 'text').toString(), defaultValue: asStr(j['default']), note: asStr(j['note']), options: opts);
  }
}

class ReportMeta {
  final String key, title, group;
  final List<String> formats;
  final List<ReportFilter> filters;
  const ReportMeta({required this.key, required this.title, required this.group, required this.formats, required this.filters});

  factory ReportMeta.fromJson(Map<String, dynamic> j) => ReportMeta(
        key: (j['key'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        group: (j['group'] ?? '').toString(),
        formats: (j['formats'] as List? ?? const []).map((e) => e.toString()).toList(),
        filters: (j['filters'] as List? ?? const []).whereType<Map>().map((e) => ReportFilter.fromJson(Map<String, dynamic>.from(e))).toList(),
      );
}

class ReportColumn {
  final String key, label, type;
  const ReportColumn({required this.key, required this.label, required this.type});
  factory ReportColumn.fromJson(Map<String, dynamic> j) =>
      ReportColumn(key: (j['key'] ?? '').toString(), label: (j['label'] ?? '').toString(), type: (j['type'] ?? 'text').toString());
}

class ReportData {
  final String title;
  final List<ReportColumn> columns;
  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic> totals, summary;
  final int page, totalPages, totalRows;
  const ReportData({required this.title, required this.columns, required this.rows, required this.totals, required this.summary,
      required this.page, required this.totalPages, required this.totalRows});

  factory ReportData.fromJson(Map<String, dynamic> j) {
    final p = j['pagination'] is Map ? Map<String, dynamic>.from(j['pagination'] as Map) : <String, dynamic>{};
    return ReportData(
      title: (j['title'] ?? '').toString(),
      columns: (j['columns'] as List? ?? const []).whereType<Map>().map((e) => ReportColumn.fromJson(Map<String, dynamic>.from(e))).toList(),
      rows: (j['rows'] as List? ?? const []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList(),
      totals: j['totals'] is Map ? Map<String, dynamic>.from(j['totals'] as Map) : {},
      summary: j['summary'] is Map ? Map<String, dynamic>.from(j['summary'] as Map) : {},
      page: asInt(p['page']) ?? 1,
      totalPages: asInt(p['total_pages']) ?? 1,
      totalRows: asInt(p['total_rows']) ?? 0,
    );
  }
}
