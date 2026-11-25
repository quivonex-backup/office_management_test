import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_response.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/payroll_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/buttons/primary_button.dart';
import '../../widgets/cards/info_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/forms/opt.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../generic/auto_settings_screen.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _j(Iterable<dynamic> parts) => parts.where((e) => e != null && '$e'.trim().isNotEmpty).join(' · ');

class PayrollRunsScreen extends StatelessWidget {
  const PayrollRunsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Pay runs',
          hasSearch: false,
          createLabel: 'New run',
          list: (f) => PayrollService.runList(status: f['status'] as String?),
          create: (b, _) => PayrollService.runCreate('${b['period_start']}', '${b['period_end']}'),
          managePerms: const ['payroll.generate'],
          filters: [FilterSpec('status', 'Status', options: Lookups.strings(const ['DRAFT', 'GENERATED', 'FINALIZED']))],
          titleOf: (i) => '${Fmt.date(i['period_start'])} → ${Fmt.date(i['period_end'])}',
          subtitleOf: (i) => _j(['${i['total_employees'] ?? 0} employees', 'Gross ${Fmt.money(i['total_gross'])}', 'Net ${Fmt.money(i['total_net'])}']),
          badgeOf: (i) => i['status'] as String?,
          onTap: (c, i, reload) async {
            await Navigator.push(c, MaterialPageRoute(builder: (_) => PayrollRunDetailScreen(runId: i['id'] as int)));
            reload();
          },
          fields: const [
            FieldSpec('period_start', 'Period start', type: FieldType.date, required: true),
            FieldSpec('period_end', 'Period end', type: FieldType.date, required: true),
          ],
        ),
      );
}

class PayrollRunDetailScreen extends StatefulWidget {
  final int runId;
  const PayrollRunDetailScreen({super.key, required this.runId});
  @override
  State<PayrollRunDetailScreen> createState() => _PayrollRunDetailScreenState();
}

class _PayrollRunDetailScreenState extends State<PayrollRunDetailScreen> {
  Key _k = UniqueKey();
  bool _busy = false;
  void _reload() => setState(() => _k = UniqueKey());

  Future<void> _act(Future<ApiResult<dynamic>> Function() call, String ok) async {
    setState(() => _busy = true);
    final r = await call();
    if (!mounted) return;
    setState(() => _busy = false);
    if (r.ok) {
      Toast.show(context, r.message.isNotEmpty ? r.message : ok);
      _reload();
    } else {
      await AppDialogs.info(context, 'Could not complete', r.fullMessage);
    }
  }

  Future<void> _payslip(int recordId) async {
    final r = await PayrollService.payslipDownload(recordId);
    if (!mounted) return;
    if (!r.ok) {
      Toast.show(context, r.fullMessage, error: true);
      return;
    }
    final err = await saveAndOpen(r.data!);
    if (err != null && mounted) Toast.show(context, err, error: true);
  }

  Future<void> _pay(Map<String, dynamic> rec) async {
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => CrudFormScreen(
          title: 'Pay ${rec['employee_name']}',
          fields: [
            FieldSpec('amount', 'Amount', type: FieldType.decimal, required: true, initial: '${rec['remaining'] ?? ''}'),
            FieldSpec('payment_date', 'Payment date', type: FieldType.date, required: true, initial: Fmt.apiDate(DateTime.now())),
            FieldSpec('payment_mode', 'Mode', type: FieldType.dropdown, required: true, initial: 'BANK_TRANSFER',
                options: const [Opt('BANK_TRANSFER', 'Bank transfer'), Opt('UPI', 'UPI'), Opt('CHEQUE', 'Cheque'), Opt('CASH', 'Cash')]),
            const FieldSpec('transaction_reference', 'Reference / UTR'),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
          onSubmit: (b, f) => PayrollService.paymentRecord({'payroll_record_id': rec['id'], ...b}),
        ),
      ),
    );
    if (saved == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return AppScaffold(
      title: 'Pay run',
      drawer: false,
      body: ApiBuilder(
        key: _k,
        load: () => PayrollService.runDetail(widget.runId),
        builder: (ctx, r, reload) {
          final run = asMap(r.data);
          final status = '${run['status']}';
          final records = asMapList(run['records']);
          return ListView(padding: const EdgeInsets.all(12), children: [
            InfoCard(
              title: '${Fmt.date(run['period_start'])} → ${Fmt.date(run['period_end'])}',
              trailing: StatusBadge(status),
              rows: [
                MapEntry('Employees', '${run['total_employees'] ?? 0}'),
                MapEntry('Gross', Fmt.money(run['total_gross'])),
                MapEntry('Deductions', Fmt.money(run['total_deductions'])),
                MapEntry('Net pay', Fmt.money(run['total_net'])),
                MapEntry('Finalized', run['finalized_at'] == null ? null : Fmt.dateTime(run['finalized_at'])),
              ],
            ),
            const SizedBox(height: 10),
            if (auth.can('payroll.generate') && status != 'FINALIZED')
              PrimaryButton(label: status == 'DRAFT' ? 'Generate payroll' : 'Regenerate payroll', icon: Icons.play_arrow, busy: _busy, onPressed: () => _act(() => PayrollService.runGenerate(widget.runId), 'Payroll generated.')),
            const SizedBox(height: 8),
            if (auth.can('payroll.finalize') && status == 'GENERATED')
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () async {
                        final ok = await AppDialogs.confirm(context, title: 'Finalize this run?', message: 'Records are locked after finalizing.', confirmLabel: 'Finalize');
                        if (ok) _act(() => PayrollService.runFinalize(widget.runId), 'Run finalized.');
                      },
                icon: const Icon(Icons.lock_outline),
                label: const Text('Finalize'),
              ),
            if (auth.can('payroll.finalize') && status == 'FINALIZED')
              OutlinedButton.icon(
                onPressed: _busy
                    ? null
                    : () async {
                        final reason = await AppDialogs.prompt(context, title: 'Reopen run', label: 'Reason', required: true, confirmLabel: 'Reopen');
                        if (reason != null) _act(() => PayrollService.runReopen(widget.runId, reason), 'Run reopened.');
                      },
                icon: const Icon(Icons.lock_open),
                label: const Text('Reopen'),
              ),
            const SizedBox(height: 12),
            Text('Payslips (${records.length})', style: Theme.of(context).textTheme.titleMedium),
            for (final rec in records)
              Card(
                margin: const EdgeInsets.only(top: 8),
                child: ListTile(
                  title: Text('${rec['employee_name']}  (${rec['employee_code']})', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(_j(['Gross ${Fmt.money(rec['gross_earnings'])}', 'Ded ${Fmt.money(rec['total_deductions'])}', 'Net ${Fmt.money(rec['net'])}', if ((rec['requires_review'] ?? false) == true) '⚠ review'])),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    StatusBadge(rec['payment_status'] as String?),
                    PopupMenuButton<String>(
                      onSelected: (v) {
                        if (v == 'slip') _payslip(rec['id'] as int);
                        if (v == 'pay') _pay(rec);
                      },
                      itemBuilder: (_) => [
                        const PopupMenuItem(value: 'slip', child: Text('Download payslip')),
                        if (status == 'FINALIZED' && auth.can('payroll.finalize') && rec['payment_status'] != 'PAID') const PopupMenuItem(value: 'pay', child: Text('Record payment')),
                      ],
                    ),
                  ]),
                ),
              ),
          ]);
        },
      ),
    );
  }
}

class PayrollPaymentsScreen extends StatelessWidget {
  const PayrollPaymentsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Payroll payments',
          hasSearch: false,
          list: (f) => PayrollService.paymentList(f),
          filters: [FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees)],
          titleOf: (i) => '${i['employee_name']} (${i['employee_code']})',
          subtitleOf: (i) => _j([Fmt.date(i['payment_date']), Fmt.label(i['payment_mode'] as String?), i['transaction_reference']]),
          trailingOf: (i) => Fmt.money(i['amount']),
          rowActions: [
            RowAction('Void payment', Icons.undo, (c, i) async {
              final reason = await AppDialogs.prompt(c, title: 'Void payment', label: 'Reason', required: true, confirmLabel: 'Void');
              if (reason == null || !c.mounted) return false;
              final r = await PayrollService.paymentVoid(i['id'] as int, reason);
              if (c.mounted) Toast.result(c, r, success: 'Payment voided.');
              return r.ok;
            }, visible: (_) => context.read<AuthProvider>().can('payroll.finalize')),
          ],
        ),
      );
}

class SalaryAssignmentsScreen extends StatelessWidget {
  const SalaryAssignmentsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Salary assignments',
          hasSearch: false,
          list: (f) => PayrollService.assignmentList(f),
          filters: [FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees)],
          titleOf: (i) => '${i['employee_name']} (${i['employee_code']})',
          subtitleOf: (i) => _j([i['salary_structure_name'], 'from ${Fmt.date(i['effective_from'])}', i['effective_to'] != null ? 'to ${Fmt.date(i['effective_to'])}' : 'open']),
          trailingOf: (i) => i['monthly_gross'] == null ? null : '${Fmt.money(i['monthly_gross'])}/mo',
        ),
      );
}

class SalaryStructuresScreen extends StatelessWidget {
  const SalaryStructuresScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Salary structures',
          hasSearch: false,
          activeFilterKey: 'is_active',
          list: (f) => PayrollService.structureList(isActive: f['is_active'] as bool?),
          deactivate: (i) => PayrollService.structureDeactivate(i['id'] as int),
          managePerms: const ['salary.assign', 'payroll.generate'],
          titleOf: (i) => '${i['name']}  (${i['code']})',
          subtitleOf: (i) => '${asMapList(i['components']).length} components · gross ${Fmt.money(i['total_gross'])}',
          onTap: (c, i, _) {
            final comps = asMapList(i['components']);
            AppDialogs.info(c, '${i['name']}', comps.isEmpty ? 'No components.' : comps.map((x) => '• ${x['component_name'] ?? x['name'] ?? x['component_code'] ?? ''}').join('\n'));
          },
        ),
      );
}

class PayrollSettingsScreen extends StatelessWidget {
  const PayrollSettingsScreen({super.key});
  @override
  Widget build(BuildContext context) => AutoSettingsScreen(title: 'Payroll settings', load: PayrollService.settingsGet, save: PayrollService.settingsSave);
}
