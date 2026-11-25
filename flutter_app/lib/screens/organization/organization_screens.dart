import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_request.dart';
import '../../models/response/access_role_response.dart';
import '../../providers/auth_provider.dart';
import '../../services/auth_service.dart';
import '../../services/other_services/accounts_service.dart';
import '../../services/other_services/employees_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/empty_view.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

const _org = ['org.manage'];

class BranchesScreen extends StatelessWidget {
  const BranchesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Branches',
          list: (f) => AccountsService.branchList(search: f['search'] as String?, isActive: f['is_active'] as bool?),
          create: (b, _) => AccountsService.branchCreate(b),
          update: (i, b, _) => AccountsService.branchUpdate(i['id'] as int, b),
          deactivate: (i) => AccountsService.branchDeactivate(i['id'] as int),
          managePerms: _org,
          activeFilterKey: 'is_active',
          titleOf: (i) => '${i['name']}${i['code'] != null && '${i['code']}'.isNotEmpty ? '  (${i['code']})' : ''}',
          subtitleOf: (i) => [i['city'], i['state_name']].where((e) => e != null && '$e'.isNotEmpty).join(', ') + '  ·  ${i['employee_count'] ?? 0} employees',
          fields: [
            const FieldSpec('name', 'Name', required: true),
            const FieldSpec('code', 'Code'),
            const FieldSpec('address', 'Address', type: FieldType.multiline),
            const FieldSpec('city', 'City'),
            FieldSpec('state_id', 'State', type: FieldType.dropdown, loadOptions: Lookups.states, clearable: true),
            FieldSpec('latitude', 'Latitude', type: FieldType.decimal, validator: Validators.latitude),
            FieldSpec('longitude', 'Longitude', type: FieldType.decimal, validator: Validators.longitude),
            const FieldSpec('allowed_radius_meters', 'Allowed radius (meters)', type: FieldType.integer),
          ],
        ),
      );
}

class DepartmentsScreen extends StatelessWidget {
  const DepartmentsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Departments',
          list: (f) => EmployeesService.departmentList(search: f['search'] as String?, isActive: f['is_active'] as bool?),
          create: (b, _) => EmployeesService.departmentCreate('${b['name']}', code: b['code'] as String?),
          update: (i, b, _) => EmployeesService.departmentUpdate(i['id'] as int, '${b['name'] ?? i['name']}', '${b['code'] ?? i['code'] ?? ''}'),
          deactivate: (i) => EmployeesService.departmentDeactivate(i['id'] as int),
          managePerms: _org,
          activeFilterKey: 'is_active',
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${i['code'] ?? ''}  ·  ${i['employee_count'] ?? 0} employees',
          fields: const [FieldSpec('name', 'Name', required: true), FieldSpec('code', 'Code')],
        ),
      );
}

class DesignationsScreen extends StatelessWidget {
  const DesignationsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Designations',
          list: (f) => EmployeesService.designationList(search: f['search'] as String?, isActive: f['is_active'] as bool?),
          create: (b, _) => EmployeesService.designationCreate('${b['name']}'),
          update: (i, b, _) => EmployeesService.designationUpdate(i['id'] as int, '${b['name'] ?? i['name']}'),
          deactivate: (i) => EmployeesService.designationDeactivate(i['id'] as int),
          managePerms: _org,
          activeFilterKey: 'is_active',
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${i['employee_count'] ?? 0} employees',
          fields: const [FieldSpec('name', 'Name', required: true)],
        ),
      );
}

/// Organization details (owner only). Edits only fields that changed values the user typed.
class OrganizationScreen extends StatelessWidget {
  const OrganizationScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    final org = auth.org;
    if (org == null) return const AppScaffold(title: 'Organization', body: EmptyView(message: 'Organization not loaded.'));
    return CrudFormScreen(
      title: 'Organization',
      item: org.raw,
      submitLabel: 'Save changes',
      fields: [
        const FieldSpec('organization_name', 'Organization name', required: true),
        const FieldSpec('legal_name', 'Legal name'),
        const FieldSpec('business_type', 'Business type'),
        const FieldSpec('industry', 'Industry'),
        const FieldSpec('description', 'Description', type: FieldType.multiline),
        const FieldSpec('registration_number', 'Registration number'),
        FieldSpec('gst_number', 'GST number', validator: Validators.gst),
        FieldSpec('pan_number', 'PAN', validator: Validators.pan),
        const FieldSpec('cin_number', 'CIN'),
        const FieldSpec('email', 'Email', type: FieldType.email),
        const FieldSpec('phone_number', 'Phone', type: FieldType.phone),
        const FieldSpec('alternate_phone_number', 'Alternate phone', type: FieldType.phone),
        FieldSpec('website', 'Website', validator: Validators.url),
        const FieldSpec('address_line_1', 'Address line 1'),
        const FieldSpec('address_line_2', 'Address line 2'),
        const FieldSpec('city', 'City'),
        const FieldSpec('district', 'District'),
        const FieldSpec('state', 'State'),
        FieldSpec('pincode', 'Pincode', validator: Validators.pincode),
        const FieldSpec('country', 'Country'),
        FieldSpec('latitude', 'Latitude', type: FieldType.decimal, validator: Validators.latitude),
        FieldSpec('longitude', 'Longitude', type: FieldType.decimal, validator: Validators.longitude),
        const FieldSpec('logo', 'Logo', type: FieldType.image),
      ],
      onSubmit: (body, files) async {
        final r = await AuthService.organizationUpdate(org.id, body, logo: files.isEmpty ? null : files.first);
        if (r.ok) await auth.refresh();
        return r;
      },
    );
  }
}

/// Access roles: list, and a form with the permission checklist grouped like the React page.
class AccessRolesScreen extends StatefulWidget {
  const AccessRolesScreen({super.key});
  @override
  State<AccessRolesScreen> createState() => _AccessRolesScreenState();
}

class _AccessRolesScreenState extends State<AccessRolesScreen> {
  Key _k = UniqueKey();

  Future<void> _open([AccessRole? role]) async {
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => AccessRoleFormScreen(role: role)));
    if (saved == true) setState(() => _k = UniqueKey());
  }

  @override
  Widget build(BuildContext context) => AppScaffold(
        title: 'Access roles',
        floatingActionButton: FloatingActionButton.extended(onPressed: _open, icon: const Icon(Icons.add), label: const Text('Add role')),
        body: ApiBuilder(
          key: _k,
          load: () => AccountsService.accessRoleList(),
          builder: (ctx, r, reload) {
            final roles = asMapList(r.data).map(AccessRole.fromJson).toList();
            if (roles.isEmpty) return const EmptyView(message: 'No access roles yet.');
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView.builder(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 90),
                itemCount: roles.length,
                itemBuilder: (_, i) {
                  final role = roles[i];
                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(role.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text('${role.permissionCodes.length} permissions · ${role.employeeCount} employees${role.isActive ? '' : ' · inactive'}'),
                      onTap: () => _open(role),
                      trailing: role.isActive
                          ? IconButton(
                              icon: const Icon(Icons.block),
                              tooltip: 'Deactivate',
                              onPressed: () async {
                                final ok = await AppDialogs.confirm(context, title: 'Deactivate role?', message: role.name, danger: true, confirmLabel: 'Deactivate');
                                if (!ok) return;
                                final res = await AccountsService.accessRoleDeactivate(role.id);
                                if (!context.mounted) return;
                                Toast.result(context, res, success: 'Role deactivated.');
                                if (res.ok) reload();
                              },
                            )
                          : null,
                    ),
                  );
                },
              ),
            );
          },
        ),
      );
}

class AccessRoleFormScreen extends StatefulWidget {
  final AccessRole? role;
  const AccessRoleFormScreen({super.key, this.role});
  @override
  State<AccessRoleFormScreen> createState() => _AccessRoleFormScreenState();
}

class _AccessRoleFormScreenState extends State<AccessRoleFormScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name = TextEditingController(text: widget.role?.name ?? '');
  late final TextEditingController _desc = TextEditingController(text: widget.role?.description ?? '');
  late final Set<String> _selected = {...?widget.role?.permissionCodes};
  bool _busy = false;
  List<PermissionItem>? _perms;
  String? _error;

  @override
  void initState() {
    super.initState();
    AccountsService.permissionList().then((r) {
      if (!mounted) return;
      setState(() {
        if (r.ok) {
          _perms = asMapList(r.data).map(PermissionItem.fromJson).toList();
        } else {
          _error = r.fullMessage;
        }
      });
    });
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    final req = AccessRoleRequest(
      accessRoleId: widget.role?.id,
      name: _name.text.trim(),
      description: _desc.text.trim(),
      permissionCodes: _selected.toList()..sort(),
    );
    final r = widget.role == null ? await AccountsService.accessRoleCreate(req) : await AccountsService.accessRoleUpdate(req);
    if (!mounted) return;
    setState(() => _busy = false);
    Toast.result(context, r, success: 'Role saved.');
    if (r.ok) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<PermissionItem>>{};
    for (final p in _perms ?? <PermissionItem>[]) {
      groups.putIfAbsent(p.group, () => []).add(p);
    }
    return Scaffold(
      appBar: AppBar(title: Text(widget.role == null ? 'New access role' : 'Edit access role')),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            TextFormField(controller: _name, decoration: const InputDecoration(labelText: 'Role name *'), validator: (v) => Validators.required(v, 'Role name')),
            const SizedBox(height: 12),
            TextFormField(controller: _desc, maxLines: 2, decoration: const InputDecoration(labelText: 'Description')),
            const SizedBox(height: 16),
            Text('Permissions (${_selected.length} selected)', style: Theme.of(context).textTheme.titleMedium),
            if (_error != null) Padding(padding: const EdgeInsets.all(12), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
            if (_perms == null && _error == null) const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
            for (final g in groups.entries)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text('${g.key}  (${g.value.where((p) => _selected.contains(p.code)).length}/${g.value.length})'),
                children: [
                  for (final p in g.value)
                    CheckboxListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      value: _selected.contains(p.code),
                      title: Text(p.label),
                      subtitle: Text(p.code, style: Theme.of(context).textTheme.bodySmall),
                      onChanged: (v) => setState(() => v == true ? _selected.add(p.code) : _selected.remove(p.code)),
                    ),
                ],
              ),
            const SizedBox(height: 16),
            PrimaryButton(label: 'Save role', busy: _busy, onPressed: _save),
          ]),
        ),
      ),
    );
  }
}
