import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// leave: types, balances, applications, transactions + calendar (weekly offs, holidays).
class LeaveService {
  LeaveService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> typeList() => _api.post(ApiUrls.leaveTypeList, {});
  static Future<ApiResult<dynamic>> typeCreate(Map<String, dynamic> f) => _api.post(ApiUrls.leaveTypeCreate, f);
  static Future<ApiResult<dynamic>> typeUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.leaveTypeUpdate, {'leave_type_id': id, ...f});
  static Future<ApiResult<dynamic>> typeDeactivate(int id) => _api.post(ApiUrls.leaveTypeDeactivate, {'leave_type_id': id});

  static Future<ApiResult<dynamic>> balanceList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.leaveBalanceList, cleanMap(f));
  static Future<ApiResult<dynamic>> balanceInitialize(int leaveYear, {List<int>? leaveTypeIds}) => _api.post(
      ApiUrls.leaveBalanceInit, {'leave_year': leaveYear, if (leaveTypeIds != null && leaveTypeIds.isNotEmpty) 'leave_type_ids': leaveTypeIds});
  static Future<ApiResult<dynamic>> balanceCarryForward({required int fromYear, required bool dryRun, List<int>? leaveTypeIds, bool recalculate = false}) =>
      _api.post(ApiUrls.leaveBalanceCarry, {
        'from_year': fromYear,
        'dry_run': dryRun,
        'recalculate': recalculate,
        if (leaveTypeIds != null && leaveTypeIds.isNotEmpty) 'leave_type_ids': leaveTypeIds,
      });
  static Future<ApiResult<dynamic>> balanceAdjust(int balanceId, num days, String remarks) =>
      _api.post(ApiUrls.leaveBalanceAdjust, {'balance_id': balanceId, 'days': days, 'remarks': remarks});

  static Future<ApiResult<dynamic>> applicationList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.leaveAppList, cleanMap(f));
  static Future<ApiResult<dynamic>> applicationReview(LeaveReviewRequest r) => _api.postRequest(ApiUrls.leaveAppReview, r);
  static Future<ApiResult<dynamic>> applicationCancel(int id) => _api.post(ApiUrls.leaveAppCancel, {'application_id': id});
  static Future<ApiResult<dynamic>> transactionList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.leaveTxnList, cleanMap(f));

  // ---- calendar
  static Future<ApiResult<dynamic>> weeklyOffList({int? shiftId}) => _api.post(ApiUrls.weeklyOffList, cleanMap({'shift_id': shiftId}));
  static Future<ApiResult<dynamic>> weeklyOffCreate(Map<String, dynamic> f) => _api.post(ApiUrls.weeklyOffCreate, f);
  static Future<ApiResult<dynamic>> weeklyOffBulkCreate(Map<String, dynamic> f) => _api.post(ApiUrls.weeklyOffBulkCreate, f);
  static Future<ApiResult<dynamic>> weeklyOffUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.weeklyOffUpdate, {'rule_id': id, ...f});
  static Future<ApiResult<dynamic>> weeklyOffClose(int id, String effectiveTo) =>
      _api.post(ApiUrls.weeklyOffDeactivate, {'rule_id': id, 'effective_to': effectiveTo});

  static Future<ApiResult<dynamic>> holidayList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.holidayList, cleanMap(f));
  static Future<ApiResult<dynamic>> holidayCreate(Map<String, dynamic> f) => _api.post(ApiUrls.holidayCreate, f);
  static Future<ApiResult<dynamic>> holidayUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.holidayUpdate, {'holiday_id': id, ...f});
  static Future<ApiResult<dynamic>> holidayDeactivate(int id) => _api.post(ApiUrls.holidayDeactivate, {'holiday_id': id});
  static Future<ApiResult<dynamic>> holidayImport(UploadFile file) =>
      _api.postForm(ApiUrls.holidayImport, files: [file]);

  /// calendar/employee/ : the logged-in employee's own days. data = {calendar: [...]}
  static Future<ApiResult<dynamic>> myCalendar(String from, String to) =>
      _api.post(ApiUrls.calendarEmployee, {'date_from': from, 'date_to': to});
}
