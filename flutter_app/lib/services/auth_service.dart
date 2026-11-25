import '../api/api_request.dart';
import '../api/api_response.dart';
import '../api/api_service.dart';
import '../api/api_url.dart';
import '../models/response/organization_response.dart';
import '../models/response/profile_response.dart';
import '../utils/helpers.dart';

/// accounts app: login, OTP, password, profile, organizations. One method per endpoint.
class AuthService {
  AuthService._();
  static final ApiService _api = ApiService.instance;

  /// data: {access, refresh}
  static Future<ApiResult<dynamic>> login(String username, String password) =>
      _api.postRequest(ApiUrls.login, LoginRequest(username: username, password: password));

  static Future<ApiResult<dynamic>> sendOtp(String email, String purpose) =>
      _api.postRequest(ApiUrls.sendOtp, SendOtpRequest(email: email, purpose: purpose));

  static Future<ApiResult<dynamic>> verifyOtp(String email, String otp, String purpose) =>
      _api.postRequest(ApiUrls.verifyOtp, VerifyOtpRequest(email: email, otp: otp, purpose: purpose));

  static Future<ApiResult<dynamic>> forgotPassword(String email, String newPassword, String confirm) => _api.postRequest(
      ApiUrls.forgotPassword, ForgotPasswordRequest(email: email, newPassword: newPassword, confirmPassword: confirm));

  static Future<ApiResult<dynamic>> changePassword(String oldPassword, String newPassword, String confirm) => _api.postRequest(
      ApiUrls.changePassword, ChangePasswordRequest(oldPassword: oldPassword, newPassword: newPassword, confirmPassword: confirm));

  static Future<ApiResult<Profile>> myProfile() async {
    final r = await _api.post(ApiUrls.myProfile, {});
    return r.map<Profile>((d) => d is Map ? Profile.fromJson(Map<String, dynamic>.from(d)) : null);
  }

  /// Name + photo editable. email / mobile only when given.
  static Future<ApiResult<dynamic>> updateMyProfile(UpdateProfileRequest req, {UploadFile? photo}) =>
      _api.postForm(ApiUrls.myProfileUpdate, fields: req.toJson(), files: [if (photo != null) photo]);

  static Future<ApiResult<List<Organization>>> myOrganizations() async {
    final r = await _api.post(ApiUrls.myOrganizations, {});
    return r.map<List<Organization>>((d) => asMapList(d).map(Organization.fromJson).toList());
  }

  /// Owner only. Send only changed fields. state / district are TEXT names.
  static Future<ApiResult<dynamic>> organizationUpdate(int id, Map<String, dynamic> fields, {UploadFile? logo}) =>
      _api.postForm(ApiUrls.organizationUpdate, fields: {'id': id, ...fields}, files: [if (logo != null) logo]);
}
