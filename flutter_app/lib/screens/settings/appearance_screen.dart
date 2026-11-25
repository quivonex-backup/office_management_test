import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/theme_provider.dart';
import '../../widgets/navigation/app_scaffold.dart';

/// Light / dark / system theme (React Appearance, reduced to what a phone needs).
/// Saved on this device.
class AppearanceScreen extends StatelessWidget {
  const AppearanceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = context.watch<ThemeProvider>();
    const options = [
      (ThemeMode.light, 'Light', 'Clean light surfaces.', Icons.light_mode_outlined),
      (ThemeMode.dark, 'Dark', 'Dark page and surfaces, easy on the eyes at night.', Icons.dark_mode_outlined),
      (ThemeMode.system, 'Follow device', 'Switches with your phone setting.', Icons.settings_suggest_outlined),
    ];
    return AppScaffold(
      title: 'Appearance',
      body: ListView(padding: const EdgeInsets.all(14), children: [
        Text('Pick a theme. It is saved on this device.', style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 12),
        for (final o in options)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ListTile(
              leading: Icon(o.$4),
              title: Text(o.$2, style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(o.$3),
              trailing: t.mode == o.$1 ? Icon(Icons.check_circle, color: Theme.of(context).colorScheme.primary) : null,
              onTap: () => t.setMode(o.$1),
            ),
          ),
        const SizedBox(height: 6),
        Text('Status colours (green, amber, red) keep their meaning in every theme.', style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}
