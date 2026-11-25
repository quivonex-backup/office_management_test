import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// employees, documents, departments, designations.
class EmployeesService {
  EmployeesService._();
  static final ApiService _api = ApiService.instance;

  /// Filters: search, scope, branch_id, department_id, designation_id, access_role_id, reports_to_id, inactive_only.
  static Future<ApiResult<dynamic>> list([Map<String, dynamic> filters = const {}]) =>
      _api.post(ApiUrls.employeeList, cleanMap(filters));
  static Future<ApiResult<dynamic>> myProfile() => _api.post(ApiUrls.employeeMyProfile, {});
  static Future<ApiResult<dynamic>> detail(int id) => _api.post(ApiUrls.employeeDetail, {'employee_id': id});

  /// Always multipart (photo = profile_photo, documents = repeated `documents`).
  static Future<ApiResult<dynamic>> create(Map<String, dynamic> fields, {UploadFile? photo, List<UploadFile> documents = const []}) =>
      _api.postForm(ApiUrls.employeeCreate, fields: fields, files: [if (photo != null) photo, ...documents]);
  static Future<ApiResult<dynamic>> update(int id, Map<String, dynamic> fields, {UploadFile? photo, List<UploadFile> documents = const []}) =>
      _api.postForm(ApiUrls.employeeUpdate, fields: {'employee_id': id, ...fields}, files: [if (photo != null) photo, ...documents]);
  static Future<ApiResult<dynamic>> createUser(int id) => _api.post(ApiUrls.employeeCreateUser, {'employee_id': id});
  static Future<ApiResult<dynamic>> deactivate(int id, {String? lastWorkingDay}) =>
      _api.post(ApiUrls.employeeDeactivate, cleanMap({'employee_id': id, 'last_working_day': lastWorkingDay}));
  static Future<ApiResult<dynamic>> reactivate(int id, {String? joiningDate}) =>
      _api.post(ApiUrls.employeeReactivate, cleanMap({'employee_id': id, 'joining_date': joiningDate}));
  static Future<ApiResult<dynamic>> docUpload(int employeeId, UploadFile file, {String? title, String? description}) =>
      _api.postForm(ApiUrls.employeeDocUpload, fields: cleanMap({'employee_id': employeeId, 'title': title, 'description': description}), files: [file]);
  static Future<ApiResult<dynamic>> docDelete(int documentId) => _api.post(ApiUrls.employeeDocDelete, {'document_id': documentId});

  static Future<ApiResult<dynamic>> departmentList({String? search, bool? isActive}) =>
      _api.post(ApiUrls.departmentList, cleanMap({'search': search, 'is_active': isActive}));
  static Future<ApiResult<dynamic>> departmentCreate(String name, {String? code}) =>
      _api.post(ApiUrls.departmentCreate, cleanMap({'name': name, 'code': code}));
  static Future<ApiResult<dynamic>> departmentUpdate(int id, String name, String code) =>
      _api.post(ApiUrls.departmentUpdate, {'department_id': id, 'name': name, 'code': code});
  static Future<ApiResult<dynamic>> departmentDeactivate(int id) => _api.post(ApiUrls.departmentDeactivate, {'department_id': id});

  static Future<ApiResult<dynamic>> designationList({String? search, bool? isActive}) =>
      _api.post(ApiUrls.designationList, cleanMap({'search': search, 'is_active': isActive}));
  static Future<ApiResult<dynamic>> designationCreate(String name) => _api.post(ApiUrls.designationCreate, {'name': name});
  static Future<ApiResult<dynamic>> designationUpdate(int id, String name) =>
      _api.post(ApiUrls.designationUpdate, {'designation_id': id, 'name': name});
  static Future<ApiResult<dynamic>> designationDeactivate(int id) => _api.post(ApiUrls.designationDeactivate, {'designation_id': id});
}
