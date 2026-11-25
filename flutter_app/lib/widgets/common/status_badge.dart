import 'package:flutter/material.dart';

import '../../constants/app_colors.dart';
import '../../utils/helpers.dart';

class StatusBadge extends StatelessWidget {
  final String? status;
  final Color? color;
  const StatusBadge(this.status, {super.key, this.color});

  @override
  Widget build(BuildContext context) {
    if (status == null || status!.isEmpty) return const SizedBox.shrink();
    final c = color ?? AppColors.forStatus(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(Fmt.label(status), style: TextStyle(color: c, fontSize: 11.5, fontWeight: FontWeight.w600)),
    );
  }
}
