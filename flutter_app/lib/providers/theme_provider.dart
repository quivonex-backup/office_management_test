import 'package:flutter/material.dart';

import '../services/storage_service.dart';

class ThemeProvider extends ChangeNotifier {
  ThemeMode mode = ThemeMode.light;

  Future<void> load() async {
    final v = await StorageService.instance.getString(StorageService.kTheme);
    mode = v == 'dark' ? ThemeMode.dark : (v == 'system' ? ThemeMode.system : ThemeMode.light);
    notifyListeners();
  }

  Future<void> setMode(ThemeMode m) async {
    mode = m;
    notifyListeners();
    await StorageService.instance.setString(StorageService.kTheme, m == ThemeMode.dark ? 'dark' : (m == ThemeMode.system ? 'system' : 'light'));
  }
}
