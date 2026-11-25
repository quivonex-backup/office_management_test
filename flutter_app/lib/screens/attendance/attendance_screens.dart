import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_request.dart';
import '../../constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/attendance_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/common/toast.dart';
import '../../widgets/dialogs/app_dialogs.dart';
import '../generic/auto_settings_screen.dart';
import '../generic/crud_list_screen.dart';
import '../generic/crud_models.dart';
import '../generic/lookups.dart';

const _settings = ['settings.manage'];

class ShiftsScreen extends StatelessWidget {
  const ShiftsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Shifts',
          hasSearch: false,
          activeFilterKey: 'is_active',
          list: (f) => AttendanceService.shiftList(isActive: f['is_active'] as bool?),
          create: (b, _) => AttendanceService.shiftCreate(b),
          update: (i, b, _) => AttendanceService.shiftUpdate(i['id'] as int, b),
          deactivate: (i) => AttendanceService.shiftDeactivate(i['id'] as int),
          managePerms: _settings,
          titleOf: (i) => '${i['name']}',
          subtitleOf: (i) => '${Fmt.time(i['start_time'])} – ${Fmt.time(i['end_time'])}${i['crosses_midnight'] == true ? ' (next day)' : ''}',
          fields: const [
            FieldSpec('name', 'Name', required: true),
            FieldSpec('start_time', 'Start time', type: FieldType.time, required: true),
            FieldSpec('end_time', 'End time', type: FieldType.time, required: true),
            FieldSpec('crosses_midnight', 'Ends after midnight', type: FieldType.boolean),
            FieldSpec('late_grace_minutes', 'Late grace (minutes)', type: FieldType.integer, clearable: true),
            FieldSpec('early_departure_grace_minutes', 'Early departure grace (minutes)', type: FieldType.integer, clearable: true),
          ],
        ),
      );
}

class ShiftAssignmentsScreen extends StatelessWidget {
  const ShiftAssignmentsScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Shift assignments',
          hasSearch: false,
          list: (f) => AttendanceService.assignList(f),
          create: (b, _) => AttendanceService.assignCreate(b),
          update: (i, b, _) => AttendanceService.assignUpdate(i['id'] as int, b),
          managePerms: _settings,
          filters: [FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees), FilterSpec('shift_id', 'Shift', loadOptions: Lookups.shifts)],
          titleOf: (i) => '${i['employee_name']} (${i['employee_code']})',
          subtitleOf: (i) => '${i['shift_name']} · from ${Fmt.date(i['effective_from'])}${i['effective_to'] != null ? ' to ${Fmt.date(i['effective_to'])}' : ' (open)'}',
          fields: [
            FieldSpec('employee_id', 'Employee', type: FieldType.dropdown, required: true, loadOptions: Lookups.employees, createOnly: true),
            FieldSpec('shift_id', 'Shift', type: FieldType.dropdown, required: true, loadOptions: Lookups.shifts, readValue: (i) => i['shift']),
            const FieldSpec('effective_from', 'Effective from', type: FieldType.date, required: true),
            const FieldSpec('effective_to', 'Effective to', type: FieldType.date, clearable: true),
          ],
        ),
      );
}

class AttendanceDevicesScreen extends StatelessWidget {
  const AttendanceDevicesScreen({super.key});
  @override
  Widget build(BuildContext context) => CrudListScreen(
        config: CrudConfig(
          title: 'Attendance devices',
          activeFilterKey: 'include_inactive',
          list: (f) => AttendanceService.deviceList(f),
          create: (b, _) => AttendanceService.deviceCreate(b),
          update: (i, b, _) => AttendanceService.deviceUpdate(i['id'] as int, b),
          deactivate: (i) => AttendanceService.deviceDeactivate(i['id'] as int),
          managePerms: const ['attendance.device_manage'],
          titleOf: (i) => '${i['name']}  (${i['device_code']})',
          subtitleOf: (i) => '${(i['branch'] as Map?)?['name'] ?? 'No branch'} · ${i['logged_in'] == true ? 'Logged in' : 'Logged out'}'
              '${i['last_seen_at'] != null ? '\nLast seen ${Fmt.dateTime(i['last_seen_at'])}' : ''}',
          rowActions: [
            RowAction('Reset device password', Icons.lock_reset, (c, i) async {
              final ok = await AppDialogs.confirm(c, title: 'Reset password?', message: 'The tablet will be logged out and a new password is created.', confirmLabel: 'Reset');
              if (!ok || !c.mounted) return false;
              final r = await AttendanceService.deviceResetPassword(i['id'] as int);
              if (!c.mounted) return false;
              if (r.ok) {
                await AppDialogs.info(c, 'New device password', '${asMap(r.data)['password'] ?? r.message}');
              } else {
                Toast.result(c, r);
              }
              return r.ok;
            }),
          ],
          fields: [
            const FieldSpec('name', 'Name', required: true),
            FieldSpec('branch_id', 'Branch', type: FieldType.dropdown, loadOptions: Lookups.branches, clearable: true, readValue: (i) => (i['branch'] as Map?)?['id']),
            const FieldSpec('device_code', 'Device code'),
            const FieldSpec('notes', 'Notes', type: FieldType.multiline),
          ],
        ),
      );
}

class AttendanceSettingsScreen extends StatelessWidget {
  const AttendanceSettingsScreen({super.key});
  @override
  Widget build(BuildContext context) =>
      AutoSettingsScreen(title: 'Attendance settings', load: AttendanceService.settingsGet, save: AttendanceService.settingsSave);
}

/// Attendance register: this month by default, filter by status / employee. Tap a row for punches.
class AttendanceRegisterScreen extends StatelessWidget {
  const AttendanceRegisterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final from = Fmt.apiDate(DateTime(now.year, now.month, 1));
    final to = Fmt.apiDate(DateTime(now.year, now.month + 1, 0));
    return CrudListScreen(
      config: CrudConfig(
        title: 'Attendance',
        hasSearch: false,
        baseFilters: {'from_date': from, 'to_date': to},
        list: (f) => AttendanceService.attendanceList(f),
        filters: [
          FilterSpec('status', 'Status', options: Lookups.strings(AppConstants.attendanceStatuses)),
          FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees),
        ],
        header: (ctx, r) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: Align(alignment: Alignment.centerLeft, child: Text('${Fmt.date(from)} – ${Fmt.date(to)}  ·  scope: ${r.scopeApplied}', style: Theme.of(ctx).textTheme.bodySmall)),
        ),
        titleOf: (i) => '${i['employee_name']} · ${Fmt.date(i['work_date'])}',
        subtitleOf: (i) => '${i['shift_name'] ?? 'No shift'}\nIn ${Fmt.time(i['check_in'])}  Out ${Fmt.time(i['check_out'])}'
            '${(i['late_minutes'] ?? 0) > 0 ? '  ·  Late ${i['late_minutes']}m' : ''}'
            '${(i['overtime_minutes'] ?? 0) > 0 ? '  ·  OT ${i['overtime_minutes']}m' : ''}',
        badgeOf: (i) => i['status'] as String?,
        onTap: (ctx, i, reload) {
          final punches = asMapList(i['punches']);
          AppDialogs.info(
            ctx,
            '${i['employee_name']} · ${Fmt.date(i['work_date'])}',
            'Status: ${Fmt.label(i['status'] as String?)}\nWorked: ${(i['net_work_minutes'] ?? 0)} min\n\n'
            '${punches.isEmpty ? 'No punches.' : punches.map((p) => '${Fmt.label(p['punch_type'] as String?)}  ${Fmt.dateTime(p['punched_at'])}  (${Fmt.label(p['verification_status'] as String?)})').join('\n')}',
          );
        },
      ),
    );
  }
}

class CorrectionsScreen extends StatelessWidget {
  const CorrectionsScreen({super.key});

  Future<bool> _review(BuildContext context, Map<String, dynamic> i, bool approve) async {
    final note = await AppDialogs.prompt(context,
        title: approve ? 'Approve correction' : 'Reject correction', label: 'Note', required: !approve, confirmLabel: approve ? 'Approve' : 'Reject');
    if (note == null || !context.mounted) return false;
    final r = await AttendanceService.correctionReview(CorrectionReviewRequest(correctionId: i['id'] as int, approve: approve, reviewNote: note));
    if (context.mounted) Toast.result(context, r, success: approve ? 'Correction approved.' : 'Correction rejected.');
    return r.ok;
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    return CrudListScreen(
      config: CrudConfig(
        title: 'Corrections',
        hasSearch: false,
        list: (f) => AttendanceService.correctionList(f),
        filters: [
          FilterSpec('status', 'Status', options: Lookups.strings(const ['PENDING', 'APPROVED', 'REJECTED', 'APPLIED'])),
          FilterSpec('employee_id', 'Employee', loadOptions: Lookups.employees),
        ],
        titleOf: (i) => '${i['employee_name']} · ${Fmt.date(i['work_date'])}',
        subtitleOf: (i) => '${Fmt.label(i['field_name'] as String?)}: ${i['old_value'] ?? '—'} → ${i['new_value'] ?? '—'}\n${i['reason'] ?? ''}',
        badgeOf: (i) => i['status'] as String?,
        rowActions: [
          RowAction('Approve', Icons.check_circle_outline, (c, i) => _review(c, i, true),
              visible: (i) => i['status'] == 'PENDING' && auth.can('attendance.approve_correction')),
          RowAction('Reject', Icons.cancel_outlined, (c, i) => _review(c, i, false),
              visible: (i) => i['status'] == 'PENDING' && auth.can('attendance.approve_correction')),
          RowAction('Withdraw', Icons.undo, (c, i) async {
            final ok = await AppDialogs.confirm(c, title: 'Withdraw correction?', message: '${i['employee_name']} · ${Fmt.date(i['work_date'])}', danger: true);
            if (!ok || !c.mounted) return false;
            final r = await AttendanceService.correctionCancel(i['id'] as int);
            if (c.mounted) Toast.result(c, r, success: 'Correction withdrawn.');
            return r.ok;
          }, visible: (i) => i['status'] == 'PENDING'),
        ],
      ),
    );
  }
}
