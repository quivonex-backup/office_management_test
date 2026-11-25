import 'package:flutter/material.dart';

class StatCard extends StatelessWidget {
  final String label, value;
  final IconData? icon;
  final Color? color;
  final VoidCallback? onTap;
  const StatCard({super.key, required this.label, required this.value, this.icon, this.color, this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            if (icon != null)
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
                child: Icon(icon, color: c, size: 22),
              ),
            if (icon != null) const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                Text(label, style: Theme.of(context).textTheme.bodySmall, maxLines: 2, overflow: TextOverflow.ellipsis),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}
