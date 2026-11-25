import '../common/ref.dart';

/// accounts/my-profile/ : user fields + access fields in one object.
class EmployeeSummary {
  final int id;
  final String employeeCode;
  final String fullName;
  final Ref? branch, department, designation;
  const EmployeeSummary({required this.id, required this.employeeCode, required this.fullName, this.branch, this.department, this.designation});

  factory EmployeeSummary.fromJson(Map<String, dynamic> j) => EmployeeSummary(
        id: asInt(j['id']) ?? 0,
        employeeCode: (j['employee_code'] ?? '').toString(),
        fullName: (j['full_name'] ?? '').toString(),
        branch: Ref.fromJson(j['branch']),
        department: Ref.fromJson(j['department']),
        designation: Ref.fromJson(j['designation']),
      );
}

class Profile {
  final int id;
  final String username, firstName, lastName;
  final String? email, mobile, profilePhoto, accountRole;
  final bool isOrgOwner;
  final int? organizationId;
  final String? organizationName;
  final EmployeeSummary? employee;
  final Ref? accessRole;
  final List<String> permissions;

  const Profile({
    required this.id,
    required this.username,
    required this.firstName,
    required this.lastName,
    this.email,
    this.mobile,
    this.profilePhoto,
    this.accountRole,
    required this.isOrgOwner,
    this.organizationId,
    this.organizationName,
    this.employee,
    this.accessRole,
    required this.permissions,
  });

  String get fullName => '$firstName $lastName'.trim().isEmpty ? username : '$firstName $lastName'.trim();

  factory Profile.fromJson(Map<String, dynamic> j) {
    final org = j['organization'];
    return Profile(
      id: asInt(j['id']) ?? 0,
      username: (j['username'] ?? '').toString(),
      firstName: (j['first_name'] ?? '').toString(),
      lastName: (j['last_name'] ?? '').toString(),
      email: asStr(j['email']),
      mobile: asStr(j['mobile']),
      profilePhoto: asStr(j['profile_photo']),
      accountRole: asStr(j['account_role']),
      isOrgOwner: j['is_org_owner'] == true,
      organizationId: org is Map ? asInt(org['id']) : null,
      organizationName: org is Map ? asStr(org['name']) : null,
      employee: j['employee'] is Map ? EmployeeSummary.fromJson(Map<String, dynamic>.from(j['employee'] as Map)) : null,
      accessRole: Ref.fromJson(j['access_role']),
      permissions: (j['permissions'] as List? ?? const []).map((e) => e.toString()).toList(),
    );
  }

  bool get hasOrganization => organizationId != null;
}
