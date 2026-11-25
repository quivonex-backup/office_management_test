import 'dart:typed_data';

/// Request models. Keys match the backend payload exactly (taken from the React services).
/// Every request exposes toJson(); empty optional values are dropped by [cleanMap].

/// A file to send as multipart: [field] is the form key, [path] the local file.
class UploadFile {
  final String field;
  final String name;

  /// Android / desktop: a file path. Web has no path, so [bytes] carries the content there.
  final String? path;
  final Uint8List? bytes;
  const UploadFile({required this.field, required this.name, this.path, this.bytes});

  /// Same file under another form field name.
  UploadFile withField(String f) => UploadFile(field: f, name: name, path: path, bytes: bytes);
}

/// Drops null / empty-string / empty-list values (the React `clean()` helper).
Map<String, dynamic> cleanMap(Map<String, dynamic> m) {
  final out = <String, dynamic>{};
  m.forEach((k, v) {
    if (v == null) return;
    if (v is String && v.trim().isEmpty) return;
    if (v is List && v.isEmpty) return;
    out[k] = v;
  });
  return out;
}

abstract class ApiRequest {
  const ApiRequest();
  Map<String, dynamic> toJson();
}

class LoginRequest extends ApiRequest {
  /// username OR email, in the same field named `username`
  final String username;
  final String password;
  const LoginRequest({required this.username, required this.password});
  @override
  Map<String, dynamic> toJson() => {'username': username, 'password': password};
}

class RefreshTokenRequest extends ApiRequest {
  final String refresh;
  const RefreshTokenRequest(this.refresh);
  @override
  Map<String, dynamic> toJson() => {'refresh': refresh};
}

/// purpose: EMAIL_VERIFICATION | FORGOT_PASSWORD | LOGIN | CHANGE_EMAIL
class SendOtpRequest extends ApiRequest {
  final String email;
  final String purpose;
  const SendOtpRequest({required this.email, required this.purpose});
  @override
  Map<String, dynamic> toJson() => {'email': email, 'purpose': purpose};
}

class VerifyOtpRequest extends ApiRequest {
  final String email;
  final String otp;
  final String purpose;
  const VerifyOtpRequest({required this.email, required this.otp, required this.purpose});
  @override
  Map<String, dynamic> toJson() => {'email': email, 'otp': otp, 'purpose': purpose};
}

class ForgotPasswordRequest extends ApiRequest {
  final String email;
  final String newPassword;
  final String confirmPassword;
  const ForgotPasswordRequest({required this.email, required this.newPassword, required this.confirmPassword});
  @override
  Map<String, dynamic> toJson() => {'email': email, 'new_password': newPassword, 'confirm_password': confirmPassword};
}

class ChangePasswordRequest extends ApiRequest {
  final String oldPassword;
  final String newPassword;
  final String confirmPassword;
  const ChangePasswordRequest({required this.oldPassword, required this.newPassword, required this.confirmPassword});
  @override
  Map<String, dynamic> toJson() =>
      {'old_password': oldPassword, 'new_password': newPassword, 'confirm_password': confirmPassword};
}

class UpdateProfileRequest extends ApiRequest {
  final String? firstName, lastName, email, mobile;
  const UpdateProfileRequest({this.firstName, this.lastName, this.email, this.mobile});
  @override
  Map<String, dynamic> toJson() => cleanMap({
        'first_name': firstName,
        'last_name': lastName,
        'email': email,
        'mobile': mobile,
      });
}

class AccessRoleRequest extends ApiRequest {
  final int? accessRoleId; // null on create
  final String name;
  final String description;
  final List<String> permissionCodes; // FULL replacement on update
  const AccessRoleRequest({this.accessRoleId, required this.name, required this.description, required this.permissionCodes});
  @override
  Map<String, dynamic> toJson() => {
        if (accessRoleId != null) 'access_role_id': accessRoleId,
        'name': name,
        'description': description,
        'permission_codes': permissionCodes,
      };
}

class LeaveReviewRequest extends ApiRequest {
  final int applicationId;
  final String decision; // APPROVED | REJECTED
  final String reviewRemarks;
  const LeaveReviewRequest({required this.applicationId, required this.decision, required this.reviewRemarks});
  @override
  Map<String, dynamic> toJson() =>
      {'application_id': applicationId, 'decision': decision, 'review_remarks': reviewRemarks};
}

class CorrectionReviewRequest extends ApiRequest {
  final int correctionId;
  final bool approve;
  final String reviewNote;
  const CorrectionReviewRequest({required this.correctionId, required this.approve, required this.reviewNote});
  @override
  Map<String, dynamic> toJson() =>
      {'correction_id': correctionId, 'approve': approve, 'review_note': reviewNote};
}

class MissedDayRequest extends ApiRequest {
  final String workDate, checkIn, checkOut, reason;
  final int? employeeId;
  const MissedDayRequest({required this.workDate, required this.checkIn, required this.checkOut, required this.reason, this.employeeId});
  @override
  Map<String, dynamic> toJson() => cleanMap({
        'work_date': workDate,
        'check_in': checkIn,
        'check_out': checkOut,
        'reason': reason,
        'employee_id': employeeId,
      });
}

class TicketStatusRequest extends ApiRequest {
  final int ticketId;
  final String status;
  final String? note;
  const TicketStatusRequest({required this.ticketId, required this.status, this.note});
  @override
  Map<String, dynamic> toJson() => cleanMap({'ticket_id': ticketId, 'status': status, 'note': note});
}

class TicketCommentRequest extends ApiRequest {
  final int ticketId;
  final String message;
  final bool isInternal;
  const TicketCommentRequest({required this.ticketId, required this.message, this.isInternal = false});
  @override
  Map<String, dynamic> toJson() =>
      {'ticket_id': ticketId, 'message': message, if (isInternal) 'is_internal': true};
}

class RaiseTicketRequest extends ApiRequest {
  final String subject, description, priority;
  final int categoryId;
  const RaiseTicketRequest({required this.subject, required this.description, required this.priority, required this.categoryId});
  @override
  Map<String, dynamic> toJson() => {
        'subject': subject,
        'description': description,
        'priority': priority,
        'category_id': categoryId,
      };
}

class ReportRunRequest extends ApiRequest {
  final Map<String, dynamic> filters;
  final int page;
  final int pageSize;
  const ReportRunRequest({this.filters = const {}, this.page = 1, this.pageSize = 25});
  @override
  Map<String, dynamic> toJson() => {...filters, 'page': page, 'page_size': pageSize};
}
