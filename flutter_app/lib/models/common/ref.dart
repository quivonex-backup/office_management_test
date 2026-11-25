/// {id, name} reference used all over the API.
class Ref {
  final int? id;
  final String name;
  const Ref({this.id, required this.name});

  static Ref? fromJson(dynamic j) {
    if (j is! Map) return null;
    return Ref(id: (j['id'] as num?)?.toInt(), name: (j['name'] ?? j['full_name'] ?? '').toString());
  }

  Map<String, dynamic> toJson() => {'id': id, 'name': name};
}

int? asInt(dynamic v) => v is num ? v.toInt() : int.tryParse(v?.toString() ?? '');
String? asStr(dynamic v) => v?.toString();
bool asBool(dynamic v, [bool def = false]) => v is bool ? v : def;
