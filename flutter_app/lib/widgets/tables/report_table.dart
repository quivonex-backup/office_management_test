import 'package:flutter/material.dart';

import '../../models/response/report_response.dart';
import '../../utils/helpers.dart';

/// Scrollable table for report data. Columns come from the server (they change per organization).
class ReportTable extends StatelessWidget {
  final List<ReportColumn> columns;
  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic> totals;
  const ReportTable({super.key, required this.columns, required this.rows, this.totals = const {}});

  String _cell(ReportColumn c, dynamic v) {
    if (v == null) return '—';
    switch (c.type) {
      case 'money':
        return Fmt.money(v);
      case 'number':
        return Fmt.number(v);
      case 'date':
        return Fmt.date(v);
      case 'time':
        return Fmt.time(v);
      case 'bool':
        return v == true ? 'Yes' : 'No';
      default:
        return v.toString();
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowHeight: 44,
        dataRowMinHeight: 40,
        dataRowMaxHeight: 56,
        columns: [for (final c in columns) DataColumn(label: Text(c.label, style: const TextStyle(fontWeight: FontWeight.w700)), numeric: c.type == 'number' || c.type == 'money')],
        rows: [
          for (final r in rows) DataRow(cells: [for (final c in columns) DataCell(Text(_cell(c, r[c.key])))]),
          if (totals.isNotEmpty)
            DataRow(color: WidgetStatePropertyAll(Theme.of(context).colorScheme.primary.withValues(alpha: 0.06)), cells: [
              for (var i = 0; i < columns.length; i++)
                DataCell(Text(i == 0 ? 'Total' : (totals[columns[i].key] == null ? '' : _cell(columns[i], totals[columns[i].key])), style: const TextStyle(fontWeight: FontWeight.w700))),
            ]),
        ],
      ),
    );
  }
}
