import 'package:flutter/material.dart';

import '../../constants/app_colors.dart';
import '../../constants/app_dimensions.dart';
import '../../utils/responsive_helper.dart';
import 'app_drawer.dart';
import 'app_top_bar.dart';

/// Standard screen frame, responsive:
///  * desktop / wide web (>= 1100): top bar + permanent sidebar + centred content,
///  * tablet / phone: app bar with a hamburger that opens the drawer.
/// Detail screens pass drawer: false and get a back arrow.
/// [hideTitleBar] drops the page title row on desktop (the dashboard shows a greeting instead).
class AppScaffold extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool drawer;
  final bool hideTitleBar;
  final PreferredSizeWidget? bottom;
  const AppScaffold({
    super.key,
    required this.title,
    this.subtitle,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.drawer = true,
    this.hideTitleBar = false,
    this.bottom,
  });

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final sidebar = drawer && box.maxWidth >= AppDimensions.desktop;
        final page = Scaffold(
          backgroundColor: sidebar ? Colors.transparent : null,
          appBar: sidebar
              ? null
              : AppBar(title: Text(title), actions: actions, bottom: bottom, automaticallyImplyLeading: true, scrolledUnderElevation: 0),
          drawer: drawer && !sidebar ? const AppDrawer() : null,
          floatingActionButton: floatingActionButton,
          body: SafeArea(
            child: MaxWidth(
              child: sidebar && !hideTitleBar
                  ? Column(children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 20, 20, 4),
                        child: Row(children: [
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(title, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
                              if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 2), child: Text(subtitle!, style: const TextStyle(fontSize: 14, color: AppColors.textMuted))),
                            ]),
                          ),
                          if (actions != null) ...actions!,
                        ]),
                      ),
                      if (bottom != null) bottom!,
                      Expanded(child: body),
                    ])
                  : body,
            ),
          ),
        );
        if (!sidebar) return page;
        return Scaffold(
          body: Column(children: [
            const AppTopBar(),
            Expanded(
              child: Row(children: [
                SizedBox(
                  width: AppDimensions.sidebarWidth,
                  child: DecoratedBox(
                    decoration: BoxDecoration(border: Border(right: BorderSide(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.6)))),
                    child: const NavigationPanel(),
                  ),
                ),
                Expanded(child: page),
              ]),
            ),
          ]),
        );
      });
}
