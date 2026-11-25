import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'constants/app_strings.dart';
import 'providers/auth_provider.dart';
import 'providers/theme_provider.dart';
import 'routes/route_generator.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final theme = ThemeProvider();
  final auth = AuthProvider();
  await theme.load();
  runApp(MultiProvider(
    providers: [
      ChangeNotifierProvider<ThemeProvider>.value(value: theme),
      ChangeNotifierProvider<AuthProvider>.value(value: auth),
    ],
    child: const OfficeManagerApp(),
  ));
  auth.init(); // restore a saved session; the router redirects when the status changes
}

class OfficeManagerApp extends StatefulWidget {
  const OfficeManagerApp({super.key});
  @override
  State<OfficeManagerApp> createState() => _OfficeManagerAppState();
}

class _OfficeManagerAppState extends State<OfficeManagerApp> {
  late final GoRouter _router = RouteGenerator.create(context.read<AuthProvider>());

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mode = context.watch<ThemeProvider>().mode;
    return MaterialApp.router(
      title: AppStrings.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: mode,
      routerConfig: _router,
    );
  }
}
