import 'package:flutter/material.dart';

import '../../constants/app_dimensions.dart';
import '../../utils/responsive_helper.dart';
import 'package:flutter/services.dart';

import '../../api/api_request.dart';
import '../../utils/validators.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_dropdown.dart';
import '../../widgets/forms/app_text_field.dart';
import '../../widgets/forms/date_field.dart';
import '../../widgets/forms/file_picker_field.dart';
import '../../widgets/forms/opt.dart';
import 'crud_models.dart';

/// Full-screen form (Scaffold + [CrudFormBody]). Pops with `true` when saved.
class CrudFormScreen extends StatelessWidget {
  final String title;
  final List<FieldSpec> fields;
  final Item? item; // null = create
  final Future<dynamic> Function(Map<String, dynamic> body, List<UploadFile> files) onSubmit;
  final String? submitLabel;
  const CrudFormScreen({super.key, required this.title, required this.fields, required this.onSubmit, this.item, this.submitLabel});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(title)),
        body: SafeArea(
          child: MaxWidth(
            width: AppDimensions.maxFormWidth,
            child: CrudFormBody(
              fields: fields,
              item: item,
              onSubmit: onSubmit,
              submitLabel: submitLabel,
              onSaved: () => Navigator.pop(context, true),
            ),
          ),
        ),
      );
}

/// Builds a create/edit form from a list of [FieldSpec]s (no Scaffold, so it can be embedded).
/// [onSubmit] receives the payload body and the picked files and returns an ApiResult.
class CrudFormBody extends StatefulWidget {
  final List<FieldSpec> fields;
  final Item? item; // null = create
  final Future<dynamic> Function(Map<String, dynamic> body, List<UploadFile> files) onSubmit;
  final String? submitLabel;
  final VoidCallback? onSaved;
  const CrudFormBody({super.key, required this.fields, required this.onSubmit, this.item, this.submitLabel, this.onSaved});

  @override
  State<CrudFormBody> createState() => _CrudFormBodyState();
}

class _CrudFormBodyState extends State<CrudFormBody> {
  final _form = GlobalKey<FormState>();
  final Map<String, TextEditingController> _text = {};
  final Map<String, dynamic> _values = {}; // dropdown / boolean
  final Map<String, UploadFile?> _files = {};
  final Map<String, List<Opt>> _opts = {};
  Map<String, String> _serverErrors = {};
  bool _busy = false;

  bool get _editing => widget.item != null;
  List<FieldSpec> get _visible => widget.fields.where((f) => _editing ? !f.createOnly : !f.editOnly).toList();

  dynamic _initialOf(FieldSpec f) {
    if (_editing) {
      final v = f.readValue != null ? f.readValue!(widget.item!) : widget.item![f.key];
      return v;
    }
    return f.initial;
  }

  @override
  void initState() {
    super.initState();
    for (final f in _visible) {
      final v = _initialOf(f);
      switch (f.type) {
        case FieldType.dropdown:
          _values[f.key] = v;
          if (f.options != null) _opts[f.key] = f.options!;
          if (f.loadOptions != null) {
            f.loadOptions!().then((o) {
              if (mounted) setState(() => _opts[f.key] = o);
            });
          }
          break;
        case FieldType.boolean:
          _values[f.key] = v is bool ? v : false;
          break;
        case FieldType.file:
        case FieldType.image:
          _files[f.key] = null;
          break;
        default:
          _text[f.key] = TextEditingController(text: v == null ? '' : v.toString());
      }
    }
  }

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
    }
    super.dispose();
  }

  String? _validator(FieldSpec f, String? v) {
    final s = (v ?? '').trim();
    if (f.required && s.isEmpty) return '${f.label} is required.';
    if (s.isEmpty) return null;
    if (f.validator != null) return f.validator!(v);
    switch (f.type) {
      case FieldType.email:
        return Validators.email(v, label: f.label);
      case FieldType.phone:
        return Validators.phone(v, label: f.label);
      case FieldType.integer:
        return Validators.integer(v, label: f.label);
      case FieldType.decimal:
        return Validators.decimal(v, label: f.label);
      case FieldType.password:
        return Validators.password(v, f.label);
      default:
        return null;
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final body = <String, dynamic>{};
    final files = <UploadFile>[];
    for (final f in _visible) {
      switch (f.type) {
        case FieldType.dropdown:
          final v = _values[f.key];
          if (v != null) {
            body[f.key] = v;
          } else if (_editing && f.clearable) {
            body[f.key] = null;
          }
          break;
        case FieldType.boolean:
          body[f.key] = _values[f.key] == true;
          break;
        case FieldType.file:
        case FieldType.image:
          final u = _files[f.key];
          if (u != null) files.add(u);
          break;
        default:
          final s = _text[f.key]!.text.trim();
          if (s.isEmpty) {
            final had = _editing && (_initialOf(f)?.toString().isNotEmpty ?? false);
            if (had) body[f.key] = f.clearable ? null : '';
            break;
          }
          if (f.type == FieldType.integer) {
            body[f.key] = int.parse(s);
          } else {
            body[f.key] = s; // decimals as text, as the backend sends them
          }
      }
    }
    setState(() {
      _busy = true;
      _serverErrors = {};
    });
    final r = await widget.onSubmit(body, files);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r.ok) {
      Toast.result(context, r, success: _editing ? 'Saved.' : 'Created.');
      widget.onSaved?.call();
    } else {
      setState(() => _serverErrors = r.fieldErrors);
      Toast.result(context, r);
    }
  }

  Widget _field(FieldSpec f) {
    final err = _serverErrors[f.key];
    switch (f.type) {
      case FieldType.dropdown:
        return AppDropdown(
          label: f.label + (f.required ? ' *' : ''),
          value: _values[f.key],
          items: _opts[f.key] ?? const [],
          errorText: err,
          allowClear: !f.required,
          validator: f.required ? (v) => v == null ? '${f.label} is required.' : null : null,
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case FieldType.boolean:
        return SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(f.label),
          value: _values[f.key] == true,
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case FieldType.date:
        return DateField(label: f.label + (f.required ? ' *' : ''), controller: _text[f.key]!, errorText: err, validator: (v) => _validator(f, v));
      case FieldType.time:
        return TimeField(label: f.label + (f.required ? ' *' : ''), controller: _text[f.key]!, errorText: err, validator: (v) => _validator(f, v));
      case FieldType.file:
      case FieldType.image:
        return FilePickerField(
          label: f.label,
          field: f.key,
          value: _files[f.key],
          imagesOnly: f.type == FieldType.image,
          onChanged: (u) => setState(() => _files[f.key] = u),
        );
      default:
        return AppTextField(
          label: f.label + (f.required ? ' *' : ''),
          controller: _text[f.key]!,
          hint: f.hint,
          errorText: err,
          obscure: f.type == FieldType.password,
          maxLines: f.type == FieldType.multiline ? 4 : 1,
          keyboardType: switch (f.type) {
            FieldType.integer => TextInputType.number,
            FieldType.decimal => const TextInputType.numberWithOptions(decimal: true),
            FieldType.email => TextInputType.emailAddress,
            FieldType.phone => TextInputType.phone,
            FieldType.multiline => TextInputType.multiline,
            _ => TextInputType.text,
          },
          formatters: f.type == FieldType.integer ? [FilteringTextInputFormatter.digitsOnly] : null,
          validator: (v) => _validator(f, v),
        );
    }
  }

  @override
  Widget build(BuildContext context) => Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          children: [
            for (final f in _visible) Padding(padding: const EdgeInsets.only(bottom: 14), child: _field(f)),
            const SizedBox(height: 6),
            PrimaryButton(label: widget.submitLabel ?? (_editing ? 'Save changes' : 'Create'), busy: _busy, onPressed: _save),
          ],
        ),
      );
}
