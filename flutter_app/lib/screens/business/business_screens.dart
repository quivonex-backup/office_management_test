import 'package:flutter/material.dart';

import '../../constants/app_colors.dart';
import '../../widgets/cards/summary_stat.dart';
import 'package:provider/provider.dart';

import '../../api/api_response.dart';
import '../../constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/business_service.dart';
import '../../utils/helpers.dart';
import '../../utils/validators.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

String _j(Iterable<dynamic> parts, [String sep = ' · ']) => parts.where((e) => e != null && '$e'.trim().isNotEmpty).join(sep);

class ClientsScreen extends StatelessWidget {
  const ClientsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Clients',
          list: (f) => BusinessService.clientList(f),
          create: (b, files) => BusinessService.clientCreate(b, files: files),
          update: (i, b, files) => BusinessService.clientUpdate(i['id'] as int, b, files: files),
          deactivate: (i) => BusinessService.clientDeactivate(i['id'] as int),
          managePerms: const ['client.manage'],
          titleOf: (i) => '${i['client_name']}',
          subtitle: 'Manage your client database and documents',
          subtitleOf: (i) => _j([i['client_code'], i['company_name'], i['mobile'], i['email']]),
          columns: [
            ColumnSpec('Code', (i) => '${i['client_code'] ?? ''}', flex: 3),
            ColumnSpec('Name', (i) => '${i['client_name']}', flex: 3, avatar: true),
            ColumnSpec('Company', (i) => '${i['company_name'] ?? ''}', flex: 3),
            ColumnSpec('Mobile', (i) => '${i['mobile'] ?? ''}', flex: 2),
            ColumnSpec('Email', (i) => '${i['email'] ?? ''}', flex: 3),
            ColumnSpec('Status', (i) => i['is_active'] == false ? 'INACTIVE' : 'ACTIVE', flex: 2, badge: true),
          ],
          fields: [
            const FieldSpec('client_name', 'Client name', required: true),
            const FieldSpec('company_name', 'Company name'),
            FieldSpec('mobile', 'Mobile', type: FieldType.phone, validator: Validators.mobile),
            const FieldSpec('email', 'Email', type: FieldType.email),
            FieldSpec('gst_number', 'GST number', validator: Validators.gst),
            const FieldSpec('address', 'Address', type: FieldType.multiline),
            const FieldSpec('state', 'State'),
            const FieldSpec('district', 'District'),
            const FieldSpec('taluka', 'Taluka'),
            FieldSpec('pincode', 'Pincode', validator: Validators.pincode),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
            const FieldSpec('documents', 'Document', type: FieldType.file),
          ],
        ),
      );
}

class VendorsScreen extends StatelessWidget {
  const VendorsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Vendors',
          list: (f) => BusinessService.vendorList(f),
          create: (b, _) => BusinessService.vendorCreate(b),
          update: (i, b, _) => BusinessService.vendorUpdate(i['id'] as int, b),
          deactivate: (i) => BusinessService.vendorDeactivate(i['id'] as int),
          managePerms: const ['vendor.manage', 'expense.manage'],
          titleOf: (i) => '${i['vendor_name']}',
          subtitle: 'Manage your vendors and suppliers',
          subtitleOf: (i) => _j([i['vendor_code'], i['company_name'], i['phone'], i['email']]),
          columns: [
            ColumnSpec('Code', (i) => '${i['vendor_code'] ?? ''}', flex: 3),
            ColumnSpec('Name', (i) => '${i['vendor_name']}', flex: 3, avatar: true),
            ColumnSpec('Company', (i) => '${i['company_name'] ?? ''}', flex: 3),
            ColumnSpec('Phone', (i) => '${i['phone'] ?? ''}', flex: 2),
            ColumnSpec('Email', (i) => '${i['email'] ?? ''}', flex: 3),
            ColumnSpec('Status', (i) => i['is_active'] == false ? 'INACTIVE' : 'ACTIVE', flex: 2, badge: true),
          ],
          fields: [
            const FieldSpec('vendor_name', 'Vendor name', required: true),
            const FieldSpec('company_name', 'Company name'),
            const FieldSpec('email', 'Email', type: FieldType.email),
            const FieldSpec('phone', 'Phone', type: FieldType.phone),
            const FieldSpec('address_line', 'Address', type: FieldType.multiline),
            const FieldSpec('state', 'State'),
            const FieldSpec('district', 'District'),
            const FieldSpec('taluka', 'Taluka'),
            FieldSpec('pincode', 'Pincode', validator: Validators.pincode),
            const FieldSpec('tax_number', 'Tax number'),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
        ),
      );
}

/// Admins (project.manage) see all projects; everyone else sees the projects they are allocated to.
class ProjectsScreen extends StatelessWidget {
  const ProjectsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final admin = context.read<AuthProvider>().can('project.manage');
    if (!admin) {
      return CrudListScreen(
        config: CrudConfig(
          title: 'Projects',
          hasSearch: false,
          list: (_) async => (await BusinessService.myProjects()).map<List>((d) => d is Map ? (d['projects'] as List? ?? []) : []),
          titleOf: (i) => '${i['project_name']}',
          subtitleOf: (i) => _j([Fmt.label(i['project_role'] as String?), i['is_project_head'] == true ? 'Project head' : null]),
          onTap: (c, i, r) async {
            final res = await BusinessService.myProjectDetail(i['project_id'] as int);
            if (!c.mounted) return;
            final d = asMap(res.data);
            final team = asMapList(d['team']).map((t) => '• ${t['name']} (${Fmt.label(t['project_role'] as String?)})').join('\n');
            AppDialogs.info(c, '${d['project_name'] ?? i['project_name']}',
                '${_j([d['client_name'], Fmt.label(d['status'] as String?)])}\nDeadline: ${Fmt.date(d['deadline'])}\n\nTeam\n$team');
          },
        ),
      );
    }
    return CrudListScreen(
      config: CrudConfig(
        title: 'Projects',
        list: (f) => BusinessService.projectList(f),
        create: (b, files) => BusinessService.projectCreate(b, files: files),
        update: (i, b, files) => BusinessService.projectUpdate(i['id'] as int, b, files: files),
        deactivate: (i) => BusinessService.projectDeactivate(i['id'] as int),
        managePerms: const ['project.manage'],
        filters: [
          FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.projectStatuses)),
          FilterSpec('client_id', 'Client', loadOptions: Lookups.clients),
        ],
        titleOf: (i) => '${i['project_name']}',
        subtitle: 'Manage and track all your projects in one place',
        subtitleOf: (i) => _j([i['client_name'], 'Deadline ${Fmt.date(i['deadline'])}', (i['project_head'] as Map?)?['name']]),
        badgeOf: (i) => i['status'] as String?,
        trailingOf: (i) => Fmt.money(i['total_cost']),
        stats: (items) {
          int n(String st) => items.where((i) => i['status'] == st).length;
          return [
            SummaryStat('Total Projects', '${items.length}', Icons.folder_copy_outlined, AppColors.accent),
            SummaryStat('In Progress', '${n('in_progress')}', Icons.trending_up, AppColors.highlight),
            SummaryStat('Completed', '${n('completed')}', Icons.check_circle_outline, AppColors.success),
            SummaryStat('On Hold', '${n('on_hold')}', Icons.pause_circle_outline, AppColors.textMuted),
          ];
        },
        columns: [
          ColumnSpec('Project', (i) => '${i['project_name']}', flex: 3, avatar: true),
          ColumnSpec('Client', (i) => '${i['client_name'] ?? ''}', flex: 3),
          ColumnSpec('Status', (i) => (i['status'] as String?) ?? '', flex: 2, badge: true),
          ColumnSpec('Priority', (i) => (i['priority'] as String?) ?? '', flex: 2, badge: true),
          ColumnSpec('Budget', (i) => Fmt.money(i['total_cost']), flex: 2),
        ],
        fields: [
          const FieldSpec('project_name', 'Project name', required: true),
          FieldSpec('client', 'Client', type: FieldType.dropdown, required: true, loadOptions: Lookups.clients),
          const FieldSpec('project_type', 'Project type'),
          const FieldSpec('description', 'Description', type: FieldType.multiline),
          const FieldSpec('start_date', 'Start date', type: FieldType.date),
          const FieldSpec('end_date', 'End date', type: FieldType.date),
          const FieldSpec('deadline', 'Deadline', type: FieldType.date),
          FieldSpec('priority', 'Priority', type: FieldType.dropdown, initial: 'medium', options: Lookups.strings(AppConstants.priorities)),
          FieldSpec('status', 'Status', type: FieldType.dropdown, initial: 'new', options: Lookups.strings(AppConstants.projectStatuses)),
          const FieldSpec('total_cost', 'Total cost', type: FieldType.decimal),
          const FieldSpec('live_url', 'Live URL'),
          const FieldSpec('documents', 'Document', type: FieldType.file),
        ],
      ),
    );
  }
}

class TasksScreen extends StatelessWidget {
  const TasksScreen({super.key});

  Future<bool> _move(BuildContext c, Map<String, dynamic> i, {String idKey = 'id'}) async {
    final s = await AppDialogs.choose<String>(c, title: 'Move task to', options: [for (final v in AppConstants.taskStatuses) MapEntry(v, Fmt.label(v))]);
    if (s == null || !c.mounted) return false;
    String? hours;
    if (s == 'DONE') hours = await AppDialogs.prompt(c, title: 'Actual hours (optional)', label: 'Hours');
    final r = await BusinessService.taskStatus(i[idKey] as int, s, actualHours: hours);
    if (c.mounted) Toast.result(c, r, success: 'Status updated.');
    return r.ok;
  }

  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Tasks',
          list: (f) async {
            final r = await BusinessService.taskList(f);
            if (r.ok || r.status != 403) return r;
            // not allowed to see all tasks: show the tasks given to me
            final mine = await BusinessService.myTasks();
            return mine.map<List>((d) => d is Map ? (d['tasks'] as List? ?? []) : []);
          },
          create: (b, _) => BusinessService.taskCreate(b),
          update: (i, b, _) => BusinessService.taskUpdate(i['id'] as int, b),
          deactivate: (i) => BusinessService.taskDeactivate(i['id'] as int),
          managePerms: const ['project.manage'],
          filters: [
            FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.taskStatuses)),
            FilterSpec('project_id', 'Project', loadOptions: Lookups.projects),
          ],
          cards: true,
          subtitle: 'Track tasks across all projects',
          titleOf: (i) => '${i['title']}',
          subtitleOf: (i) => _j([i['project_name'], (i['assigned_to_details'] as Map?)?['name'], i['due_date'] != null ? 'Due ${Fmt.date(i['due_date'])}' : null]),
          badgeOf: (i) => i['status'] as String?,
          rowActions: [RowAction('Change status', Icons.swap_horiz, (c, i) => _move(c, i))],
          fields: [
            FieldSpec('project', 'Project', type: FieldType.dropdown, required: true, loadOptions: Lookups.projects, createOnly: true),
            const FieldSpec('title', 'Title', required: true),
            const FieldSpec('description', 'Description', type: FieldType.multiline),
            FieldSpec('assigned_to', 'Assigned to', type: FieldType.dropdown, loadOptions: Lookups.employees, clearable: true, readValue: (i) => (i['assigned_to_details'] as Map?)?['id']),
            FieldSpec('priority', 'Priority', type: FieldType.dropdown, initial: 'medium', options: Lookups.strings(AppConstants.priorities)),
            const FieldSpec('due_date', 'Due date', type: FieldType.date),
            const FieldSpec('estimated_hours', 'Estimated hours', type: FieldType.decimal),
            const FieldSpec('actual_hours', 'Actual hours', type: FieldType.decimal),
          ],
        ),
      );
}

class TeamAllocationScreen extends StatelessWidget {
  const TeamAllocationScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Team allocation',
          hasSearch: false,
          list: (f) => BusinessService.teamList(f),
          create: (b, _) => BusinessService.teamCreate(b),
          update: (i, b, _) => BusinessService.teamUpdate(i['id'] as int, b),
          deactivate: (i) => BusinessService.teamDeactivate(i['id'] as int),
          managePerms: const ['project.manage'],
          filters: [FilterSpec('project_id', 'Project', loadOptions: Lookups.projects), FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees)],
          titleOf: (i) => '${i['employee_name']} — ${i['project_name']}',
          subtitleOf: (i) => _j([i['project_role'], '${i['allocation_percentage']}%', i['is_project_head'] == true ? 'Project head' : null]),
          rowActions: [
            RowAction('Make project head', Icons.star_outline, (c, i) async {
              final r = await BusinessService.assignHead(i['id'] as int);
              if (c.mounted) Toast.result(c, r, success: 'Project head assigned.');
              return r.ok;
            }, visible: (i) => i['is_project_head'] != true),
          ],
          fields: [
            FieldSpec('project', 'Project', type: FieldType.dropdown, required: true, loadOptions: Lookups.projects, createOnly: true),
            FieldSpec('employee', 'Employee', type: FieldType.dropdown, required: true, loadOptions: Lookups.employees, createOnly: true),
            const FieldSpec('project_role', 'Project role', required: true),
            const FieldSpec('allocation_percentage', 'Allocation %', type: FieldType.decimal, initial: '100'),
            const FieldSpec('start_date', 'Start date', type: FieldType.date),
            const FieldSpec('end_date', 'End date', type: FieldType.date),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
        ),
      );
}

class ExpensesScreen extends StatelessWidget {
  const ExpensesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Expenses',
          list: (f) => BusinessService.expenseList(f),
          create: (b, files) => BusinessService.expenseCreate(b, files: files),
          update: (i, b, files) => BusinessService.expenseUpdate(i['id'] as int, b, files: files),
          deactivate: (i) => BusinessService.expenseDeactivate(i['id'] as int),
          managePerms: const ['expense.manage'],
          filters: [
            FilterSpec('payment_status', 'Payment', options: Lookups.strings(const ['paid', 'unpaid'])),
            FilterSpec('expense_type', 'Type', options: Lookups.strings(AppConstants.expenseTypes)),
          ],
          titleOf: (i) => '${i['title']}',
          subtitle: 'Track and manage all office expenses',
          subtitleOf: (i) => _j([i['expense_number'], i['expense_type_display'], Fmt.date(i['expense_date']), i['vendor_name']]),
          badgeOf: (i) => (i['payment_status'] as String?)?.toUpperCase(),
          trailingOf: (i) => Fmt.money(i['amount']),
          stats: (items) {
            final paid = items.where((i) => i['payment_status'] == 'paid').length;
            return [
              SummaryStat('Total Expenses', '${items.length}', Icons.receipt_long_outlined, AppColors.accent),
              SummaryStat('Paid', '$paid', Icons.check_circle_outline, AppColors.success),
              SummaryStat('Unpaid', '${items.length - paid}', Icons.schedule, AppColors.highlight),
            ];
          },
          columns: [
            ColumnSpec('Number', (i) => '${i['expense_number'] ?? ''}', flex: 2),
            ColumnSpec('Title', (i) => '${i['title']}', flex: 3, avatar: true),
            ColumnSpec('Type', (i) => '${i['expense_type_display'] ?? ''}', flex: 2),
            ColumnSpec('Date', (i) => Fmt.date(i['expense_date']), flex: 2),
            ColumnSpec('Vendor', (i) => '${i['vendor_name'] ?? ''}', flex: 2),
            ColumnSpec('Amount', (i) => Fmt.money(i['amount']), flex: 2),
            ColumnSpec('Payment', (i) => ((i['payment_status'] as String?) ?? '').toUpperCase(), flex: 2, badge: true),
          ],
          fields: [
            const FieldSpec('title', 'Title', required: true),
            FieldSpec('expense_type', 'Type', type: FieldType.dropdown, required: true, options: Lookups.strings(AppConstants.expenseTypes)),
            const FieldSpec('amount', 'Amount', type: FieldType.decimal, required: true),
            const FieldSpec('expense_date', 'Expense date', type: FieldType.date, required: true),
            const FieldSpec('due_date', 'Due date', type: FieldType.date),
            FieldSpec('vendor', 'Vendor', type: FieldType.dropdown, loadOptions: Lookups.vendors, clearable: true),
            FieldSpec('project', 'Project', type: FieldType.dropdown, loadOptions: Lookups.projects, clearable: true),
            FieldSpec('payment_status', 'Payment status', type: FieldType.dropdown, initial: 'unpaid', options: Lookups.strings(const ['paid', 'unpaid'])),
            const FieldSpec('payment_date', 'Payment date', type: FieldType.date),
            FieldSpec('payment_method', 'Payment method', type: FieldType.dropdown, options: Lookups.strings(AppConstants.payMethods)),
            const FieldSpec('reference_number', 'Reference number'),
            const FieldSpec('description', 'Description', type: FieldType.multiline),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
            const FieldSpec('documents', 'Bill / document', type: FieldType.file),
          ],
        ),
      );
}

class RecurringExpensesScreen extends StatelessWidget {
  const RecurringExpensesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Recurring expenses',
          list: (f) => BusinessService.recurringList(f),
          create: (b, _) => BusinessService.recurringCreate(b),
          update: (i, b, _) => BusinessService.recurringUpdate(i['id'] as int, b),
          deactivate: (i) => BusinessService.recurringDeactivate(i['id'] as int),
          managePerms: const ['expense.manage'],
          titleOf: (i) => '${i['title']}',
          subtitleOf: (i) => _j([i['expense_type_display'], i['frequency_display'], i['vendor_name'], 'from ${Fmt.date(i['start_date'])}']),
          fields: [
            const FieldSpec('title', 'Title', required: true),
            FieldSpec('expense_type', 'Type', type: FieldType.dropdown, required: true, options: Lookups.strings(AppConstants.recurringTypes)),
            FieldSpec('frequency', 'Frequency', type: FieldType.dropdown, required: true, initial: 'monthly', options: Lookups.strings(const ['monthly', 'quarterly', 'yearly'])),
            const FieldSpec('start_date', 'Start date', type: FieldType.date, required: true),
            const FieldSpec('end_date', 'End date', type: FieldType.date),
            FieldSpec('vendor', 'Vendor', type: FieldType.dropdown, loadOptions: Lookups.vendors, clearable: true),
            FieldSpec('project', 'Project', type: FieldType.dropdown, loadOptions: Lookups.projects, clearable: true),
            const FieldSpec('description', 'Description', type: FieldType.multiline),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
        ),
      );
}

class ReimbursementsScreen extends StatelessWidget {
  const ReimbursementsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    Future<bool> review(BuildContext c, Map<String, dynamic> i, bool approve) async {
      final note = await AppDialogs.prompt(c, title: approve ? 'Approve claim' : 'Reject claim', label: approve ? 'Note (optional)' : 'Reason', required: !approve, confirmLabel: approve ? 'Approve' : 'Reject');
      if (note == null || !c.mounted) return false;
      final r = await BusinessService.reimbReview(i['id'] as int, approve, note);
      if (c.mounted) Toast.result(c, r, success: approve ? 'Claim approved.' : 'Claim rejected.');
      return r.ok;
    }

    return CrudListScreen(
      config: CrudConfig(
        title: 'Reimbursements',
        hasSearch: false,
        list: (f) => BusinessService.reimbList(f),
        filters: [FilterSpec('status', 'Status', options: Lookups.strings(const ['PENDING', 'APPROVED', 'REJECTED', 'PAID', 'CANCELLED']))],
        titleOf: (i) => '${i['title']}',
        subtitleOf: (i) => _j([i['employee_name'], i['reimbursement_number'], Fmt.date(i['expense_date']), i['payee_upi_id']]),
        badgeOf: (i) => i['status'] as String?,
        trailingOf: (i) => Fmt.money(i['amount']),
        rowActions: [
          RowAction('Approve', Icons.check_circle_outline, (c, i) => review(c, i, true), visible: (i) => i['status'] == 'PENDING' && auth.can('reimbursement.review')),
          RowAction('Reject', Icons.cancel_outlined, (c, i) => review(c, i, false), visible: (i) => i['status'] == 'PENDING' && auth.can('reimbursement.review')),
          RowAction('Mark as paid', Icons.payments_outlined, (c, i) async {
            final saved = await Navigator.push<bool>(
              c,
              MaterialPageRoute(
                builder: (_) => CrudFormScreen(
                  title: 'Mark paid — ${i['title']}',
                  fields: [
                    FieldSpec('payment_method', 'Payment method', type: FieldType.dropdown, required: true, options: Lookups.strings(AppConstants.payMethods)),
                    const FieldSpec('payment_date', 'Payment date', type: FieldType.date, required: true),
                    const FieldSpec('payment_reference', 'Reference / UTR'),
                  ],
                  onSubmit: (b, f) => BusinessService.reimbPay(i['id'] as int, b),
                ),
              ),
            );
            return saved == true;
          }, visible: (i) => i['status'] == 'APPROVED' && auth.can('reimbursement.pay')),
        ],
      ),
    );
  }
}

class ProjectPaymentsScreen extends StatelessWidget {
  const ProjectPaymentsScreen({super.key});

  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Project payments',
          list: (f) => BusinessService.ppList(f),
          create: (b, files) => BusinessService.ppCreate(b, files: files),
          update: (i, b, files) => BusinessService.ppUpdate(i['id'] as int, b, files: files),
          deactivate: (i) => BusinessService.ppCancel(i['id'] as int),
          deactivateLabel: 'Cancel payment',
          deactivateWarning: 'This payment will be cancelled.',
          managePerms: const ['payment.manage'],
          filters: [FilterSpec('project_id', 'Project', loadOptions: Lookups.projects)],
          titleOf: (i) => '${i['project_name']} — ${i['title'] ?? Fmt.label(i['payment_type'] as String?)}',
          subtitleOf: (i) => _j(['Paid ${Fmt.money(i['paid_amount'])}', 'Due ${Fmt.money(i['outstanding_amount'])}', i['due_date'] != null ? 'by ${Fmt.date(i['due_date'])}' : null]),
          badgeOf: (i) => i['status'] as String?,
          trailingOf: (i) => Fmt.money(i['amount']),
          rowActions: [
            RowAction('Record transaction', Icons.add_card_outlined, (c, i) async {
              final saved = await Navigator.push<bool>(
                c,
                MaterialPageRoute(
                  builder: (_) => CrudFormScreen(
                    title: 'Record transaction',
                    fields: [
                      const FieldSpec('amount', 'Amount', type: FieldType.decimal, required: true),
                      FieldSpec('payment_method', 'Method', type: FieldType.dropdown, required: true, options: Lookups.strings(AppConstants.txMethods)),
                      FieldSpec('transaction_date', 'Date', type: FieldType.date, required: true, initial: Fmt.apiDate(DateTime.now())),
                      const FieldSpec('reference_number', 'Reference / receipt number (cash, other)'),
                      const FieldSpec('utr_number', 'UTR (UPI, bank transfer)'),
                      const FieldSpec('bank_name', 'Bank name (bank transfer, cheque)'),
                      const FieldSpec('cheque_number', 'Cheque number'),
                      const FieldSpec('cheque_date', 'Cheque date', type: FieldType.date),
                      const FieldSpec('gateway_transaction_id', 'Gateway transaction id (card, online)'),
                      const FieldSpec('notes', 'Notes', type: FieldType.multiline),
                    ],
                    onSubmit: (b, f) => BusinessService.txCreate({'payment_id': i['id'], ...b}),
                  ),
                ),
              );
              return saved == true;
            }, visible: (i) => i['status'] != 'CANCELLED'),
          ],
          fields: [
            FieldSpec('project', 'Project', type: FieldType.dropdown, required: true, loadOptions: Lookups.projects, createOnly: true),
            FieldSpec('payment_type', 'Type', type: FieldType.dropdown, required: true, initial: 'INSTALLMENT', options: Lookups.strings(const ['ADVANCE', 'INSTALLMENT'])),
            const FieldSpec('title', 'Title'),
            const FieldSpec('installment_number', 'Installment number', type: FieldType.integer),
            const FieldSpec('amount', 'Amount', type: FieldType.decimal, required: true),
            const FieldSpec('due_date', 'Due date', type: FieldType.date),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
            const FieldSpec('documents', 'Document', type: FieldType.file),
          ],
        ),
      );
}

/// Invoice PDFs and payment reminders, per project.
class InvoicesScreen extends StatelessWidget {
  const InvoicesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Invoices and reminders',
          list: (f) => BusinessService.projectList(f),
          titleOf: (i) => '${i['project_name']}',
          subtitleOf: (i) => _j([i['client_name'], Fmt.money(i['total_cost'])]),
          rowActions: [
            RowAction('Download invoice', Icons.picture_as_pdf_outlined, (c, i) async {
              final r = await BusinessService.ppInvoice(i['id'] as int);
              if (!c.mounted) return false;
              if (!r.ok) {
                Toast.result(c, ApiResult<dynamic>.failure(r.fullMessage));
                return false;
              }
              final err = await saveAndOpen(r.data!);
              if (err != null && c.mounted) Toast.show(c, err, error: true);
              return false;
            }),
            RowAction('Send payment reminder', Icons.notifications_active_outlined, (c, i) async {
              final ok = await AppDialogs.confirm(c, title: 'Send reminder?', message: 'Email ${i['client_name']} about pending payments for ${i['project_name']}.', confirmLabel: 'Send');
              if (!ok || !c.mounted) return false;
              final r = await BusinessService.ppReminder([i['id'] as int], true);
              if (c.mounted) Toast.result(c, r, success: 'Reminder sent.');
              return false;
            }),
          ],
        ),
      );
}
