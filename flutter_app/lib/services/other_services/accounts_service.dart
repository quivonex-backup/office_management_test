import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// branches, permissions and access roles.
class AccountsService {
  AccountsService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> branchList({String? search, bool? isActive}) =>
      _api.post(ApiUrls.branchList, cleanMap({'search': search, 'is_active': isActive}));
  static Future<ApiResult<dynamic>> branchCreate(Map<String, dynamic> body) => _api.post(ApiUrls.branchCreate, body);
  static Future<ApiResult<dynamic>> branchUpdate(int id, Map<String, dynamic> body) =>
      _api.post(ApiUrls.branchUpdate, {'branch_id': id, ...body});
  static Future<ApiResult<dynamic>> branchDeactivate(int id) => _api.post(ApiUrls.branchDeactivate, {'branch_id': id});

  static Future<ApiResult<dynamic>> permissionList() => _api.post(ApiUrls.permissionList, {});
  static Future<ApiResult<dynamic>> accessRoleList({bool? isActive}) =>
      _api.post(ApiUrls.accessRoleList, cleanMap({'is_active': isActive}));
  static Future<ApiResult<dynamic>> accessRoleCreate(AccessRoleRequest r) => _api.postRequest(ApiUrls.accessRoleCreate, r);
  static Future<ApiResult<dynamic>> accessRoleUpdate(AccessRoleRequest r) => _api.postRequest(ApiUrls.accessRoleUpdate, r);
  static Future<ApiResult<dynamic>> accessRoleDeactivate(int id) => _api.post(ApiUrls.accessRoleDeactivate, {'access_role_id': id});
}
