import 'dart:convert';

import '../../api/api_request.dart';
import '../../api/api_response.dart';
import '../../api/api_service.dart';
import '../../api/api_url.dart';

class RecruitmentService {
  RecruitmentService._();
  static final ApiService _api = ApiService.instance;

  /// data = list; `raw['summary']` holds {total, by_stage, by_status}.
  static Future<ApiResult<dynamic>> list([Map<String, dynamic> f = const {}]) => _api.post(ApiUrls.applicantList, cleanMap(f));
  static Future<ApiResult<dynamic>> detail(int id) => _api.post(ApiUrls.applicantDetail, {'applicant_id': id});

  /// Lists / objects go as JSON strings when the request is multipart.
  static Map<String, dynamic> _jsonify(Map<String, dynamic> o) =>
      o.map((k, v) => MapEntry(k, (v is Map || v is List) ? jsonEncode(v) : v));

  static Future<ApiResult<dynamic>> create(Map<String, dynamic> fields, {UploadFile? resume, List<UploadFile> documents = const [], List<String> documentTypes = const []}) {
    final files = [if (resume != null) resume, ...documents];
    if (files.isEmpty) return _api.post(ApiUrls.applicantCreate, cleanMap(fields));
    return _api.postForm(ApiUrls.applicantCreate,
        fields: {..._jsonify(cleanMap(fields)), if (documentTypes.isNotEmpty) 'document_types': documentTypes}, files: files);
  }

  static Future<ApiResult<dynamic>> update(int id, Map<String, dynamic> fields, {UploadFile? resume, List<UploadFile> documents = const [], List<String> documentTypes = const []}) {
    final files = [if (resume != null) resume, ...documents];
    if (files.isEmpty) return _api.post(ApiUrls.applicantUpdate, {'applicant_id': id, ...fields});
    return _api.postForm(ApiUrls.applicantUpdate,
        fields: {'applicant_id': id, ..._jsonify(fields), if (documentTypes.isNotEmpty) 'document_types': documentTypes}, files: files);
  }

  static Future<ApiResult<dynamic>> status(int id, String status, {String? note}) =>
      _api.post(ApiUrls.applicantStatus, cleanMap({'applicant_id': id, 'status': status, 'note': note}));
  static Future<ApiResult<dynamic>> verification(int id, Map<String, dynamic> body) => _api.post(ApiUrls.applicantVerification, {'applicant_id': id, ...body});
  static Future<ApiResult<dynamic>> onboarding(int id, Map<String, dynamic> body) => _api.post(ApiUrls.applicantOnboarding, {'applicant_id': id, ...body});
  static Future<ApiResult<dynamic>> convert(int id, {bool? createUser}) =>
      _api.post(ApiUrls.applicantConvert, cleanMap({'applicant_id': id, 'create_user': createUser}));
  static Future<ApiResult<BlobFile>> offerLetter(int id, {int? offerId}) =>
      _api.postBlob(ApiUrls.offerLetterDownload, cleanMap({'applicant_id': id, 'offer_id': offerId}), 'offer_letter.pdf');
}
