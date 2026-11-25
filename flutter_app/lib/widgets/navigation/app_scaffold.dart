import 'package:flutter/material.dart';

import '../../constants/app_dimensions.dart';
import '../../utils/responsive_helper.dart';
import 'app_drawer.dart';

/// Standard screen frame, responsive:
///  * desktop / wide web (>= 1100): permanent sidebar + top bar + centred content,
///  * tablet / phone: top bar with a hamburger that opens the drawer.
/// Detail screens pass drawer: false and get a back arrow.
class AppScaffold extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final bool drawer;
  final PreferredSizeWidget? bottom;
  const AppScaffold({super.key, required this.title, required this.body, this.actions, this.floatingActionButton, this.drawer = true, this.bottom});

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final sidebar = drawer && box.maxWidth >= AppDimensions.desktop;
        final page = Scaffold(
          appBar: AppBar(title: Text(title), actions: actions, bottom: bottom, automaticallyImplyLeading: !sidebar),
          drawer: drawer && !sidebar ? const AppDrawer() : null,
          floatingActionButton: floatingActionButton,
          body: SafeArea(child: MaxWidth(child: body)),
        );
        if (!sidebar) return page;
        return Row(children: [
          const SizedBox(width: AppDimensions.sidebarWidth, child: NavigationPanel()),
          const VerticalDivider(width: 1),
          Expanded(child: page),
        ]);
      });
}
