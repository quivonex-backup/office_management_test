import 'package:flutter/material.dart';

import '../../api/api_response.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/navigation/app_scaffold.dart';
import 'crud_form_screen.dart';
import 'crud_models.dart';

/// Settings endpoints work as "POST {} reads, POST body saves" and return one flat object.
/// This screen builds the form from the shape the server actually returns (bool -> switch,
/// whole number -> integer, decimal text -> decimal, HH:mm:ss -> time, else text),
/// so nothing is guessed about field names.
class AutoSettingsScreen extends StatelessWidget {
  final String title;
  final Future<ApiResult<dynamic>> Function() load;
  final Future<ApiResult<dynamic>> Function(Map<String, dynamic> body) save;
  final Set<String> hidden;
  const AutoSettingsScreen({super.key, required this.title, required this.load, required this.save, this.hidden = const {}});

  static final _skip = {'id', 'created_at', 'updated_at', 'organization', 'organization_id'};

  String _pretty(String k) {
    final t = k.replaceAll('_', ' ');
    return t[0].toUpperCase() + t.substring(1);
  }

  List<FieldSpec> _fieldsFor(Map<String, dynamic> m) {
    final out = <FieldSpec>[];
    m.forEach((k, v) {
      if (_skip.contains(k) || hidden.contains(k) || v is Map || v is List) return;
      final label = _pretty(k);
      if (v is bool) {
        out.add(FieldSpec(k, label, type: FieldType.boolean));
      } else if (v is int) {
        out.add(FieldSpec(k, label, type: FieldType.integer));
      } else if (v is double) {
        out.add(FieldSpec(k, label, type: FieldType.decimal));
      } else if (v is String && RegExp(r'^\d{1,2}:\d{2}(:\d{2})?$').hasMatch(v)) {
        out.add(FieldSpec(k, label, type: FieldType.time));
      } else if (v is String && RegExp(r'^-?\d+\.\d+$').hasMatch(v)) {
        out.add(FieldSpec(k, label, type: FieldType.decimal));
      } else if (v is String || v == null) {
        out.add(FieldSpec(k, label));
      }
    });
    return out;
  }

  @override
  Widget build(BuildContext context) => AppScaffold(
        title: title,
        body: ApiBuilder(
          load: load,
          builder: (ctx, r, reload) {
            final data = asMap(r.data);
            return CrudFormBody(
              fields: _fieldsFor(data),
              item: data,
              submitLabel: 'Save settings',
              onSubmit: (body, files) => save(body),
            );
          },
        ),
      );
}

