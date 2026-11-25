import '../common/ref.dart';

class Branch {
  final int id;
  final String name;
  final String? code, address, city, stateName;
  final int? stateId, allowedRadiusMeters;
  final String? latitude, longitude;
  final bool isActive;
  final int employeeCount;
  const Branch({required this.id, required this.name, this.code, this.address, this.city, this.stateName, this.stateId,
      this.allowedRadiusMeters, this.latitude, this.longitude, required this.isActive, required this.employeeCount});

  factory Branch.fromJson(Map<String, dynamic> j) => Branch(
        id: asInt(j['id']) ?? 0,
        name: (j['name'] ?? '').toString(),
        code: asStr(j['code']),
        address: asStr(j['address']),
        city: asStr(j['city']),
        stateId: asInt(j['state_id']),
        stateName: asStr(j['state_name']),
        latitude: asStr(j['latitude']),
        longitude: asStr(j['longitude']),
        allowedRadiusMeters: asInt(j['allowed_radius_meters']),
        isActive: j['is_active'] != false,
        employeeCount: asInt(j['employee_count']) ?? 0,
      );
}
