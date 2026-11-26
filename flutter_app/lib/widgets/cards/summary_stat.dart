import 'package:flutter/material.dart';

import '../../constants/app_colors.dart';
import '../../utils/responsive_helper.dart';

/// One number tile of the row above a list ("9 Total Employees").
class SummaryStat {
  final String label, value;
  final IconData icon;
  final Color color;
  const SummaryStat(this.label, this.value, this.icon, this.color);
}

class SummaryStats extends StatelessWidget {
  final List<SummaryStat> stats;
  const SummaryStats({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    if (stats.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(builder: (context, box) {
      final cols = box.maxWidth >= 860 ? stats.length.clamp(1, 4).toInt() : (box.maxWidth >= 520 ? stats.length.clamp(1, 3).toInt() : 2);
      return GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: stats.length,
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: cols, mainAxisSpacing: 12, crossAxisSpacing: 12, mainAxisExtent: 78),
        itemBuilder: (_, i) {
          final s = stats[i];
          return Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: BorderSide(color: s.color.withValues(alpha: 0.12))),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(color: s.color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(14)),
                  child: Icon(s.icon, color: s.color, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                    FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(s.value, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w700))),
                    Text(s.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, color: AppColors.textMuted)),
                  ]),
                ),
              ]),
            ),
          );
        },
      );
    });
  }
}

/// Square soft icon button used for row actions (view / edit / delete) and the refresh button.
class SoftIconButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String tooltip;
  final VoidCallback? onTap;
  final double size;
  const SoftIconButton({super.key, required this.icon, required this.color, required this.tooltip, this.onTap, this.size = 36});

  @override
  Widget build(BuildContext context) => Tooltip(
        message: tooltip,
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
            child: Icon(icon, size: size * 0.5, color: color),
          ),
        ),
      );
}
