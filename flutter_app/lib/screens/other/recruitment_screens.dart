import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/recruitment_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/cards/info_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _j(Iterable<dynamic> parts) => parts.where((e) => e != null && '$e'.trim().isNotEmpty).join(' · ');
const _sources = ['JOB_PORTAL', 'REFERRAL', 'WEBSITE', 'WALK_IN', 'CAMPUS', 'AGENCY', 'SOCIAL', 'OTHER'];

List<FieldSpec> _applicantFields() => [
      FieldSpec('first_name', 'First name', required: true, validator: (v) => Validators.name(v, label: 'First name', required: true)),
      const FieldSpec('middle_name', 'Middle name'),
      FieldSpec('last_name', 'Last name', required: true, validator: (v) => Validators.name(v, label: 'Last name', required: true)),
      const FieldSpec('email', 'Email', type: FieldType.email, required: true),
      FieldSpec('mobile', 'Mobile', type: FieldType.phone, required: true, validator: (v) => Validators.mobile(v, required: true)),
      FieldSpec('designation_id', 'Applying for (designation)', type: FieldType.dropdown, loadOptions: Lookups.designations, clearable: true, readValue: (i) => (i['designation'] as Map?)?['id']),
      const FieldSpec('position_title', 'Position title'),
      FieldSpec('department_id', 'Department', type: FieldType.dropdown, loadOptions: Lookups.departments, clearable: true, readValue: (i) => (i['department'] as Map?)?['id']),
      FieldSpec('branch_id', 'Branch', type: FieldType.dropdown, loadOptions: Lookups.branches, clearable: true, readValue: (i) => (i['branch'] as Map?)?['id']),
      FieldSpec('source', 'Source', type: FieldType.dropdown, initial: 'OTHER', options: Lookups.strings(_sources)),
      const FieldSpec('applied_on', 'Applied on', type: FieldType.date),
      const FieldSpec('total_experience_years', 'Experience (years)', type: FieldType.decimal),
      const FieldSpec('current_company', 'Current company'),
      const FieldSpec('current_ctc', 'Current CTC', type: FieldType.decimal),
      const FieldSpec('expected_ctc', 'Expected CTC', type: FieldType.decimal),
      const FieldSpec('notice_period_days', 'Notice period (days)', type: FieldType.integer),
      const FieldSpec('skills', 'Skills', type: FieldType.multiline),
      const FieldSpec('remarks', 'Remarks', type: FieldType.multiline),
      const FieldSpec('resume', 'Resume', type: FieldType.file),
    ];

class ApplicantsScreen extends StatelessWidget {
  const ApplicantsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Applicants',
          createLabel: 'Add applicant',
          list: (f) async {
            final r = await RecruitmentService.list(f);
            return r;
          },
          create: (b, files) => RecruitmentService.create(b, resume: files.isEmpty ? null : files.first),
          managePerms: const ['applicant.create'],
          fields: _applicantFields(),
          filters: [
            FilterSpec('stage', 'Stage', options: Lookups.strings(const ['APPLICANT', 'VERIFICATION', 'ONBOARDING', 'COMPLETED', 'CLOSED'])),
            FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.applicantStatuses)),
          ],
          header: (ctx, r) {
            final s = (r.raw['summary'] as Map?) ?? const {};
            final byStage = (s['by_stage'] as Map?) ?? const {};
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('${s['total'] ?? 0} applicants${byStage.isEmpty ? '' : '  ·  ${byStage.entries.map((e) => '${Fmt.label(e.key as String)} ${e.value}').join(', ')}'}',
                    style: Theme.of(ctx).textTheme.bodySmall),
              ),
            );
          },
          titleOf: (i) => '${i['full_name']}',
          subtitleOf: (i) => _j([i['applicant_code'], (i['designation'] as Map?)?['name'] ?? i['position_title'], i['mobile'], Fmt.label(i['stage'] as String?)]),
          badgeOf: (i) => i['status'] as String?,
          onTap: (c, i, reload) async {
            await Navigator.push(c, MaterialPageRoute(builder: (_) => ApplicantDetailScreen(applicantId: i['id'] as int)));
            reload();
          },
        ),
      );
}

class ApplicantDetailScreen extends StatefulWidget {
  final int applicantId;
  const ApplicantDetailScreen({super.key, required this.applicantId});
  @override
  State<ApplicantDetailScreen> createState() => _ApplicantDetailScreenState();
}

class _ApplicantDetailScreenState extends State<ApplicantDetailScreen> {
  Key _k = UniqueKey();
  void _reload() => setState(() => _k = UniqueKey());

  Future<void> _status(Map<String, dynamic> a) async {
    final s = await AppDialogs.choose<String>(context, title: 'Set status', options: [for (final v in AppConstants.applicantStatuses) MapEntry(v, Fmt.label(v))]);
    if (s == null || !mounted) return;
    final note = await AppDialogs.prompt(context, title: 'Note (optional)', label: 'Note');
    if (note == null || !mounted) return;
    final r = await RecruitmentService.status(a['id'] as int, s, note: note);
    if (!mounted) return;
    Toast.result(context, r, success: 'Status updated.');
    if (r.ok) _reload();
  }

  Future<void> _convert(Map<String, dynamic> a) async {
    final ok = await AppDialogs.confirm(context, title: 'Convert to employee?', message: '${a['full_name']} will become an employee.', confirmLabel: 'Convert');
    if (!ok || !mounted) return;
    final r = await RecruitmentService.convert(a['id'] as int);
    if (!mounted) return;
    Toast.result(context, r, success: 'Converted to employee.');
    if (r.ok) _reload();
  }

  Future<void> _edit(Map<String, dynamic> a) async {
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => CrudFormScreen(
          title: 'Edit applicant',
          item: a,
          fields: _applicantFields(),
          onSubmit: (b, files) => RecruitmentService.update(a['id'] as int, b, resume: files.isEmpty ? null : files.first),
        ),
      ),
    );
    if (saved == true) _reload();
  }

  Future<void> _offer(int id) async {
    final r = await RecruitmentService.offerLetter(id);
    if (!mounted) return;
    if (!r.ok) {
      Toast.show(context, r.fullMessage, error: true);
      return;
    }
    final err = await saveAndOpen(r.data!);
    if (err != null && mounted) Toast.show(context, err, error: true);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return AppScaffold(
      title: 'Applicant',
      drawer: false,
      body: ApiBuilder(
        key: _k,
        load: () => RecruitmentService.detail(widget.applicantId),
        builder: (ctx, r, reload) {
          final d = asMap(r.data);
          final a = asMap(d['applicant']);
          final allowed = (d['allowed_actions'] as List? ?? const []).map((e) => '$e').toList();
          final checks = [...asMapList(d['verification_checks']), ...asMapList(d['onboarding_checks'])];
          final interviews = asMapList(d['interviews']);
          final offer = d['current_offer'] is Map ? asMap(d['current_offer']) : null;
          final history = asMapList(d['history']);
          return ListView(padding: const EdgeInsets.all(12), children: [
            InfoCard(
              title: '${a['full_name']}',
              trailing: StatusBadge(a['status'] as String?),
              rows: [
                MapEntry('Code', a['applicant_code'] as String?),
                MapEntry('Stage', Fmt.label(a['stage'] as String?)),
                MapEntry('Email', a['email'] as String?),
                MapEntry('Mobile', a['mobile'] as String?),
                MapEntry('Position', (a['designation'] as Map?)?['name'] as String? ?? a['position_title'] as String?),
                MapEntry('Department', (a['department'] as Map?)?['name'] as String?),
                MapEntry('Source', Fmt.label(a['source'] as String?)),
                MapEntry('Experience', a['total_experience_years'] == null ? null : '${a['total_experience_years']} yrs'),
                MapEntry('Expected CTC', a['expected_ctc'] == null ? null : Fmt.money(a['expected_ctc'])),
                MapEntry('Joining date', a['joining_date'] == null ? null : Fmt.date(a['joining_date'])),
                MapEntry('Skills', a['skills'] as String?),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (auth.can('applicant.update'))
                OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _edit(a), icon: const Icon(Icons.edit_outlined), label: const Text('Edit')),
              if (auth.can('applicant.status_update'))
                OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _status(a), icon: const Icon(Icons.flag_outlined), label: const Text('Set status')),
              if (allowed.contains('convert') && auth.can('applicant.convert'))
                OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _convert(a), icon: const Icon(Icons.badge_outlined), label: const Text('Convert')),
              if (offer != null)
                OutlinedButton.icon(style: OutlinedButton.styleFrom(minimumSize: const Size(110, 40)), onPressed: () => _offer(a['id'] as int), icon: const Icon(Icons.picture_as_pdf_outlined), label: const Text('Offer letter')),
            ]),
            if (offer != null) ...[
              const SizedBox(height: 8),
              InfoCard(title: 'Current offer (v${offer['version']})', trailing: StatusBadge(offer['status'] as String?), rows: [
                MapEntry('Joining', Fmt.date(offer['joining_date'])),
                MapEntry('Annual CTC', offer['annual_ctc'] == null ? null : Fmt.money(offer['annual_ctc'])),
                MapEntry('Monthly gross', offer['monthly_gross'] == null ? null : Fmt.money(offer['monthly_gross'])),
                MapEntry('Valid until', offer['valid_until'] == null ? null : Fmt.date(offer['valid_until'])),
              ]),
            ],
            if (interviews.isNotEmpty) ...[
              const SizedBox(height: 8),
              InfoCard(title: 'Interviews', rows: [for (final i in interviews) MapEntry('${i['round_name']}', _j([Fmt.label(i['result'] as String?), if (i['scheduled_at'] != null) Fmt.dateTime(i['scheduled_at']), (i['interviewer'] as Map?)?['full_name']]))]),
            ],
            if (checks.isNotEmpty) ...[
              const SizedBox(height: 8),
              InfoCard(title: 'Checklists', rows: [for (final c in checks) MapEntry('${c['label']}', Fmt.label(c['status'] as String?))]),
            ],
            if (history.isNotEmpty) ...[
              const SizedBox(height: 8),
              InfoCard(title: 'History', rows: [for (final h in history.take(15)) MapEntry(Fmt.dateTime(h['created_at']), _j([Fmt.label(h['action'] as String?), h['note']]))]),
            ],
          ]);
        },
      ),
    );
  }
}
