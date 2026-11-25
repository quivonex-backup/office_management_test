import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

class VisitorsService {
  VisitorsService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> create(Map<String, dynamic> f, {UploadFile? photo}) => photo == null
      ? _api.post(ApiUrls.vsCreate, cleanMap(f))
      : _api.postForm(ApiUrls.vsCreate, fields: cleanMap(f), files: [photo.withField('photo')]);
  /// Dates default to today on the server; inside_only without dates = everyone still inside.
  static Future<ApiResult<dynamic>> list([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.vsList, cleanMap(f));
  static Future<ApiResult<dynamic>> detail(int id) => _api.post(ApiUrls.vsDetail, {'visit_id': id});
  /// A new photo goes in a second multipart call so the JSON fields can carry nulls.
  static Future<ApiResult<dynamic>> update(int id, Map<String, dynamic> f, {UploadFile? photo, bool removePhoto = false}) async {
    final r = await _api.post(ApiUrls.vsUpdate, {'visit_id': id, ...f, if (removePhoto) 'remove_photo': true});
    if (!r.ok || photo == null) return r;
    return _api.postForm(ApiUrls.vsUpdate, fields: {'visit_id': id}, files: [photo.withField('photo')]);
  }
  static Future<ApiResult<dynamic>> checkOut(int id, {String? checkOutAt}) =>
      _api.post(ApiUrls.vsCheckOut, cleanMap({'visit_id': id, 'check_out_at': checkOutAt}));
  static Future<ApiResult<dynamic>> deactivate(int id) => _api.post(ApiUrls.vsDeactivate, {'visit_id': id});
  static Future<ApiResult<dynamic>> lookup(String mobile) => _api.post(ApiUrls.vsLookup, {'visitor_mobile': mobile});
  static Future<ApiResult<dynamic>> myVisitors([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.vsMy, cleanMap(f));
  static Future<ApiResult<BlobFile>> excel([Map<String, dynamic> f = const {}]) =>
      _api.postBlob(ApiUrls.vsList, {...cleanMap(f), 'format': 'xlsx'}, 'visitor_log.xlsx');
}
