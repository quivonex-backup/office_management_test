import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

class AssetsService {
  AssetsService._();
  static final ApiService _api = ApiService.instance;

  static Future<ApiResult<dynamic>> categoryList({bool includeInactive = false}) =>
      _api.post(ApiUrls.asCatList, includeInactive ? {'include_inactive': true} : {});
  static Future<ApiResult<dynamic>> categoryCreate(String name, {String? description}) =>
      _api.post(ApiUrls.asCatCreate, cleanMap({'name': name, 'description': description}));
  static Future<ApiResult<dynamic>> categoryUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.asCatUpdate, {'category_id': id, ...f});
  static Future<ApiResult<dynamic>> categoryDeactivate(int id) => _api.post(ApiUrls.asCatDeactivate, {'category_id': id});

  /// data = list; raw['summary'] = {total, by_status}
  static Future<ApiResult<dynamic>> assetList([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.asList, cleanMap(f));
  static Future<ApiResult<dynamic>> assetDetail(int id) => _api.post(ApiUrls.asDetail, {'asset_id': id});
  static Future<ApiResult<dynamic>> assetCreate(Map<String, dynamic> f) => _api.post(ApiUrls.asCreate, cleanMap(f));
  static Future<ApiResult<dynamic>> assetUpdate(int id, Map<String, dynamic> f) => _api.post(ApiUrls.asUpdate, {'asset_id': id, ...f});
  static Future<ApiResult<dynamic>> assetAssign(Map<String, dynamic> f) => _api.post(ApiUrls.asAssign, cleanMap(f));
  static Future<ApiResult<dynamic>> assetReturn(Map<String, dynamic> f) => _api.post(ApiUrls.asReturn, cleanMap(f));
  static Future<ApiResult<dynamic>> assetDeactivate(int id) => _api.post(ApiUrls.asDeactivate, {'asset_id': id});
  static Future<ApiResult<dynamic>> myAssets() => _api.post(ApiUrls.asMy, {});
  static Future<ApiResult<BlobFile>> assetExcel([Map<String, dynamic> f = const {}]) =>
      _api.postBlob(ApiUrls.asList, {...cleanMap(f), 'format': 'xlsx'}, 'asset_register.xlsx');
}
