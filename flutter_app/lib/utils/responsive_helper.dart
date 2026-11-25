import 'package:flutter/material.dart';

import '../constants/app_dimensions.dart';

enum ScreenSize { mobile, tablet, desktop }

/// Screen-size helpers. Use `Responsive.of(context)` or `Responsive.fromWidth(w)` inside a LayoutBuilder.
class Responsive {
  Responsive._();

  static ScreenSize fromWidth(double w) =>
      w >= AppDimensions.desktop ? ScreenSize.desktop : (w >= AppDimensions.tablet ? ScreenSize.tablet : ScreenSize.mobile);

  static ScreenSize of(BuildContext c) => fromWidth(MediaQuery.sizeOf(c).width);
  static bool isMobile(BuildContext c) => of(c) == ScreenSize.mobile;
  static bool isDesktop(BuildContext c) => of(c) == ScreenSize.desktop;

  /// Grid columns for stat cards / tiles at a given width.
  static int columns(double w, {int mobile = 2, int tablet = 3, int desktop = 4}) {
    switch (fromWidth(w)) {
      case ScreenSize.mobile:
        return mobile;
      case ScreenSize.tablet:
        return tablet;
      case ScreenSize.desktop:
        return desktop;
    }
  }
}

/// Centers [child] and limits its width on big screens (forms, lists).
class MaxWidth extends StatelessWidget {
  final double width;
  final Widget child;
  const MaxWidth({super.key, this.width = AppDimensions.maxContentWidth, required this.child});

  @override
  Widget build(BuildContext context) => Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(constraints: BoxConstraints(maxWidth: width), child: child),
      );
}
