import '../common/ref.dart';

class PermissionItem {
  final String code, group, label;
  const PermissionItem({required this.code, required this.group, required this.label});
  factory PermissionItem.fromJson(Map<String, dynamic> j) => PermissionItem(
      code: (j['code'] ?? '').toString(), group: (j['group'] ?? 'Other').toString(), label: (j['label'] ?? j['code'] ?? '').toString());
}

class AccessRole {
  final int id;
  final String name;
  final String? description;
  final bool isActive;
  final List<String> permissionCodes;
  final int employeeCount;
  const AccessRole({required this.id, required this.name, this.description, required this.isActive, required this.permissionCodes, required this.employeeCount});

  factory AccessRole.fromJson(Map<String, dynamic> j) => AccessRole(
        id: asInt(j['id']) ?? 0,
        name: (j['name'] ?? '').toString(),
        description: asStr(j['description']),
        isActive: j['is_active'] != false,
        permissionCodes: (j['permission_codes'] as List? ?? const []).map((e) => e.toString()).toList(),
        employeeCount: asInt(j['employee_count']) ?? 0,
      );
}
