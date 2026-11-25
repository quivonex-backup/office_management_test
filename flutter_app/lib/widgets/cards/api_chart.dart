import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../constants/app_colors.dart';

/// Renders the backend's chart shape: {type: line|bar, labels: [...], series: [{name, data: [...]}]}.
class ApiChart extends StatelessWidget {
  final Map<String, dynamic> chart;
  final double height;
  const ApiChart({super.key, required this.chart, this.height = 190});

  @override
  Widget build(BuildContext context) {
    final labels = (chart['labels'] as List? ?? const []).map((e) => '$e').toList();
    final series = (chart['series'] as List? ?? const []).whereType<Map>().toList();
    if (labels.isEmpty || series.isEmpty) return const SizedBox.shrink();
    final isBar = chart['type'] == 'bar';
    final colors = AppColors.chart;
    double maxY = 1;
    for (final s in series) {
      for (final v in (s['data'] as List? ?? const [])) {
        if (v is num && v > maxY) maxY = v.toDouble();
      }
    }
    final titles = FlTitlesData(
      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 34)),
      bottomTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 26,
          interval: labels.length > 8 ? (labels.length / 6).ceilToDouble() : 1,
          getTitlesWidget: (v, meta) {
            final i = v.toInt();
            if (i < 0 || i >= labels.length) return const SizedBox.shrink();
            final t = labels[i];
            return Padding(padding: const EdgeInsets.only(top: 6), child: Text(t.length > 6 ? t.substring(0, 6) : t, style: const TextStyle(fontSize: 10)));
          },
        ),
      ),
    );
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(
        height: height,
        child: isBar
            ? BarChart(BarChartData(
                maxY: maxY * 1.15,
                titlesData: titles,
                gridData: const FlGridData(drawVerticalLine: false),
                borderData: FlBorderData(show: false),
                barGroups: [
                  for (var i = 0; i < labels.length; i++)
                    BarChartGroupData(x: i, barRods: [
                      for (var s = 0; s < series.length; s++)
                        BarChartRodData(
                          toY: (((series[s]['data'] as List?) ?? const []).length > i ? (series[s]['data'] as List)[i] : 0) is num
                              ? ((series[s]['data'] as List)[i] as num).toDouble()
                              : 0,
                          width: series.length > 1 ? 8 : 14,
                          color: colors[s % colors.length],
                          borderRadius: BorderRadius.circular(3),
                        ),
                    ]),
                ],
              ))
            : LineChart(LineChartData(
                minY: 0,
                maxY: maxY * 1.15,
                titlesData: titles,
                gridData: const FlGridData(drawVerticalLine: false),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  for (var s = 0; s < series.length; s++)
                    LineChartBarData(
                      isCurved: true,
                      barWidth: 2.5,
                      color: colors[s % colors.length],
                      dotData: const FlDotData(show: false),
                      spots: [
                        for (var i = 0; i < labels.length; i++)
                          FlSpot(i.toDouble(), (((series[s]['data'] as List?) ?? const []).length > i && (series[s]['data'] as List)[i] is num) ? ((series[s]['data'] as List)[i] as num).toDouble() : 0),
                      ],
                    ),
                ],
              )),
      ),
      if (series.length > 1)
        Wrap(spacing: 12, children: [
          for (var s = 0; s < series.length; s++)
            Row(mainAxisSize: MainAxisSize.min, children: [
              Container(width: 10, height: 10, color: colors[s % colors.length]),
              const SizedBox(width: 4),
              Text('${series[s]['name']}', style: const TextStyle(fontSize: 11)),
            ]),
        ]),
    ]);
  }
}
