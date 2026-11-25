import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_request.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/leave_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/empty_view.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../../widgets/navigation/app_scaffold.dart';
import '../../constants/app_constants.dart';
import '../generic/crud_form_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';
import '../../widgets/forms/opt.dart';

const _settings = ['settings.manage'];
const _calendarManage = ['calendar.manage', 'settings.manage'];

class LeaveTypesScreen extends StatelessWidget {
  const LeaveTypesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Leave types',
          hasSearch: false,
          list: (_) => LeaveService.typeList(),
          create: (b, _) => LeaveService.typeCreate(b),
          update: (i, b, _) => LeaveService.typeUpdate(i['id'] as int, b),
          deactivate: (i) => LeaveService.typeDeactivate(i['id'] as int),
          managePerms: _settings,
          titleOf: (i) => '${i['name']}  (${i['code']})',
          subtitleOf: (i) => '${Fmt.number(i['annual_allocation'])} days / year · ${i['is_paid'] == true ? 'Paid' : 'Unpaid'}'
              '${i['carry_forward_enabled'] == true ? ' · Carry forward' : ''}',
          fields: const [
            FieldSpec('name', 'Name', required: true),
            FieldSpec('code', 'Code', required: true),
            FieldSpec('description', 'Description', type: FieldType.multiline),
            FieldSpec('annual_allocation', 'Annual allocation (days)', type: FieldType.decimal, required: true),
            FieldSpec('is_paid', 'Paid leave', type: FieldType.boolean, initial: true),
            FieldSpec('carry_forward_enabled', 'Carry forward unused days', type: FieldType.boolean),
            FieldSpec('max_carry_forward_days', 'Max carry-forward days (blank = no limit)', type: FieldType.decimal, clearable: true),
          ],
        ),
      );
}

class HolidaysScreen extends StatelessWidget {
  const HolidaysScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Holidays',
          list: (f) => LeaveService.holidayList({'search': f['search']}),
          create: (b, _) => LeaveService.holidayCreate(b),
          update: (i, b, _) => LeaveService.holidayUpdate(i['id'] as int, b),
          deactivate: (i) => LeaveService.holidayDeactivate(i['id'] as int),
          managePerms: _calendarManage,
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${Fmt.date(i['date'])} · ${Fmt.label(i['holiday_type'] as String?)} · ${Fmt.label(i['pay_type'] as String?)}'
              '${i['is_optional'] == true ? ' · Optional' : ''}',
          fields: [
            const FieldSpec('date', 'Date', type: FieldType.date, required: true),
            const FieldSpec('name', 'Name', required: true),
            FieldSpec('holiday_type', 'Type', type: FieldType.dropdown, required: true, initial: 'PUBLIC', options: Lookups.strings(AppConstants.holidayTypes)),
            FieldSpec('pay_type', 'Pay type', type: FieldType.dropdown, required: true, initial: 'PAID', options: Lookups.strings(const ['PAID', 'UNPAID'])),
            const FieldSpec('is_optional', 'Optional holiday', type: FieldType.boolean),
            const FieldSpec('description', 'Description', type: FieldType.multiline),
          ],
        ),
      );
}

class WeeklyOffsScreen extends StatelessWidget {
  const WeeklyOffsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Weekly offs',
          hasSearch: false,
          list: (f) => LeaveService.weeklyOffList(shiftId: f['shift_id'] as int?),
          create: (b, _) => LeaveService.weeklyOffCreate(b),
          update: (i, b, _) => LeaveService.weeklyOffUpdate(i['id'] as int, b),
          deactivate: (i) => LeaveService.weeklyOffClose(i['id'] as int, Fmt.apiDate(DateTime.now())),
          deactivateLabel: 'Close rule today',
          deactivateWarning: 'The rule ends today. Rules are never deleted.',
          managePerms: _calendarManage,
          filters: [FilterSpec('shift_id', 'Shift', loadOptions: Lookups.shifts)],
          titleOf: (i) => '${i['shift_name']} — ${AppConstants.weekDays[(i['day_of_week'] as int?) ?? 0]}',
          subtitleOf: (i) => '${i['week_of_month'] == null ? 'Every week' : 'Week ${i['week_of_month']} of the month'}'
              ' · from ${Fmt.date(i['effective_from'])}${i['effective_to'] != null ? ' to ${Fmt.date(i['effective_to'])}' : ''}',
          fields: [
            FieldSpec('shift', 'Shift', type: FieldType.dropdown, required: true, loadOptions: Lookups.shifts, createOnly: true),
            FieldSpec('day_of_week', 'Day', type: FieldType.dropdown, required: true, options: Lookups.weekDays()),
            FieldSpec('week_of_month', 'Which week (blank = every week)', type: FieldType.dropdown, clearable: true,
                options: [for (var n = 1; n <= 5; n++) Opt(n, 'Week $n')]),
            const FieldSpec('effective_from', 'Effective from', type: FieldType.date, required: true),
            const FieldSpec('effective_to', 'Effective to', type: FieldType.date, clearable: true),
          ],
        ),
      );
}

class LeaveApplicationsScreen extends StatelessWidget {
  const LeaveApplicationsScreen({super.key});

  Future<bool> _review(BuildContext context, Map<String, dynamic> i, String decision) async {
    final note = await AppDialogs.prompt(context,
        title: decision == 'APPROVED' ? 'Approve leave' : 'Reject leave', label: 'Remarks', required: decision == 'REJECTED', confirmLabel: decision == 'APPROVED' ? 'Approve' : 'Reject');
    if (note == null || !context.mounted) return false;
    final r = await LeaveService.applicationReview(LeaveReviewRequest(applicationId: i['id'] as int, decision: decision, reviewRemarks: note));
    if (!context.mounted) return false;
    Toast.result(context, r, success: 'Leave ${decision.toLowerCase()}.');
    return r.ok;
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    return CrudListScreen(
      config: CrudConfig(
        title: 'Leave applications',
        hasSearch: false,
        list: (f) => LeaveService.applicationList(f),
        filters: [
          FilterSpec('status', 'Status', options: Lookups.strings(const ['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'])),
          FilterSpec('leave_type_id', 'Leave type', loadOptions: Lookups.leaveTypes),
        ],
        titleOf: (i) => '${i['employee_name']} · ${i['leave_type_name']}',
        subtitleOf: (i) => '${Fmt.date(i['start_date'])} → ${Fmt.date(i['end_date'])} · ${Fmt.number(i['total_days'])} day(s)\n${i['reason'] ?? ''}',
        badgeOf: (i) => i['status'] as String?,
        rowActions: [
          RowAction('Approve', Icons.check_circle_outline, (c, i) => _review(c, i, 'APPROVED'),
              visible: (i) => i['status'] == 'PENDING' && auth.can('leave.approve')),
          RowAction('Reject', Icons.cancel_outlined, (c, i) => _review(c, i, 'REJECTED'),
              visible: (i) => i['status'] == 'PENDING' && auth.can('leave.approve')),
          RowAction('Cancel leave', Icons.event_busy_outlined, (c, i) async {
            final ok = await AppDialogs.confirm(c, title: 'Cancel this leave?', message: '${i['employee_name']} · ${i['leave_type_name']}', danger: true);
            if (!ok || !c.mounted) return false;
            final r = await LeaveService.applicationCancel(i['id'] as int);
            if (c.mounted) Toast.result(c, r, success: 'Leave cancelled.');
            return r.ok;
          }, visible: (i) => (i['status'] == 'PENDING' || i['status'] == 'APPROVED') && auth.can('leave.approve')),
        ],
      ),
    );
  }
}

class LeaveBalancesScreen extends StatelessWidget {
  const LeaveBalancesScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final year = DateTime.now().year;
    return CrudListScreen(
      config: CrudConfig(
        title: 'Leave balances',
        hasSearch: false,
        baseFilters: {'leave_year': year},
        list: (f) => LeaveService.balanceList(f),
        filters: [
          FilterSpec('leave_type_id', 'Leave type', loadOptions: Lookups.leaveTypes),
          FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees),
          FilterSpec('leave_year', 'Year', options: [for (var y = year + 1; y >= year - 3; y--) Opt(y, '$y')]),
        ],
        titleOf: (i) => '${i['employee_name']} · ${i['leave_type_name']}',
        subtitleOf: (i) => 'Allocated ${Fmt.number(i['allocated_days'])} · Used ${Fmt.number(i['used_days'])} · Pending ${Fmt.number(i['pending_days'])}',
        trailingOf: (i) => '${Fmt.number(i['available_days'])} left',
        rowActions: [
          RowAction('Adjust balance', Icons.tune, (c, i) async {
            final saved = await Navigator.push<bool>(
              c,
              MaterialPageRoute(
                builder: (_) => CrudFormScreen(
                  title: 'Adjust ${i['employee_name']}',
                  fields: const [
                    FieldSpec('days', 'Days (use minus to deduct)', type: FieldType.decimal, required: true),
                    FieldSpec('remarks', 'Remarks', type: FieldType.multiline, required: true),
                  ],
                  onSubmit: (b, f) => LeaveService.balanceAdjust(i['id'] as int, num.parse('${b['days']}'), '${b['remarks']}'),
                ),
              ),
            );
            return saved == true;
          }, visible: (_) => context.read<AuthProvider>().canAny(_settings)),
        ],
      ),
    );
  }
}

class LeaveHistoryScreen extends StatelessWidget {
  const LeaveHistoryScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Leave history',
          hasSearch: false,
          list: (f) => LeaveService.transactionList(f),
          filters: [
            FilterSpec('leave_type_id', 'Leave type', loadOptions: Lookups.leaveTypes),
            FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees),
            FilterSpec('transaction_type', 'Type',
                options: Lookups.strings(const ['ALLOCATION', 'PENDING_RESERVE', 'APPROVAL', 'REJECTION', 'CANCELLATION', 'ADJUSTMENT', 'CARRY_FORWARD'])),
          ],
          titleOf: (i) => '${i['employee_name']} · ${i['leave_type_name']}',
          subtitleOf: (i) => '${Fmt.label(i['transaction_type'] as String?)} · ${Fmt.dateTime(i['created_at'])}\n${i['remarks'] ?? ''}',
          trailingOf: (i) => '${Fmt.number(i['days'])} d',
        ),
      );
}

/// The logged-in employee's own month: working days, weekly offs, holidays.
class MyCalendarScreen extends StatefulWidget {
  const MyCalendarScreen({super.key});
  @override
  State<MyCalendarScreen> createState() => _MyCalendarScreenState();
}

class _MyCalendarScreenState extends State<MyCalendarScreen> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  Key _k = UniqueKey();

  void _shift(int d) => setState(() {
        _month = DateTime(_month.year, _month.month + d);
        _k = UniqueKey();
      });

  Color _color(String t) => switch (t) {
        'HOLIDAY' => Colors.orange,
        'WEEKLY_OFF' => Colors.blueGrey,
        'WORKING_DAY' => Colors.green,
        _ => Colors.grey,
      };

  @override
  Widget build(BuildContext context) {
    final from = DateTime(_month.year, _month.month, 1);
    final to = DateTime(_month.year, _month.month + 1, 0);
    return AppScaffold(
      title: 'My calendar',
      body: Column(children: [
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          IconButton(onPressed: () => _shift(-1), icon: const Icon(Icons.chevron_left)),
          Text('${_monthName(_month.month)} ${_month.year}', style: Theme.of(context).textTheme.titleMedium),
          IconButton(onPressed: () => _shift(1), icon: const Icon(Icons.chevron_right)),
        ]),
        Expanded(
          child: ApiBuilder(
            key: _k,
            load: () => LeaveService.myCalendar(Fmt.apiDate(from), Fmt.apiDate(to)),
            builder: (ctx, r, reload) {
              final days = asMapList(asMap(r.data)['calendar']);
              if (days.isEmpty) return const EmptyView(message: 'No calendar days.');
              return ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: days.length,
                itemBuilder: (_, i) {
                  final d = days[i];
                  final type = '${d['day_type']}';
                  return Card(
                    margin: const EdgeInsets.only(bottom: 6),
                    child: ListTile(
                      dense: true,
                      leading: CircleAvatar(radius: 6, backgroundColor: _color(type)),
                      title: Text(Fmt.date(d['date'])),
                      subtitle: Text(d['holiday_name'] != null ? '${d['holiday_name']}' : (d['shift_name'] != null ? '${d['shift_name']}  ${Fmt.time(d['shift_start_time'])} – ${Fmt.time(d['shift_end_time'])}' : '')),
                      trailing: StatusBadge(type, color: _color(type)),
                    ),
                  );
                },
              );
            },
          ),
        ),
      ]),
    );
  }

  String _monthName(int m) => const ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][m - 1];
}
