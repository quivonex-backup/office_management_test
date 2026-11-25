import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// attendance: settings, shifts, assignments, register, corrections, kiosk devices.
class AttendanceService {
  AttendanceService._();
  static final ApiService _api = ApiService.instance;

  // settings: POST {} reads, a body updates
  static Future<ApiResult<dynamic>> settingsGet() => _api.post(ApiUrls.attSettings, {});
  static Future<ApiResult<dynamic>> settingsSave(Map<String, dynamic> f) => _api.post(ApiUrls.attSettings, f);

  static Future<ApiResult<dynamic>> shiftList({bool? isActive}) => _api.post(ApiUrls.shiftList, cleanMap({'is_active': isActive}));
  static Future<ApiResult<dynamic>> shiftCreate(Map<String, dynamic> f) => _api.post(ApiUrls.shiftCreate, f);
  static Future<ApiResult<dynamic>> shiftUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.shiftUpdate, {'shift_id': id, ...f});
  static Future<ApiResult<dynamic>> shiftDeactivate(int id) => _api.post(ApiUrls.shiftDeactivate, {'shift_id': id});

  static Future<ApiResult<dynamic>> assignList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.assignList, cleanMap(f));
  static Future<ApiResult<dynamic>> assignCreate(Map<String, dynamic> f) => _api.post(ApiUrls.assignCreate, f);
  static Future<ApiResult<dynamic>> assignUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.assignUpdate, {'assignment_id': id, ...f});
  static Future<ApiResult<dynamic>> assignBulk(Map<String, dynamic> f) => _api.post(ApiUrls.assignBulk, f);
  static Future<ApiResult<dynamic>> assignPattern(Map<String, dynamic> f) => _api.post(ApiUrls.assignPattern, f);
  static Future<ApiResult<dynamic>> assignBulkClose(List<int> ids, String effectiveTo) =>
      _api.post(ApiUrls.assignBulkClose, {'assignment_ids': ids, 'effective_to': effectiveTo});

  static Future<ApiResult<dynamic>> attendanceList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.attList, cleanMap(f));
  static Future<ApiResult<dynamic>> bulkMarkAbsent(Map<String, dynamic> f) => _api.post(ApiUrls.attBulkAbsent, f);

  static Future<ApiResult<dynamic>> correctionList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.correctionList, cleanMap(f));
  static Future<ApiResult<dynamic>> correctionMissedDay(MissedDayRequest r) => _api.postRequest(ApiUrls.correctionMissedDay, r);
  static Future<ApiResult<dynamic>> correctionCancel(int id) => _api.post(ApiUrls.correctionCancel, {'correction_id': id});
  static Future<ApiResult<dynamic>> correctionReview(CorrectionReviewRequest r) => _api.postRequest(ApiUrls.correctionReview, r);

  static Future<ApiResult<dynamic>> deviceList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.deviceList, cleanMap(f));
  static Future<ApiResult<dynamic>> deviceCreate(Map<String, dynamic> f) => _api.post(ApiUrls.deviceCreate, cleanMap(f));
  /// branch_id: null clears the branch, so it is sent as given.
  static Future<ApiResult<dynamic>> deviceUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.deviceUpdate, {'device_id': id, ...f});
  static Future<ApiResult<dynamic>> deviceResetPassword(int id) => _api.post(ApiUrls.deviceResetPassword, {'device_id': id});
  static Future<ApiResult<dynamic>> deviceDeactivate(int id) => _api.post(ApiUrls.deviceDeactivate, {'device_id': id});
}
