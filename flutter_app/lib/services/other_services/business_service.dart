import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// clients, vendors, projects, tasks, expenses, reimbursements, project payments.
/// Files go as multipart; everything else as JSON (same rule as the React `save()` helper).
class BusinessService {
  BusinessService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> _save(String path, Map<String, dynamic> fields, List<UploadFile> files) {
    if (files.isEmpty) return _api.post(path, fields);
    return _api.postForm(path, fields: fields, files: files);
  }

  static List<UploadFile> docs(List<UploadFile> f) => f.map((x) => x.withField('documents')).toList();

  // ---- clients
  static Future<ApiResult<dynamic>> clientList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.clientList, cleanMap(f));
  static Future<ApiResult<dynamic>> clientDetail(int id) => _api.post(ApiUrls.clientDetail, {'client_id': id});
  static Future<ApiResult<dynamic>> clientCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.clientCreate, cleanMap(f), docs(files));
  static Future<ApiResult<dynamic>> clientUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.clientUpdate, {'client_id': id, ...f}, docs(files));
  static Future<ApiResult<dynamic>> clientDeactivate(int id) => _api.post(ApiUrls.clientDeactivate, {'client_id': id});

  // ---- vendors
  static Future<ApiResult<dynamic>> vendorList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.vendorList, cleanMap(f));
  static Future<ApiResult<dynamic>> vendorDetail(int id) => _api.post(ApiUrls.vendorDetail, {'vendor_id': id});
  static Future<ApiResult<dynamic>> vendorCreate(Map<String, dynamic> f) => _api.post(ApiUrls.vendorCreate, cleanMap(f));
  static Future<ApiResult<dynamic>> vendorUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.vendorUpdate, {'vendor_id': id, ...f});
  static Future<ApiResult<dynamic>> vendorDeactivate(int id) => _api.post(ApiUrls.vendorDeactivate, {'vendor_id': id});

  // ---- projects
  static Future<ApiResult<dynamic>> projectList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.projectList, cleanMap(f));
  static Future<ApiResult<dynamic>> projectDetail(int id) => _api.post(ApiUrls.projectDetail, {'project_id': id});
  static Future<ApiResult<dynamic>> projectCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.projectCreate, cleanMap(f), docs(files));
  static Future<ApiResult<dynamic>> projectUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.projectUpdate, {'project_id': id, ...f}, docs(files));
  static Future<ApiResult<dynamic>> projectDeactivate(int id) => _api.post(ApiUrls.projectDeactivate, {'project_id': id});

  // ---- team allocation
  static Future<ApiResult<dynamic>> teamList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.teamList, cleanMap(f));
  static Future<ApiResult<dynamic>> projectTeam(int projectId) => _api.post(ApiUrls.projectTeam, {'project_id': projectId});
  static Future<ApiResult<dynamic>> employeeProjects(int employeeId) => _api.post(ApiUrls.employeeProjects, {'employee_id': employeeId});
  static Future<ApiResult<dynamic>> teamCreate(Map<String, dynamic> f) => _api.post(ApiUrls.teamCreate, cleanMap(f));
  static Future<ApiResult<dynamic>> teamUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.teamUpdate, {'allocation_id': id, ...f});
  static Future<ApiResult<dynamic>> teamDeactivate(int id) => _api.post(ApiUrls.teamDeactivate, {'allocation_id': id});
  static Future<ApiResult<dynamic>> assignHead(int allocationId) => _api.post(ApiUrls.assignHead, {'allocation_id': allocationId});

  // ---- what a non-admin sees
  static Future<ApiResult<dynamic>> myProjects({bool headOnly = false}) => _api.post(headOnly ? ApiUrls.myProjectsHead : ApiUrls.myProjects, {});
  static Future<ApiResult<dynamic>> myProjectDetail(int projectId) => _api.post(ApiUrls.myProjectDetail, {'project_id': projectId});
  static Future<ApiResult<dynamic>> myTasks([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.myTasks, cleanMap(f));

  // ---- tasks
  static Future<ApiResult<dynamic>> taskList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.taskList, cleanMap(f));
  static Future<ApiResult<dynamic>> taskDetail(int id) => _api.post(ApiUrls.taskDetail, {'task_id': id});
  static Future<ApiResult<dynamic>> taskCreate(Map<String, dynamic> f) => _api.post(ApiUrls.taskCreate, cleanMap(f));
  static Future<ApiResult<dynamic>> taskUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.taskUpdate, {'task_id': id, ...f});
  static Future<ApiResult<dynamic>> taskStatus(int id, String status, {String? actualHours}) =>
      _api.post(ApiUrls.taskStatus, cleanMap({'task_id': id, 'status': status, 'actual_hours': actualHours}));
  static Future<ApiResult<dynamic>> taskDeactivate(int id) => _api.post(ApiUrls.taskDeactivate, {'task_id': id});

  // ---- company expenses
  static Future<ApiResult<dynamic>> expenseList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.expenseList, cleanMap(f));
  static Future<ApiResult<dynamic>> expenseDetail(int id) => _api.post(ApiUrls.expenseDetail, {'expense_id': id});
  static Future<ApiResult<dynamic>> expenseCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.expenseCreate, f, docs(files));
  static Future<ApiResult<dynamic>> expenseUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.expenseUpdate, {'expense_id': id, ...f}, docs(files));
  static Future<ApiResult<dynamic>> expenseDeactivate(int id) => _api.post(ApiUrls.expenseDeactivate, {'expense_id': id});

  // ---- recurring expenses + monthly entries
  static Future<ApiResult<dynamic>> recurringList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.recurringList, cleanMap(f));
  static Future<ApiResult<dynamic>> recurringDetail(int id) => _api.post(ApiUrls.recurringDetail, {'recurring_expense_id': id});
  static Future<ApiResult<dynamic>> recurringCreate(Map<String, dynamic> f) => _api.post(ApiUrls.recurringCreate, f);
  static Future<ApiResult<dynamic>> recurringUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.recurringUpdate, {'recurring_expense_id': id, ...f});
  static Future<ApiResult<dynamic>> recurringDeactivate(int id) => _api.post(ApiUrls.recurringDeactivate, {'recurring_expense_id': id});
  static Future<ApiResult<dynamic>> entryCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.entryCreate, f, docs(files));
  static Future<ApiResult<dynamic>> entryUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.entryUpdate, {'entry_id': id, ...f}, docs(files));
  static Future<ApiResult<dynamic>> entryDelete(int id) => _api.post(ApiUrls.entryDeactivate, {'entry_id': id});

  // ---- reimbursements
  static Future<ApiResult<dynamic>> reimbList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.reimbList, cleanMap(f));
  static Future<ApiResult<dynamic>> reimbDetail(int id) => _api.post(ApiUrls.reimbDetail, {'reimbursement_id': id});
  static Future<ApiResult<dynamic>> reimbReview(int id, bool approve, String note) => _api.post(
      ApiUrls.reimbReview,
      approve
          ? cleanMap({'reimbursement_id': id, 'approve': true, 'review_notes': note})
          : {'reimbursement_id': id, 'approve': false, 'rejection_reason': note});
  static Future<ApiResult<dynamic>> reimbPay(int id, Map<String, dynamic> f) => _api.post(ApiUrls.reimbPay, cleanMap({'reimbursement_id': id, ...f}));

  // ---- project payments
  static Future<ApiResult<dynamic>> ppList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.ppList, cleanMap(f));
  static Future<ApiResult<dynamic>> ppByProject(int projectId) => _api.post(ApiUrls.ppByProject, {'project_id': projectId});
  static Future<ApiResult<dynamic>> ppCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.ppCreate, f, docs(files));
  static Future<ApiResult<dynamic>> ppUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) => _save(ApiUrls.ppUpdate, {'payment_id': id, ...f}, docs(files));
  static Future<ApiResult<dynamic>> ppCancel(int id) => _api.post(ApiUrls.ppCancel, {'payment_id': id});
  static Future<ApiResult<dynamic>> txCreate(Map<String, dynamic> f) => _api.post(ApiUrls.txCreate, cleanMap(f));
  /// status: REFUNDED | CANCELLED
  static Future<ApiResult<dynamic>> txUpdate(int id, String status, {String? notes}) =>
      _api.post(ApiUrls.txUpdate, cleanMap({'transaction_id': id, 'status': status, 'notes': notes}));
  static Future<ApiResult<dynamic>> ppReminder(List<int> projectIds, bool includeHistory) =>
      _api.post(ApiUrls.ppReminder, {'project_ids': projectIds, 'include_transaction_history': includeHistory});
  static Future<ApiResult<BlobFile>> ppInvoice(int projectId) =>
      _api.postBlob(ApiUrls.ppInvoice, {'project_id': projectId}, 'invoice.pdf');
}
