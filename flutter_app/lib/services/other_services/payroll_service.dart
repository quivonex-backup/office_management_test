import '../../api/api_response.dart';
import '../../api/api_request.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// payroll (admin side).
class PayrollService {
  PayrollService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> settingsGet() => _api.post(ApiUrls.payrollSettings, {});
  static Future<ApiResult<dynamic>> settingsSave(Map<String, dynamic> f) => _api.post(ApiUrls.payrollSettings, f);
  static Future<ApiResult<dynamic>> statutoryGet() => _api.post(ApiUrls.payrollStatutory, {});
  static Future<ApiResult<dynamic>> statutorySave(Map<String, dynamic> f) => _api.post(ApiUrls.payrollStatutory, f);

  static Future<ApiResult<dynamic>> componentList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.componentList, cleanMap(f));
  static Future<ApiResult<dynamic>> componentCreate(Map<String, dynamic> f) => _api.post(ApiUrls.componentCreate, f);
  static Future<ApiResult<dynamic>> componentDetail(int id) => _api.post(ApiUrls.componentDetail, {'component_id': id});
  static Future<ApiResult<dynamic>> componentUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.componentUpdate, {'component_id': id, ...f});
  static Future<ApiResult<dynamic>> componentDeactivate(int id) => _api.post(ApiUrls.componentDeactivate, {'component_id': id});

  static Future<ApiResult<dynamic>> structureList({bool? isActive}) => _api.post(ApiUrls.structureList, cleanMap({'is_active': isActive}));
  static Future<ApiResult<dynamic>> structureCreate(Map<String, dynamic> f) => _api.post(ApiUrls.structureCreate, f);
  static Future<ApiResult<dynamic>> structureUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.structureUpdate, {'structure_id': id, ...f});
  static Future<ApiResult<dynamic>> structureDeactivate(int id) => _api.post(ApiUrls.structureDeactivate, {'structure_id': id});

  static Future<ApiResult<dynamic>> assignmentList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.salaryAssignList, cleanMap(f));
  static Future<ApiResult<dynamic>> assignmentCreate(Map<String, dynamic> f) => _api.post(ApiUrls.salaryAssignCreate, f);
  static Future<ApiResult<dynamic>> assignmentUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.salaryAssignUpdate, {'assignment_id': id, ...f});
  static Future<ApiResult<dynamic>> assignmentBulk(Map<String, dynamic> f) => _api.post(ApiUrls.salaryAssignBulk, f);
  static Future<ApiResult<dynamic>> assignmentBulkClose(List<int> ids, String effectiveTo) =>
      _api.post(ApiUrls.salaryAssignBulkClose, {'assignment_ids': ids, 'effective_to': effectiveTo});

  /// body: {period_start, period_end} OR {reference_month}
  static Future<ApiResult<dynamic>> runPreview(Map<String, dynamic> f) => _api.post(ApiUrls.runPreview, f);
  static Future<ApiResult<dynamic>> runCreate(String periodStart, String periodEnd) =>
      _api.post(ApiUrls.runCreate, {'period_start': periodStart, 'period_end': periodEnd});
  static Future<ApiResult<dynamic>> runList({String? status}) => _api.post(ApiUrls.runList, cleanMap({'status': status}));
  static Future<ApiResult<dynamic>> runDetail(int id) => _api.post(ApiUrls.runDetail, {'payroll_run_id': id});
  static Future<ApiResult<dynamic>> runGenerate(int id) => _api.post(ApiUrls.runGenerate, {'payroll_run_id': id});
  static Future<ApiResult<dynamic>> runReopen(int id, String reason) => _api.post(ApiUrls.runReopen, {'payroll_run_id': id, 'reason': reason});
  static Future<ApiResult<dynamic>> runFinalize(int id) => _api.post(ApiUrls.runFinalize, {'payroll_run_id': id});

  static Future<ApiResult<dynamic>> recordList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.recordList, cleanMap(f));
  static Future<ApiResult<dynamic>> recordUpdate(Map<String, dynamic> f) => _api.post(ApiUrls.recordUpdate, cleanMap(f));
  static Future<ApiResult<dynamic>> paymentRecord(Map<String, dynamic> f) => _api.post(ApiUrls.paymentRecord, f);
  static Future<ApiResult<dynamic>> paymentBulk(Map<String, dynamic> f) => _api.post(ApiUrls.paymentBulk, f);
  static Future<ApiResult<dynamic>> paymentList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.paymentList, cleanMap(f));
  static Future<ApiResult<dynamic>> paymentVoid(int id, String reason) => _api.post(ApiUrls.paymentVoid, {'payment_id': id, 'reason': reason});
  static Future<ApiResult<BlobFile>> payslipDownload(int recordId) =>
      _api.postBlob(ApiUrls.payslipDownload, {'payroll_record_id': recordId}, 'payslip.pdf');
  static Future<ApiResult<dynamic>> calculate(Map<String, dynamic> f) => _api.post(ApiUrls.payrollCalculator, cleanMap(f));
}
