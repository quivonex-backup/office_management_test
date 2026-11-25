import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';
import '../../utils/helpers.dart';

class LocationService {
  LocationService._();
  static final ApiService _api = ApiService.instance;
  static ApiResult<dynamic>? _states;
  static void clearCache() => _states = null;

  /// ~36 rows: fetched once per session.
  static Future<ApiResult<dynamic>> states() async {
    if (_states != null && _states!.ok) return _states!;
    final r = await _api.post(ApiUrls.stateList, {});
    if (r.ok) _states = r;
    return r;
  }

  static Future<ApiResult<dynamic>> districts(int stateId) => _api.post(ApiUrls.districtList, {'state_id': stateId});
  static Future<ApiResult<dynamic>> talukas(int districtId) => _api.post(ApiUrls.talukaList, {'district_id': districtId});

  static Future<List<Map<String, dynamic>>> stateItems() async => asMapList((await states()).data);
}
