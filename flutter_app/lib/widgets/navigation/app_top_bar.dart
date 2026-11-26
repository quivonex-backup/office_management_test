import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../api/api_url.dart';
import '../../constants/app_colors.dart';
import '../../constants/app_dimensions.dart';
import '../../constants/app_menu.dart';
import '../../constants/app_strings.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/communications_service.dart';
import '../../utils/helpers.dart';
import '../dialogs/app_dialogs.dart';

/// Desktop / web top bar: brand, page search, notification bell, appearance, account menu.
class AppTopBar extends StatefulWidget {
  const AppTopBar({super.key});
  @override
  State<AppTopBar> createState() => _AppTopBarState();
}

class _AppTopBarState extends State<AppTopBar> {
  int _unread = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _loadCount();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _loadCount());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _loadCount() async {
    final r = await CommunicationsService.notifCount();
    if (!mounted || !r.ok) return;
    setState(() => _unread = asInt(asMap(r.data)['unread_count']) ?? 0);
  }

  Widget _roundButton(BuildContext context, IconData icon, String tip, VoidCallback onTap, {bool dot = false}) {
    final scheme = Theme.of(context).colorScheme;
    return Tooltip(
      message: tip,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(color: scheme.surfaceContainerHighest.withValues(alpha: 0.5), shape: BoxShape.circle),
          child: Stack(alignment: Alignment.center, children: [
            Icon(icon, size: 21, color: AppColors.textMuted),
            if (dot) Positioned(right: 11, top: 10, child: Container(width: 8, height: 8, decoration: BoxDecoration(color: scheme.error, shape: BoxShape.circle))),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scheme = Theme.of(context).colorScheme;
    final p = auth.profile;
    final role = p == null ? '' : (p.isOrgOwner ? 'Owner' : (p.accessRole?.name ?? p.accountRole ?? ''));

    final pages = <MenuItem>[
      for (final g in appMenu)
        for (final i in g.items)
          if ((!i.employeeOnly || auth.hasEmployee) && auth.canAny(i.anyOf)) i,
    ];

    return Container(
      height: 68,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(color: Theme.of(context).cardTheme.color, border: Border(bottom: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.6)))),
      child: Row(children: [
        SizedBox(
          width: AppDimensions.sidebarWidth - 40,
          child: Row(children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(12)),
              child: Icon(Icons.business_center_outlined, color: scheme.primary),
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(AppStrings.appName, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          ]),
        ),
        const SizedBox(width: 20),
        Expanded(
          child: Align(
            alignment: Alignment.centerLeft,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: Autocomplete<MenuItem>(
                displayStringForOption: (i) => i.label,
                optionsBuilder: (v) {
                  final q = v.text.trim().toLowerCase();
                  if (q.isEmpty) return const Iterable<MenuItem>.empty();
                  return pages.where((i) => i.label.toLowerCase().contains(q)).take(8);
                },
                onSelected: (i) => context.go(i.path),
                optionsViewBuilder: (context, onSelected, options) => Align(
                  alignment: Alignment.topLeft,
                  child: Material(
                    elevation: 6,
                    borderRadius: BorderRadius.circular(14),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 420, maxHeight: 320),
                      child: ListView(shrinkWrap: true, padding: const EdgeInsets.symmetric(vertical: 6), children: [
                        for (final i in options) ListTile(dense: true, leading: Icon(i.icon, size: 20), title: Text(i.label), onTap: () => onSelected(i)),
                      ]),
                    ),
                  ),
                ),
                fieldViewBuilder: (context, controller, focus, onSubmit) => TextField(
                  controller: controller,
                  focusNode: focus,
                  decoration: InputDecoration(
                    hintText: 'Search pages...',
                    hintStyle: const TextStyle(color: AppColors.textMuted, fontSize: 14),
                    prefixIcon: const Icon(Icons.search, color: AppColors.textMuted),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(vertical: 13),
                    filled: true,
                    fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.4),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.outlineVariant)),
                    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.primary)),
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        _roundButton(context, Icons.notifications_none, 'Notifications', () => context.go('/notifications'), dot: _unread > 0),
        const SizedBox(width: 10),
        _roundButton(context, Icons.settings_outlined, 'Appearance', () => context.go('/appearance')),
        const SizedBox(width: 14),
        PopupMenuButton<String>(
          tooltip: 'Account',
          offset: const Offset(0, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          onSelected: (v) async {
            if (v == 'logout') {
              final ok = await AppDialogs.confirm(context, title: 'Log out', message: 'Do you want to log out?', confirmLabel: 'Log out');
              if (ok) await auth.logout();
            } else {
              context.go(v);
            }
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: '/profile', child: Text('My profile')),
            PopupMenuItem(value: '/change-password', child: Text('Change password')),
            PopupMenuItem(value: '/appearance', child: Text('Appearance')),
            PopupMenuDivider(),
            PopupMenuItem(value: 'logout', child: Text('Log out')),
          ],
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: AppColors.accentSoft,
              foregroundColor: scheme.primary,
              backgroundImage: (p?.profilePhoto ?? '').isNotEmpty ? NetworkImage(ApiUrls.media(p!.profilePhoto)) : null,
              child: (p?.profilePhoto ?? '').isEmpty ? Text(Fmt.initials(p?.fullName ?? ''), style: const TextStyle(fontWeight: FontWeight.w700)) : null,
            ),
            const SizedBox(width: 10),
            Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
              Text(p?.fullName ?? '', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              Text(role, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
            ]),
          ]),
        ),
      ]),
    );
  }
}
