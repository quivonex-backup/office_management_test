import 'package:flutter/material.dart';

class PrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool busy;
  final IconData? icon;
  const PrimaryButton({super.key, required this.label, required this.onPressed, this.busy = false, this.icon});

  @override
  Widget build(BuildContext context) => FilledButton(
        onPressed: busy ? null : onPressed,
        child: busy
            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
            : Row(mainAxisAlignment: MainAxisAlignment.center, mainAxisSize: MainAxisSize.min, children: [
                if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 8)],
                Text(label),
              ]),
      );
}
