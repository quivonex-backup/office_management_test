/// Spacing, breakpoints and size limits shared by all screens.
class AppDimensions {
  AppDimensions._();

  // breakpoints (logical px)
  static const double tablet = 700; // >= tablet: collapsible rail
  static const double desktop = 1100; // >= desktop: permanent sidebar

  // spacing
  static const double xs = 4, sm = 8, md = 12, lg = 16, xl = 24;
  static const double radius = 12;

  // layout
  static const double sidebarWidth = 272;
  static const double railWidth = 76;
  static const double maxContentWidth = 1280;
  static const double maxFormWidth = 760;
  static const double authCardWidth = 420;
}
