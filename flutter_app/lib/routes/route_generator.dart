import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../constants/app_strings.dart';
import '../providers/auth_provider.dart';
import '../screens/auth/forgot_password_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/org_picker_screen.dart';
import '../widgets/loaders/loading_view.dart';
import 'app_routes.dart';

/// Builds the app's GoRouter. URLs are the React paths, so the browser's address bar, refresh,
/// back button and deep links work on Flutter Web, and Android back works the same way.
/// Auth state decides where you may be (see [_redirect]).
class RouteGenerator {
  RouteGenerator._();

  static const _authPaths = {AppRoutes.login, AppRoutes.forgotPassword, AppRoutes.selectOrganization, AppRoutes.noAccess, AppRoutes.splash};

  static GoRouter create(AuthProvider auth) => GoRouter(
        initialLocation: AppRoutes.home,
        refreshListenable: auth,
        redirect: (context, state) => _redirect(auth, state),
        errorBuilder: (context, state) => const _NotFound(),
        routes: [
          GoRoute(path: '/', redirect: (_, __) => AppRoutes.home),
          GoRoute(path: AppRoutes.splash, builder: (_, __) => const Scaffold(body: LoadingView())),
          GoRoute(path: AppRoutes.login, builder: (_, __) => const LoginScreen()),
          GoRoute(path: AppRoutes.forgotPassword, builder: (_, __) => const ForgotPasswordScreen()),
          GoRoute(path: AppRoutes.selectOrganization, builder: (_, __) => const OrgPickerScreen()),
          GoRoute(path: AppRoutes.noAccess, builder: (_, __) => const NoAccessScreen()),
          for (final e in AppRoutes.pages.entries)
            GoRoute(
              path: e.key,
              pageBuilder: (context, state) => NoTransitionPage<void>(
                key: state.pageKey,
                child: RouteGuard(path: e.key, child: e.value(context)),
              ),
            ),
        ],
      );

  static String? _redirect(AuthProvider auth, GoRouterState state) {
    final path = state.uri.path;
    final here = state.uri.toString();
    switch (auth.status) {
      case AuthStatus.booting:
        // remember where the browser was opened so a refresh on /employees comes back to it
        return path == AppRoutes.splash ? null : '${AppRoutes.splash}?from=${Uri.encodeComponent(here)}';
      case AuthStatus.out:
        if (path == AppRoutes.login || path == AppRoutes.forgotPassword) return null;
        final from = path == AppRoutes.splash ? state.uri.queryParameters['from'] : here;
        final keep = from != null && from != '/' && !_authPaths.contains(Uri.parse(from).path);
        return keep ? '${AppRoutes.login}?from=${Uri.encodeComponent(from)}' : AppRoutes.login;
      case AuthStatus.needOrg:
        return path == AppRoutes.selectOrganization ? null : AppRoutes.selectOrganization;
      case AuthStatus.noAccess:
        return path == AppRoutes.noAccess ? null : AppRoutes.noAccess;
      case AuthStatus.ready:
        if (_authPaths.contains(path) || path == '/') {
          final from = state.uri.queryParameters['from'];
          if (from != null && from.startsWith('/') && !_authPaths.contains(Uri.parse(from).path)) return from;
          return AppRoutes.home;
        }
        return null;
    }
  }
}

class _NotFound extends StatelessWidget {
  const _NotFound();

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text(AppStrings.appName)),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.search_off, size: 52),
              const SizedBox(height: 12),
              const Text('That page does not exist.'),
              const SizedBox(height: 16),
              FilledButton(onPressed: () => context.go(AppRoutes.home), style: FilledButton.styleFrom(minimumSize: const Size(180, 46)), child: const Text('Go to dashboard')),
            ]),
          ),
        ),
      );
}
