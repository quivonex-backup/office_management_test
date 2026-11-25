import 'package:flutter/foundation.dart';

import '../api/api_response.dart';
import '../api/api_service.dart';
import '../constants/app_strings.dart';
import '../models/response/organization_response.dart';
import '../models/response/profile_response.dart';
import '../services/auth_service.dart';
import '../services/other_services/location_service.dart';
import '../services/storage_service.dart';

/// booting -> restoring a saved session | out -> Login | needOrg -> pick an organization
/// noAccess -> account has no organization | ready -> the panel
enum AuthStatus { booting, out, needOrg, noAccess, ready }

/// Port of React core/auth.tsx.
/// Login steps: login -> my-organizations -> (pick one if several) -> my-profile.
class AuthProvider extends ChangeNotifier {
  final ApiService _api = ApiService.instance;
  final StorageService _store = StorageService.instance;

  AuthStatus status = AuthStatus.booting;
  Profile? profile;
  List<Organization> organizations = [];
  String? notice;
  bool _started = false;

  Organization? get org {
    final id = profile?.organizationId;
    for (final o in organizations) {
      if (o.id == id) return o;
    }
    return null;
  }

  void setNotice(String message) {
    notice = message;
    notifyListeners();
  }

  void clearNotice() {
    notice = null;
    notifyListeners();
  }

  /// Restore the saved session. Call once at app start.
  Future<void> init() async {
    if (_started) return;
    _started = true;
    _api.onSessionExpired = () => _reset(AppStrings.sessionExpired);
    await _api.loadTokens();
    if (!_api.hasTokens) {
      status = AuthStatus.out;
      notifyListeners();
      return;
    }
    final err = await _bootstrap();
    if (err != null) _reset(err);
  }

  void _reset(String? message) {
    profile = null;
    organizations = [];
    _api.activeOrgId = null;
    LocationService.clearCache();
    notice = message;
    status = AuthStatus.out;
    notifyListeners();
  }

  Future<String?> _loadProfile() async {
    final p = await AuthService.myProfile();
    if (!p.ok || p.data == null) return p.status == 401 ? null : p.message;
    profile = p.data;
    status = p.data!.hasOrganization ? AuthStatus.ready : AuthStatus.noAccess;
    notifyListeners();
    return null;
  }

  /// organizations -> (organization choice) -> my-profile. Returns an error message or null.
  Future<String?> _bootstrap() async {
    final orgs = await AuthService.myOrganizations();
    if (!orgs.ok) return orgs.status == 401 ? null : orgs.message;
    final list = orgs.data ?? [];
    organizations = list;
    if (list.length > 1) {
      final saved = await _store.getInt(StorageService.kOrg);
      if (saved != null && list.any((o) => o.id == saved)) {
        _api.activeOrgId = saved;
      } else {
        _api.activeOrgId = null;
        profile = null;
        status = AuthStatus.needOrg;
        notifyListeners();
        return null;
      }
    } else {
      _api.activeOrgId = null; // single-organization users never send organization_id
    }
    return _loadProfile();
  }

  Future<ApiResult<dynamic>> login(String username, String password, bool remember) async {
    final r = await AuthService.login(username, password);
    if (!r.ok || r.data is! Map) return r;
    final d = r.data as Map;
    await _api.setTokens(d['access'].toString(), d['refresh'].toString(), persist: remember);
    await _store.remove(StorageService.kOrg);
    notice = null;
    final err = await _bootstrap();
    if (err != null) {
      await _api.clearTokens();
      _reset(null);
      return ApiResult<dynamic>.failure(err);
    }
    return r;
  }

  Future<void> logout() async {
    await _api.clearTokens();
    _reset(null);
  }

  Future<String?> selectOrganization(int id) async {
    await _store.setInt(StorageService.kOrg, id);
    _api.activeOrgId = id;
    LocationService.clearCache();
    return _loadProfile();
  }

  void switchOrganization() {
    status = AuthStatus.needOrg;
    notifyListeners();
  }

  /// Reload my-profile + organizations (after editing profile / organization).
  Future<void> refresh() async {
    final orgs = await AuthService.myOrganizations();
    if (orgs.ok && orgs.data != null) organizations = orgs.data!;
    await _loadProfile();
  }

  /// owner has every permission; otherwise the role must have the code.
  bool can(String code) {
    final p = profile;
    return p != null && (p.isOrgOwner || p.permissions.contains(code));
  }

  bool canAny([List<String>? codes]) => codes == null || codes.isEmpty || codes.any(can);

  bool get hasEmployee => profile?.employee != null;
}
