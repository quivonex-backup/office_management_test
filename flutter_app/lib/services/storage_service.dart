import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Token + small preference storage.
/// Tokens go to Flutter Secure Storage (Android Keystore). Preferences (saved
/// organization, remembered username, theme) go to SharedPreferences.
/// Mirrors localStorage keys of the React app: om_access, om_refresh, om_org.
class StorageService {
  StorageService._();
  static final StorageService instance = StorageService._();

  static const kAccess = 'om_access';
  static const kRefresh = 'om_refresh';
  static const kOrg = 'om_org';
  static const kRememberUser = 'om_remember_user';
  static const kRememberOff = 'om_remember_off';
  static const kTheme = 'om_theme';

  final FlutterSecureStorage _secure = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<String?> readSecure(String key) async {
    try {
      return await _secure.read(key: key);
    } catch (_) {
      return null;
    }
  }

  Future<void> writeSecure(String key, String value) async {
    try {
      await _secure.write(key: key, value: value);
    } catch (_) {}
  }

  Future<void> deleteSecure(String key) async {
    try {
      await _secure.delete(key: key);
    } catch (_) {}
  }

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  Future<String?> getString(String key) async => (await _prefs).getString(key);
  Future<void> setString(String key, String value) async => (await _prefs).setString(key, value);
  Future<int?> getInt(String key) async => (await _prefs).getInt(key);
  Future<void> setInt(String key, int value) async => (await _prefs).setInt(key, value);
  Future<void> remove(String key) async => (await _prefs).remove(key);
}
