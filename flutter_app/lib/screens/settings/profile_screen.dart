import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_request.dart';
import '../../api/api_url.dart';
import '../../providers/auth_provider.dart';
import '../../services/auth_service.dart';
import '../../services/other_services/employees_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/cards/info_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/forms/app_text_field.dart';
import '../../widgets/forms/file_picker_field.dart';
import '../../widgets/navigation/app_scaffold.dart';

/// Port of pages/settings/MyProfile.tsx. Name + photo are editable; email / mobile only for
/// accounts without an employee record. An employee login also shows its read-only employee record.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _form = GlobalKey<FormState>();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _email = TextEditingController();
  final _mobile = TextEditingController();
  UploadFile? _photo;
  bool _busy = false;
  Map<String, String> _errs = {};

  @override
  void initState() {
    super.initState();
    final p = context.read<AuthProvider>().profile;
    if (p != null) {
      _first.text = p.firstName;
      _last.text = p.lastName;
      _email.text = p.email ?? '';
      _mobile.text = p.mobile ?? '';
    }
  }

  @override
  void dispose() {
    _first.dispose();
    _last.dispose();
    _email.dispose();
    _mobile.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final auth = context.read<AuthProvider>();
    final hasEmp = auth.hasEmployee;
    if (!_form.currentState!.validate()) {
      Toast.show(context, 'Please fix the highlighted fields.', error: true);
      return;
    }
    setState(() {
      _busy = true;
      _errs = {};
    });
    final r = await AuthService.updateMyProfile(
      UpdateProfileRequest(
        firstName: _first.text.trim(),
        lastName: _last.text.trim(),
        email: hasEmp ? null : _email.text.trim(),
        mobile: hasEmp ? null : _mobile.text.trim(),
      ),
      photo: _photo,
    );
    if (!mounted) return;
    setState(() => _busy = false);
    Toast.result(context, r);
    if (!r.ok) {
      setState(() => _errs = r.fieldErrors);
      return;
    }
    setState(() => _photo = null);
    await auth.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final p = auth.profile;
    final hasEmp = auth.hasEmployee;
    final roleLabel = p == null ? '' : (p.isOrgOwner ? 'Organization owner' : (p.accessRole?.name ?? p.accountRole ?? ''));
    return AppScaffold(
      title: 'My profile',
      body: ListView(padding: const EdgeInsets.all(14), children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(children: [
              CircleAvatar(
                radius: 46,
                backgroundImage: (p?.profilePhoto ?? '').isNotEmpty ? NetworkImage(ApiUrls.media(p!.profilePhoto)) : null,
                child: (p?.profilePhoto ?? '').isEmpty ? Text(Fmt.initials(p?.fullName ?? ''), style: const TextStyle(fontSize: 26)) : null,
              ),
              const SizedBox(height: 10),
              Text(p?.fullName ?? '', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
              Text('@${p?.username ?? ''}'),
              if (roleLabel.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Chip(label: Text(roleLabel), avatar: const Icon(Icons.verified_user_outlined, size: 16))),
              if (!hasEmp) const Text('No employee record', style: TextStyle(fontSize: 12)),
              if ((p?.email ?? '').isNotEmpty) Text(p!.email!),
              if ((p?.mobile ?? '').isNotEmpty) Text(p!.mobile!),
              if (auth.org != null) Text(auth.org!.organizationName, style: Theme.of(context).textTheme.bodySmall),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Form(
              key: _form,
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text('Edit account details', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text('Your login account. The account photo is only a display picture and is not used for attendance.', style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 14),
                FilePickerField(label: 'Account photo', field: 'profile_photo', value: _photo, imagesOnly: true, onChanged: (f) => setState(() => _photo = f)),
                const SizedBox(height: 12),
                AppTextField(label: 'First name', controller: _first, validator: (v) => Validators.name(v, label: 'First name', required: true), errorText: _errs['first_name']),
                const SizedBox(height: 12),
                AppTextField(label: 'Last name', controller: _last, validator: (v) => Validators.name(v, label: 'Last name', required: true), errorText: _errs['last_name']),
                const SizedBox(height: 12),
                AppTextField(
                  label: 'Email',
                  controller: _email,
                  readOnly: hasEmp,
                  keyboardType: TextInputType.emailAddress,
                  hint: hasEmp ? 'Managed by your administrator.' : null,
                  validator: hasEmp ? null : (v) => Validators.email(v, required: true),
                  errorText: _errs['email'],
                ),
                const SizedBox(height: 12),
                AppTextField(
                  label: 'Mobile',
                  controller: _mobile,
                  readOnly: hasEmp,
                  keyboardType: TextInputType.phone,
                  hint: hasEmp ? 'Managed by your administrator.' : null,
                  validator: hasEmp ? null : (v) => Validators.mobile(v),
                  errorText: _errs['mobile'],
                ),
                const SizedBox(height: 12),
                AppTextField(label: 'Username', controller: TextEditingController(text: p?.username ?? ''), readOnly: true, hint: 'Username cannot be changed.'),
                const SizedBox(height: 16),
                PrimaryButton(label: 'Save changes', busy: _busy, onPressed: _save),
              ]),
            ),
          ),
        ),
        if (hasEmp) ...[
          const SizedBox(height: 18),
          Text('My employee profile', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
          Text('Read-only. Your administrator or reporting manager maintains these details.', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 8),
          _EmployeeRecord(key: ValueKey(p!.employee!.id)),
        ],
      ]),
    );
  }
}

/// employees/my-profile/ rendered as label/value cards (scalar fields grouped by section).
class _EmployeeRecord extends StatelessWidget {
  const _EmployeeRecord({super.key});

  static String _label(String k) => Fmt.label(k);

  String? _show(dynamic v) {
    if (v == null) return null;
    if (v is bool) return v ? 'Yes' : 'No';
    if (v is Map) return (v['name'] ?? v['full_name'] ?? v['title'])?.toString();
    if (v is List || v.toString().isEmpty) return null;
    return v.toString();
  }

  @override
  Widget build(BuildContext context) {
    return ApiBuilder(
      load: () => EmployeesService.myProfile(),
      builder: (ctx, r, reload) {
        final d = asMap(r.data);
        const skip = {'id', 'profile_photo', 'documents', 'organization', 'user'};
        final scalars = <MapEntry<String, String?>>[];
        final sections = <Widget>[];
        d.forEach((k, v) {
          if (skip.contains(k)) return;
          if (v is Map && (v['name'] == null && v['full_name'] == null && v['title'] == null)) {
            final rows = <MapEntry<String, String?>>[];
            v.forEach((k2, v2) {
              final s = _show(v2);
              if (s != null) rows.add(MapEntry(_label(k2.toString()), s));
            });
            if (rows.isNotEmpty) sections.add(Padding(padding: const EdgeInsets.only(top: 10), child: InfoCard(title: _label(k), rows: rows)));
          } else if (v is List) {
            final items = asMapList(v);
            if (items.isNotEmpty) {
              sections.add(Padding(
                padding: const EdgeInsets.only(top: 10),
                child: InfoCard(title: _label(k), rows: [
                  for (final it in items)
                    MapEntry(_show(it['title'] ?? it['name'] ?? it['type'] ?? it['id']) ?? '', _show(it['file'] ?? it['number'] ?? it['value'] ?? it['created_at'])),
                ]),
              ));
            }
          } else {
            final s = _show(v);
            if (s != null) scalars.add(MapEntry(_label(k), s));
          }
        });
        final docs = asMapList(d['documents']);
        return Column(children: [
          InfoCard(title: 'Employee details', rows: scalars),
          ...sections,
          if (docs.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Card(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Padding(padding: EdgeInsets.fromLTRB(14, 12, 14, 0), child: Text('My documents', style: TextStyle(fontWeight: FontWeight.w700))),
                  for (final doc in docs)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.description_outlined),
                      title: Text('${doc['title'] ?? 'Document'}'),
                      subtitle: Text(Fmt.date(doc['created_at'])),
                    ),
                ]),
              ),
            ),
        ]);
      },
    );
  }
}
