import '../common/ref.dart';

class Organization {
  final int id;
  final String organizationName;
  final String? logo;
  final Map<String, dynamic> raw;
  const Organization({required this.id, required this.organizationName, this.logo, required this.raw});

  factory Organization.fromJson(Map<String, dynamic> j) => Organization(
        id: asInt(j['id']) ?? 0,
        organizationName: (j['organization_name'] ?? '').toString(),
        logo: asStr(j['logo']),
        raw: j,
      );

  String? field(String k) => asStr(raw[k]);
}
