import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

class ReportsService {
  ReportsService._();
  static final ApiService _api = ApiService.instance;

  /// The whole dashboard in ONE call; the server decides which widgets this user may see.
  static Future<ApiResult<dynamic>> dashboard({String? month}) =>
      _api.post(ApiUrls.dashboard, month == null ? {} : {'month': month});
  static Future<ApiResult<dynamic>> reportList() => _api.post(ApiUrls.reportList, {});
  static Future<ApiResult<dynamic>> run(String key, Map<String, dynamic> body) => _api.post('${ApiUrls.reportBase}$key/', body);
  static Future<ApiResult<BlobFile>> excel(String key, Map<String, dynamic> body) =>
      _api.postBlob('${ApiUrls.reportBase}$key/', {...body, 'format': 'xlsx'}, '${key}_report.xlsx');
}
