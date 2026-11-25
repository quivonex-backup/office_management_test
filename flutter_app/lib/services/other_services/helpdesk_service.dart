import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

class HelpdeskService {
  HelpdeskService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> categoryOptions() => _api.post(ApiUrls.tkCatOptions, {});
  static Future<ApiResult<dynamic>> categoryList({bool includeInactive = false}) =>
      _api.post(ApiUrls.tkCatList, includeInactive ? {'include_inactive': true} : {});
  static Future<ApiResult<dynamic>> categoryCreate(Map<String, dynamic> f) => _api.post(ApiUrls.tkCatCreate, f);
  /// Send department_id / default_assignee_id = null to clear them.
  static Future<ApiResult<dynamic>> categoryUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.tkCatUpdate, {'category_id': id, ...f});
  static Future<ApiResult<dynamic>> categoryDeactivate(int id) => _api.post(ApiUrls.tkCatDeactivate, {'category_id': id});

  static Future<ApiResult<dynamic>> ticketCreate(Map<String, dynamic> f, {UploadFile? attachment}) => attachment == null
      ? _api.post(ApiUrls.tkCreate, cleanMap(f))
      : _api.postForm(ApiUrls.tkCreate, fields: cleanMap(f), files: [attachment.withField('attachment')]);
  /// view: raised | assigned
  static Future<ApiResult<dynamic>> myTickets({String view = 'raised', String? status}) =>
      _api.post(ApiUrls.tkMy, cleanMap({'view': view, 'status': status}));
  /// data = list; raw['summary'] = {total, by_status, unassigned_open}
  static Future<ApiResult<dynamic>> ticketList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.tkList, cleanMap(f));
  static Future<ApiResult<dynamic>> ticketDetail(int id) => _api.post(ApiUrls.tkDetail, {'ticket_id': id});
  static Future<ApiResult<dynamic>> ticketAssign(int id, int? assigneeId) => _api.post(ApiUrls.tkAssign, {'ticket_id': id, 'assignee_id': assigneeId});
  static Future<ApiResult<dynamic>> ticketUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.tkUpdate, {'ticket_id': id, ...f});
  static Future<ApiResult<dynamic>> ticketStatus(TicketStatusRequest r) => _api.postRequest(ApiUrls.tkStatus, r);
  static Future<ApiResult<dynamic>> ticketComment(TicketCommentRequest r, {UploadFile? attachment}) => attachment == null
      ? _api.postRequest(ApiUrls.tkComment, r)
      : _api.postForm(ApiUrls.tkComment, fields: r.toJson(), files: [attachment.withField('attachment')]);
}
