import 'package:flutter/material.dart';

import '../../constants/app_dimensions.dart';
import '../../constants/app_strings.dart';

/// Shared frame for the signed-out screens (React AuthLayout).
class AuthLayout extends StatelessWidget {
  final String title;
  final String? lead;
  final Widget child;
  final bool showBack;
  const AuthLayout({super.key, required this.title, this.lead, required this.child, this.showBack = false});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: showBack ? AppBar(backgroundColor: Colors.transparent, foregroundColor: scheme.onSurface) : null,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: AppDimensions.authCardWidth),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(12)),
                    child: Icon(Icons.business_center_outlined, color: scheme.onPrimary),
                  ),
                  const SizedBox(width: 10),
                  Text(AppStrings.appName, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                ]),
                const SizedBox(height: 28),
                Text(title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
                if (lead != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(lead!, style: Theme.of(context).textTheme.bodyMedium)),
                const SizedBox(height: 20),
                child,
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
