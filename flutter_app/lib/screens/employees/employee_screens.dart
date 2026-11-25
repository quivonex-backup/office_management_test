import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_response.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../api/api_request.dart';
import '../../api/api_url.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/employees_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/cards/info_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

/// Employee create / edit fields. Keys are the multipart keys the React EmployeeForm sends.
List<FieldSpec> employeeFields({required bool canAssignRole, required bool canCreateUser}) => [
      FieldSpec('first_name', 'First name', required: true, validator: (v) => Validators.name(v, label: 'First name', required: true)),
      FieldSpec('middle_name', 'Middle name', validator: (v) => Validators.name(v, label: 'Middle name')),
      FieldSpec('last_name', 'Last name', required: true, validator: (v) => Validators.name(v, label: 'Last name', required: true)),
      const FieldSpec('date_of_birth', 'Date of birth', type: FieldType.date),
      FieldSpec('gender', 'Gender', type: FieldType.dropdown, options: const [Opt('MALE', 'Male'), Opt('FEMALE', 'Female'), Opt('OTHER', 'Other')]),
      FieldSpec('mobile', 'Mobile', type: FieldType.phone, validator: Validators.mobile),
      FieldSpec('alternate_mobile', 'Alternate mobile', type: FieldType.phone, validator: (v) => Validators.mobile(v, label: 'Alternate mobile')),
      FieldSpec('personal_email', 'Personal email', type: FieldType.email),
      const FieldSpec('address', 'Address', type: FieldType.multiline),
      const FieldSpec('state', 'State'),
      const FieldSpec('district', 'District'),
      const FieldSpec('taluka', 'Taluka'),
      FieldSpec('pincode', 'Pincode', validator: Validators.pincode),
      const FieldSpec('profile_photo', 'Profile photo', type: FieldType.image),
      // job
      const FieldSpec('joining_date', 'Joining date', type: FieldType.date),
      FieldSpec('branch_id', 'Branch', type: FieldType.dropdown, loadOptions: Lookups.branches, clearable: true, readValue: (i) => (i['branch'] as Map?)?['id']),
      FieldSpec('department_id', 'Department', type: FieldType.dropdown, loadOptions: Lookups.departments, clearable: true, readValue: (i) => (i['department_ref'] as Map?)?['id']),
      FieldSpec('designation_id', 'Designation', type: FieldType.dropdown, loadOptions: Lookups.designations, clearable: true, readValue: (i) => (i['designation_ref'] as Map?)?['id']),
      if (canAssignRole)
        FieldSpec('access_role_id', 'Access role', type: FieldType.dropdown, loadOptions: Lookups.accessRoles, clearable: true, readValue: (i) => (i['access_role'] as Map?)?['id']),
      FieldSpec('reports_to_id', 'Reports to', type: FieldType.dropdown, loadOptions: Lookups.employees, clearable: true, readValue: (i) => (i['reports_to'] as Map?)?['id']),
      FieldSpec('work_state', 'Work state', type: FieldType.dropdown, loadOptions: Lookups.states, clearable: true),
      const FieldSpec('attendance_location_exempt', 'Remote worker (no location check)', type: FieldType.boolean),
      if (canCreateUser) const FieldSpec('create_user', 'Create a login for this employee', type: FieldType.boolean, createOnly: true),
      // emergency
      const FieldSpec('emergency_contact_name', 'Emergency contact name'),
      FieldSpec('emergency_contact_number', 'Emergency contact number', type: FieldType.phone, validator: (v) => Validators.mobile(v, label: 'Emergency number')),
      const FieldSpec('emergency_contact_relation', 'Relation'),
      // statutory + bank
      const FieldSpec('pf_uan', 'PF UAN'),
      const FieldSpec('vpf_percentage', 'Voluntary PF %', type: FieldType.decimal),
      const FieldSpec('esi_ip_number', 'ESI IP number'),
      FieldSpec('pan_number', 'PAN', validator: Validators.pan),
      FieldSpec('tax_regime', 'Tax regime', type: FieldType.dropdown, options: const [Opt('OLD', 'Old regime'), Opt('NEW', 'New regime')]),
      const FieldSpec('bank_account_number', 'Bank account number'),
      FieldSpec('bank_ifsc', 'IFSC', validator: Validators.ifsc),
      const FieldSpec('bank_name', 'Bank name'),
      const FieldSpec('bank_branch', 'Bank branch'),
      FieldSpec('upi_id', 'UPI ID', validator: Validators.upi),
      const FieldSpec('documents', 'Document', type: FieldType.file),
    ];

Future<ApiResult<dynamic>> _submitEmployee(int? id, Map<String, dynamic> body, List<UploadFile> files) {
  UploadFile? photo;
  final docs = <UploadFile>[];
  for (final f in files) {
    if (f.field == 'profile_photo') {
      photo = f;
    } else {
      docs.add(f.withField('documents'));
    }
  }
  return id == null ? EmployeesService.create(body, photo: photo, documents: docs) : EmployeesService.update(id, body, photo: photo, documents: docs);
}

class EmployeeListScreen extends StatelessWidget {
  const EmployeeListScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    final fields = employeeFields(canAssignRole: auth.can('access.manage'), canCreateUser: auth.can('employee.create_user'));
    return CrudListScreen(
      config: CrudConfig(
        title: 'Employees',
        list: (f) => EmployeesService.list(f),
        create: (b, files) => _submitEmployee(null, b, files),
        fields: fields,
        managePerms: const ['employee.update'],
        createLabel: 'Add employee',
        filters: [
          FilterSpec('branch_id', 'Branch', loadOptions: Lookups.branches),
          FilterSpec('department_id', 'Department', loadOptions: Lookups.departments),
          FilterSpec('designation_id', 'Designation', loadOptions: Lookups.designations),
          const FilterSpec('inactive_only', 'Status', options: [Opt(true, 'Left the company')]),
        ],
        header: (ctx, r) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: Align(alignment: Alignment.centerLeft, child: Text('Showing: ${r.scopeApplied}', style: Theme.of(ctx).textTheme.bodySmall)),
        ),
        titleOf: (i) => '${i['full_name']}',
        subtitleOf: (i) => [i['employee_code'], i['designation'], i['department']].where((e) => e != null && '$e'.isNotEmpty).join(' · '),
        badgeOf: (i) => i['is_active'] == false ? 'INACTIVE' : null,
        onTap: (c, i, reload) async {
          await Navigator.push(c, MaterialPageRoute(builder: (_) => EmployeeDetailScreen(employeeId: i['id'] as int)));
          reload();
        },
      ),
    );
  }
}

class EmployeeDetailScreen extends StatefulWidget {
  final int employeeId;
  const EmployeeDetailScreen({super.key, required this.employeeId});
  @override
  State<EmployeeDetailScreen> createState() => _EmployeeDetailScreenState();
}

class _EmployeeDetailScreenState extends State<EmployeeDetailScreen> {
  Key _k = UniqueKey();
  void _reload() => setState(() => _k = UniqueKey());

  Future<void> _edit(Map<String, dynamic> e) async {
    final auth = context.read<AuthProvider>();
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => CrudFormScreen(
          title: 'Edit ${e['full_name']}',
          item: e,
          fields: employeeFields(canAssignRole: auth.can('access.manage'), canCreateUser: false),
          onSubmit: (b, files) => _submitEmployee(e['id'] as int, b, files),
        ),
      ),
    );
    if (saved == true) _reload();
  }

  Future<void> _deactivate(Map<String, dynamic> e) async {
    final day = await AppDialogs.prompt(context, title: 'Deactivate ${e['full_name']}', label: 'Last working day (yyyy-mm-dd, optional)', confirmLabel: 'Deactivate');
    if (day == null || !mounted) return;
    final r = await EmployeesService.deactivate(e['id'] as int, lastWorkingDay: day.isEmpty ? null : day);
    if (!mounted) return;
    Toast.result(context, r, success: 'Employee deactivated.');
    if (r.ok) _reload();
  }

  Future<void> _reactivate(Map<String, dynamic> e) async {
    final day = await AppDialogs.prompt(context, title: 'Reactivate ${e['full_name']}', label: 'Joining date (yyyy-mm-dd, optional)', confirmLabel: 'Reactivate');
    if (day == null || !mounted) return;
    final r = await EmployeesService.reactivate(e['id'] as int, joiningDate: day.isEmpty ? null : day);
    if (!mounted) return;
    if (r.ok) {
      final steps = (asMap(r.data)['next_steps'] as List? ?? const []).join('\n• ');
      await AppDialogs.info(context, 'Employee reactivated', steps.isEmpty ? r.message : 'Next steps:\n• $steps');
      _reload();
    } else {
      Toast.result(context, r);
    }
  }

  Future<void> _createUser(Map<String, dynamic> e) async {
    final ok = await AppDialogs.confirm(context, title: 'Create login?', message: 'Create a login for ${e['full_name']}.', confirmLabel: 'Create');
    if (!ok || !mounted) return;
    final r = await EmployeesService.createUser(e['id'] as int);
    if (!mounted) return;
    Toast.result(context, r, success: 'Login created.');
    if (r.ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return AppScaffold(
      title: 'Employee',
      drawer: false,
      body: ApiBuilder(
        key: _k,
        load: () => EmployeesService.detail(widget.employeeId),
        builder: (ctx, r, reload) {
          final e = asMap(r.data);
          final docs = asMapList(e['documents']);
          String? ref(String k) => (e[k] as Map?)?['name'] as String?;
          final canEdit = auth.can('employee.update');
          return ListView(padding: const EdgeInsets.all(12), children: [
            Row(children: [
              CircleAvatar(
                radius: 32,
                backgroundImage: (e['profile_photo'] ?? '').toString().isNotEmpty ? NetworkImage(ApiUrls.media(e['profile_photo'] as String)) : null,
                child: (e['profile_photo'] ?? '').toString().isEmpty ? Text(Fmt.initials('${e['full_name']}')) : null,
              ),
              const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${e['full_name']}', style: Theme.of(context).textTheme.titleLarge),
                Text('${e['employee_code']}'),
                Wrap(spacing: 6, children: [StatusBadge(e['is_active'] == false ? 'INACTIVE' : 'ACTIVE'), if (e['has_user_account'] == true) const StatusBadge('HAS LOGIN', color: Colors.blueGrey)]),
              ])),
            ]),
            const SizedBox(height: 10),
            if (canEdit)
              Wrap(spacing: 8, runSpacing: 8, children: [
                OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _edit(e), icon: const Icon(Icons.edit_outlined), label: const Text('Edit')),
                if (e['has_user_account'] != true && auth.can('employee.create_user'))
                  OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _createUser(e), icon: const Icon(Icons.vpn_key_outlined), label: const Text('Create login')),
                if (e['is_active'] != false)
                  OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _deactivate(e), icon: const Icon(Icons.person_off_outlined), label: const Text('Deactivate'))
                else
                  OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _reactivate(e), icon: const Icon(Icons.person_add_alt), label: const Text('Reactivate')),
              ]),
            const SizedBox(height: 10),
            InfoCard(title: 'Job', rows: [
              MapEntry('Branch', ref('branch')),
              MapEntry('Department', ref('department_ref') ?? e['department'] as String?),
              MapEntry('Designation', ref('designation_ref') ?? e['designation'] as String?),
              MapEntry('Reports to', (e['reports_to'] as Map?)?['full_name'] as String?),
              MapEntry('Access role', ref('access_role')),
              MapEntry('Joined', e['joining_date'] == null ? null : Fmt.date(e['joining_date'])),
              MapEntry('Status', Fmt.label(e['employment_status'] as String?)),
              MapEntry('Work state', e['work_state_name'] as String?),
            ]),
            const SizedBox(height: 8),
            InfoCard(title: 'Personal', rows: [
              MapEntry('Mobile', e['mobile'] as String?),
              MapEntry('Alternate', e['alternate_mobile'] as String?),
              MapEntry('Email', e['personal_email'] as String?),
              MapEntry('Date of birth', e['date_of_birth'] == null ? null : Fmt.date(e['date_of_birth'])),
              MapEntry('Gender', Fmt.label(e['gender'] as String?)),
              MapEntry('Address', [e['address'], e['taluka'], e['district'], e['state'], e['pincode']].where((x) => x != null && '$x'.isNotEmpty).join(', ')),
              MapEntry('Emergency', [e['emergency_contact_name'], e['emergency_contact_number'], e['emergency_contact_relation']].where((x) => x != null && '$x'.isNotEmpty).join(' · ')),
            ]),
            const SizedBox(height: 8),
            InfoCard(title: 'Statutory & bank', rows: [
              MapEntry('PAN', e['pan_number'] as String?),
              MapEntry('PF UAN', e['pf_uan'] as String?),
              MapEntry('ESI', e['esi_ip_number'] as String?),
              MapEntry('Tax regime', e['tax_regime'] as String?),
              MapEntry('Bank', [e['bank_name'], e['bank_branch']].where((x) => x != null && '$x'.isNotEmpty).join(', ')),
              MapEntry('Account', e['bank_account_number'] as String?),
              MapEntry('IFSC', e['bank_ifsc'] as String?),
              MapEntry('UPI', e['upi_id'] as String?),
            ]),
            if (docs.isNotEmpty) ...[
              const SizedBox(height: 8),
              Card(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Padding(padding: EdgeInsets.fromLTRB(14, 12, 14, 0), child: Text('Documents', style: TextStyle(fontWeight: FontWeight.w700))),
                  for (final d in docs)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.description_outlined),
                      title: Text('${d['title']}'),
                      subtitle: Text(Fmt.date(d['created_at'])),
                      onTap: () => launchUrl(Uri.parse(ApiUrls.media(d['file'] as String?)), mode: LaunchMode.externalApplication),
                      trailing: canEdit
                          ? IconButton(
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () async {
                                final ok = await AppDialogs.confirm(context, title: 'Delete document?', message: '${d['title']}', danger: true, confirmLabel: 'Delete');
                                if (!ok || !context.mounted) return;
                                final res = await EmployeesService.docDelete(d['id'] as int);
                                if (!context.mounted) return;
                                Toast.result(context, res, success: 'Document deleted.');
                                if (res.ok) _reload();
                              },
                            )
                          : null,
                    ),
                ]),
              ),
            ],
          ]);
        },
      ),
    );
  }
}
