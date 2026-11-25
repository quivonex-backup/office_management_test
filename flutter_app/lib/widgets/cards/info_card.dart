import 'package:flutter/material.dart';

/// Titled card with key/value rows (detail screens).
class InfoCard extends StatelessWidget {
  final String? title;
  final List<MapEntry<String, String?>> rows;
  final Widget? trailing;
  const InfoCard({super.key, this.title, required this.rows, this.trailing});

  @override
  Widget build(BuildContext context) {
    final shown = rows.where((e) => e.value != null && e.value!.trim().isNotEmpty).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (title != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                Expanded(child: Text(title!, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
                if (trailing != null) trailing!,
              ]),
            ),
          if (shown.isEmpty) const Text('—'),
          for (final e in shown)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 120, child: Text(e.key, style: Theme.of(context).textTheme.bodySmall)),
                Expanded(child: Text(e.value!, style: Theme.of(context).textTheme.bodyMedium)),
              ]),
            ),
        ]),
      ),
    );
  }
}
