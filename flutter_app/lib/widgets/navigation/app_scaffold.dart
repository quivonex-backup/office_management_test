import 'package:flutter/material.dart';

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
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool drawer;
  final bool hideTitleBar;
  final PreferredSizeWidget? bottom;
  const AppScaffold({
    super.key,
    required this.title,
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
          appBar: sidebar && hideTitleBar && bottom == null && (actions == null || actions!.isEmpty)
              ? null
              : AppBar(
                  title: Text(title),
                  actions: actions,
                  bottom: bottom,
                  automaticallyImplyLeading: !sidebar,
                  backgroundColor: sidebar ? Colors.transparent : null,
                  scrolledUnderElevation: 0,
                ),
          drawer: drawer && !sidebar ? const AppDrawer() : null,
          floatingActionButton: floatingActionButton,
          body: SafeArea(child: MaxWidth(child: body)),
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
