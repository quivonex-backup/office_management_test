import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

/// notifications, announcements, project chat.
class CommunicationsService {
  CommunicationsService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> notifList({bool? unreadOnly, int? limit, int? beforeId}) =>
      _api.post(ApiUrls.notifList, cleanMap({'unread_only': unreadOnly, 'limit': limit, 'before_id': beforeId}));
  static Future<ApiResult<dynamic>> notifRead(List<int> ids) => _api.post(ApiUrls.notifRead, {'notification_ids': ids});
  static Future<ApiResult<dynamic>> notifReadAll() => _api.post(ApiUrls.notifReadAll, {});
  static Future<ApiResult<dynamic>> notifCount() => _api.post(ApiUrls.notifCount, {});
  static Future<ApiResult<dynamic>> notifDelete(List<int> ids) => _api.post(ApiUrls.notifDelete, {'notification_ids': ids});

  static Future<ApiResult<dynamic>> annList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.annList, cleanMap(f));
  static Future<ApiResult<dynamic>> annMy({String? priority}) => _api.post(ApiUrls.annMy, cleanMap({'priority': priority}));
  static List<UploadFile> _att(List<UploadFile> f) => f.map((x) => x.withField('attachments')).toList();
  static Future<ApiResult<dynamic>> annCreate(Map<String, dynamic> f, {List<UploadFile> files = const []}) =>
      _api.postForm(ApiUrls.annCreate, fields: f, files: _att(files));
  static Future<ApiResult<dynamic>> annUpdate(int id, Map<String, dynamic> f, {List<UploadFile> files = const []}) =>
      _api.postForm(ApiUrls.annUpdate, fields: {'announcement_id': id, ...f}, files: _att(files));
  static Future<ApiResult<dynamic>> annDeactivate(int id) => _api.post(ApiUrls.annDeactivate, {'announcement_id': id});

  static Future<ApiResult<dynamic>> chatMessages(int projectId, {int? sinceId, int? beforeId, int? limit}) =>
      _api.post(ApiUrls.chatMessages, cleanMap({'project_id': projectId, 'since_id': sinceId, 'before_id': beforeId, 'limit': limit}));
  static Future<ApiResult<dynamic>> chatSend(int projectId, String body, {List<UploadFile> files = const []}) =>
      _api.postForm(ApiUrls.chatSend, fields: {'project_id': projectId, 'body': body}, files: _att(files));
  static Future<ApiResult<dynamic>> chatDelete(int messageId) => _api.post(ApiUrls.chatDelete, {'message_id': messageId});
  static Future<ApiResult<dynamic>> chatSettingsGet(int projectId) => _api.post(ApiUrls.chatSettings, {'project_id': projectId});
  /// posting_permission: ADMIN_ONLY | ADMIN_AND_HEAD | ALL_MEMBERS
  static Future<ApiResult<dynamic>> chatSettingsSave(int projectId, String permission) =>
      _api.post(ApiUrls.chatSettings, {'project_id': projectId, 'posting_permission': permission});
}
