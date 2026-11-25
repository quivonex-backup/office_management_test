import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../api/api_url.dart';
import '../../constants/app_colors.dart';
import '../../constants/app_menu.dart';
import '../../constants/app_strings.dart';
import '../../providers/auth_provider.dart';
import '../../utils/helpers.dart';
import '../dialogs/app_dialogs.dart';

/// Mobile / tablet: the menu as a slide-in drawer.
class AppDrawer extends StatelessWidget {
  const AppDrawer({super.key});
  @override
  Widget build(BuildContext context) => const Drawer(child: NavigationPanel(inDrawer: true));
}

/// The React sidebar. Items are filtered by the same permission codes (anyOf / employeeOnly).
/// Used inside the [Drawer] (phones, tablets) and as the permanent sidebar on desktop / web.
class NavigationPanel extends StatelessWidget {
  final bool inDrawer;
  const NavigationPanel({super.key, this.inDrawer = false});

  void _go(BuildContext context, String path) {
    if (inDrawer) Navigator.of(context).pop(); // close the drawer
    if (GoRouterState.of(context).uri.path == path) return;
    context.go(path);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scheme = Theme.of(context).colorScheme;
    final p = auth.profile;
    final current = GoRouterState.of(context).uri.path;

    bool visible(MenuItem i) {
      if (i.employeeOnly && !auth.hasEmployee) return false;
      return auth.canAny(i.anyOf);
    }

    final groups = <Widget>[];
    String? lastSection;
    for (final g in appMenu) {
      if (g.hidden) continue;
      final items = g.items.where(visible).toList();
      if (items.isEmpty) continue;
      if (g.section != lastSection) {
        groups.add(Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
          child: Text(g.section.toUpperCase(), style: Theme.of(context).textTheme.labelSmall?.copyWith(letterSpacing: 1.1, color: AppColors.textMuted)),
        ));
        lastSection = g.section;
      }
      final hasActive = items.any((i) => i.path == current);
      if (items.length == 1) {
        final i = items.first;
        groups.add(_tile(context, i, current == i.path));
      } else {
        groups.add(ExpansionTile(
          key: PageStorageKey('menu-${g.title}'),
          initiallyExpanded: hasActive || g.title == 'Home',
          leading: Icon(g.icon, color: hasActive ? scheme.primary : null),
          title: Text(g.title, style: TextStyle(fontWeight: hasActive ? FontWeight.w700 : FontWeight.w500)),
          children: [for (final i in items) _tile(context, i, current == i.path, indent: true)],
        ));
      }
    }

    return Material(
      color: Theme.of(context).drawerTheme.backgroundColor ?? scheme.surface,
      child: SafeArea(
        child: Column(children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 14),
            color: scheme.primary,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              CircleAvatar(
                radius: 26,
                backgroundColor: Colors.white24,
                backgroundImage: (p?.profilePhoto ?? '').isNotEmpty ? NetworkImage(ApiUrls.media(p!.profilePhoto)) : null,
                child: (p?.profilePhoto ?? '').isEmpty ? Text(Fmt.initials(p?.fullName ?? ''), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)) : null,
              ),
              const SizedBox(height: 10),
              Text(p?.fullName ?? '', style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
              Text(p?.organizationName ?? AppStrings.appName, style: const TextStyle(color: Colors.white70, fontSize: 12.5)),
              if (p?.accessRole != null) Text(p!.accessRole!.name, style: const TextStyle(color: Colors.white70, fontSize: 12)),
            ]),
          ),
          Expanded(child: ListView(padding: EdgeInsets.zero, children: groups)),
          const Divider(height: 1),
          for (final i in appMenu.firstWhere((g) => g.hidden).items) _tile(context, i, current == i.path, dense: true),
          if (auth.organizations.length > 1)
            ListTile(
              dense: true,
              leading: const Icon(Icons.swap_horiz),
              title: const Text('Switch organization'),
              onTap: () {
                if (inDrawer) Navigator.of(context).pop();
                auth.switchOrganization();
              },
            ),
          ListTile(
            dense: true,
            leading: Icon(Icons.logout, color: scheme.error),
            title: Text('Log out', style: TextStyle(color: scheme.error)),
            onTap: () async {
              final ok = await AppDialogs.confirm(context, title: 'Log out', message: 'Do you want to log out?', confirmLabel: 'Log out');
              if (ok) await auth.logout(); // the router sends you to Login
            },
          ),
        ]),
      ),
    );
  }

  Widget _tile(BuildContext context, MenuItem i, bool active, {bool indent = false, bool dense = false}) {
    final scheme = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (i.divider != null && indent)
        Padding(
          padding: const EdgeInsets.fromLTRB(72, 8, 16, 2),
          child: Text(i.divider!.toUpperCase(), style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textMuted, letterSpacing: 0.8)),
        ),
      ListTile(
        dense: dense || indent,
        selected: active,
        selectedColor: scheme.primary,
        selectedTileColor: scheme.primary.withValues(alpha: 0.08),
        contentPadding: EdgeInsets.only(left: indent ? 28 : 16, right: 12),
        leading: Icon(i.icon, size: 22),
        title: Text(i.label),
        onTap: () => _go(context, i.path),
      ),
    ]);
  }
}
