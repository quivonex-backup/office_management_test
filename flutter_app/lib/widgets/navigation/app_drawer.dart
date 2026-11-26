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
          padding: const EdgeInsets.fromLTRB(22, 16, 16, 6),
          child: Text(g.section.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: 1.1, color: AppColors.textMuted, fontWeight: FontWeight.w600)),
        ));
        lastSection = g.section;
      }
      final hasActive = items.any((i) => i.path == current);
      if (items.length == 1) {
        groups.add(_tile(context, items.first, current == items.first.path));
      } else {
        groups.add(Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            key: PageStorageKey('menu-${g.title}'),
            initiallyExpanded: hasActive || g.title == 'Home',
            tilePadding: const EdgeInsets.symmetric(horizontal: 22),
            childrenPadding: EdgeInsets.zero,
            iconColor: scheme.primary,
            leading: Icon(g.icon, size: 22, color: hasActive ? scheme.primary : AppColors.textMuted),
            title: Text(g.title, style: TextStyle(fontSize: 14, fontWeight: hasActive ? FontWeight.w600 : FontWeight.w500, color: hasActive ? scheme.primary : null)),
            children: [for (final i in items) _tile(context, i, current == i.path, indent: true)],
          ),
        ));
      }
    }

    final help = appMenu.firstWhere((g) => g.hidden).items.where(visible).toList();
    final support = findMenuItem('/helpdesk/my');
    final supportVisible = support != null && visible(support);

    return Material(
      color: Theme.of(context).cardTheme.color,
      child: SafeArea(
        child: Column(children: [
          if (inDrawer)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: AppColors.accentSoft,
                  foregroundColor: scheme.primary,
                  backgroundImage: (p?.profilePhoto ?? '').isNotEmpty ? NetworkImage(ApiUrls.media(p!.profilePhoto)) : null,
                  child: (p?.profilePhoto ?? '').isEmpty ? Text(Fmt.initials(p?.fullName ?? ''), style: const TextStyle(fontWeight: FontWeight.w700)) : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(p?.fullName ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    Text(p?.organizationName ?? AppStrings.appName, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
                  ]),
                ),
              ]),
            ),
          Expanded(child: ListView(padding: const EdgeInsets.only(top: 6, bottom: 8), children: groups)),
          const Divider(),
          for (final i in help) _tile(context, i, current == i.path),
          if (auth.organizations.length > 1)
            _plain(context, Icons.swap_horiz, 'Switch organization', AppColors.textMuted, () {
              if (inDrawer) Navigator.of(context).pop();
              auth.switchOrganization();
            }),
          _plain(context, Icons.logout, 'Log out', scheme.error, () async {
            final ok = await AppDialogs.confirm(context, title: 'Log out', message: 'Do you want to log out?', confirmLabel: 'Log out');
            if (ok) await auth.logout(); // the router sends you to Login
          }),
          if (supportVisible)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 6, 14, 14),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => _go(context, '/helpdesk/my'),
                child: Ink(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(16)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(Icons.headset_mic_outlined, color: scheme.primary),
                    const SizedBox(height: 8),
                    const Text('Need Help?', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                    const Text('Contact support team', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                  ]),
                ),
              ),
            ),
        ]),
      ),
    );
  }

  Widget _plain(BuildContext context, IconData icon, String label, Color color, VoidCallback onTap) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 1),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(children: [
              Icon(icon, size: 21, color: color),
              const SizedBox(width: 14),
              Text(label, style: TextStyle(fontSize: 14, color: color, fontWeight: FontWeight.w500)),
            ]),
          ),
        ),
      );

  Widget _tile(BuildContext context, MenuItem i, bool active, {bool indent = false}) {
    final scheme = Theme.of(context).colorScheme;
    final color = active ? scheme.primary : AppColors.textMuted;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (i.divider != null && indent)
        Padding(
          padding: const EdgeInsets.fromLTRB(60, 8, 16, 2),
          child: Text(i.divider!.toUpperCase(), style: const TextStyle(fontSize: 10.5, color: AppColors.textMuted, letterSpacing: 0.8)),
        ),
      Padding(
        padding: EdgeInsets.fromLTRB(indent ? 22 : 12, 1, 12, 1),
        child: Material(
          color: active ? AppColors.accentSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => _go(context, i.path),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(children: [
                Icon(i.icon, size: 21, color: color),
                const SizedBox(width: 14),
                Expanded(child: Text(i.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 14, fontWeight: active ? FontWeight.w600 : FontWeight.w500, color: active ? scheme.primary : null))),
              ]),
            ),
          ),
        ),
      ),
    ]);
  }
}
