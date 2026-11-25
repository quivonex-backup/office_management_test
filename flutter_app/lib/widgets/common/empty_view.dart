import 'package:flutter/material.dart';

import '../../constants/app_strings.dart';

class EmptyView extends StatelessWidget {
  final String message;
  final IconData icon;
  final Widget? action;
  const EmptyView({super.key, this.message = AppStrings.empty, this.icon = Icons.inbox_outlined, this.action});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 52, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyLarge),
            if (action != null) ...[const SizedBox(height: 16), action!],
          ]),
        ),
      );
}
