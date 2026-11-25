import 'package:flutter/material.dart';

import '../../constants/app_strings.dart';

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.error_outline, size: 52, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(minimumSize: const Size(140, 44)),
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text(AppStrings.retry),
              ),
            ],
          ]),
        ),
      );
}
