import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../services/other_services/reports_service.dart';
import '../../utils/helpers.dart';
import '../../utils/responsive_helper.dart';
import '../../widgets/cards/api_chart.dart';
import '../../widgets/cards/stat_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/navigation/app_scaffold.dart';

/// One call (reports/dashboard/) returns every widget this user may see; a widget the
/// server does not send is simply not drawn (same rule as the React dashboard).
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  Widget _grid(List<Widget> kids) => LayoutBuilder(
        builder: (context, box) => GridView.count(
          crossAxisCount: Responsive.columns(box.maxWidth, mobile: 2, tablet: 3, desktop: 4),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          childAspectRatio: box.maxWidth < 420 ? 1.9 : 2.4,
          children: kids,
        ),
      );

  Widget _section(BuildContext c, String title, Widget child) => Padding(
        padding: const EdgeInsets.only(top: 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(title, style: Theme.of(c).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
          child,
        ]),
      );

  String _n(dynamic v) => v == null ? '0' : Fmt.number(v);

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    void go(String path) => context.go(path);

    return AppScaffold(
      title: 'Dashboard',
      body: ApiBuilder(
        load: () => ReportsService.dashboard(),
        builder: (ctx, r, reload) {
          final d = asMap(r.data);
          final w = asMap(d['widgets']);
          final kids = <Widget>[];

          final my = w['my_today'] is Map ? asMap(w['my_today']) : null;
          if (my != null) {
            final shift = my['shift'] is Map ? asMap(my['shift']) : null;
            kids.add(_section(
              ctx,
              'My day',
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [Expanded(child: Text(Fmt.date(my['date']), style: const TextStyle(fontWeight: FontWeight.w600))), StatusBadge(my['status'] as String?)]),
                    const SizedBox(height: 6),
                    if (shift != null) Text('Shift: ${shift['name']}  ${Fmt.time(shift['start'])} – ${Fmt.time(shift['end'])}'),
                    Text('Check in: ${my['check_in'] == null ? '—' : Fmt.time(my['check_in'])}    Check out: ${my['check_out'] == null ? '—' : Fmt.time(my['check_out'])}'),
                  ]),
                ),
              ),
            ));
          }

          final org = w['org_today'] is Map ? asMap(w['org_today']) : (w['team_today'] is Map ? asMap(w['team_today']) : null);
          if (org != null) {
            kids.add(_section(ctx, w['org_today'] is Map ? 'Today · everyone' : 'Today · my team', _grid([
              StatCard(label: 'Present', value: _n(org['present']), icon: Icons.check_circle_outline, color: Colors.green, onTap: () => go('/attendance')),
              StatCard(label: 'Late', value: _n(org['late']), icon: Icons.schedule, color: Colors.orange),
              StatCard(label: 'On leave', value: _n(org['on_leave']), icon: Icons.beach_access_outlined, color: Colors.blue),
              StatCard(label: 'Absent', value: _n(org['absent']), icon: Icons.person_off_outlined, color: Colors.red),
            ])));
          }

          final tiles = <Widget>[];
          final hc = w['headcount'] is Map ? asMap(w['headcount']) : null;
          if (hc != null) tiles.add(StatCard(label: 'Employees', value: _n(hc['total']), icon: Icons.people_outline, onTap: () => go('/employees')));
          final ap = w['pending_approvals'] is Map ? asMap(w['pending_approvals']) : null;
          if (ap != null) {
            final lv = asMap(ap['leave'])['count'];
            final co = asMap(ap['attendance_corrections'])['count'];
            if (lv != null) tiles.add(StatCard(label: 'Leave to approve', value: _n(lv), icon: Icons.beach_access_outlined, color: Colors.orange, onTap: () => go('/leave/applications')));
            if (co != null) tiles.add(StatCard(label: 'Corrections to approve', value: _n(co), icon: Icons.history_edu_outlined, color: Colors.orange, onTap: () => go('/attendance/corrections')));
          }
          final hd = w['helpdesk'] is Map ? asMap(w['helpdesk']) : null;
          if (hd != null) tiles.add(StatCard(label: 'Open tickets (${_n(hd['unassigned'])} unassigned)', value: _n(hd['open']), icon: Icons.support_agent_outlined, onTap: () => go('/helpdesk/queue')));
          final vi = w['visitors_today'] is Map ? asMap(w['visitors_today']) : null;
          if (vi != null) tiles.add(StatCard(label: 'Visitors inside (of ${_n(vi['total'])})', value: _n(vi['inside']), icon: Icons.door_front_door_outlined, onTap: () => go('/visitors')));
          final pr = w['projects'] is Map ? asMap(w['projects']) : null;
          if (pr != null) {
            tiles.add(StatCard(label: 'Open tasks', value: _n(pr['open_tasks']), icon: Icons.checklist_outlined, onTap: () => go('/projects/tasks')));
            tiles.add(StatCard(label: 'Overdue tasks', value: _n(pr['overdue_tasks']), icon: Icons.warning_amber_outlined, color: Colors.red));
          }
          final rc = w['receivables'] is Map ? asMap(w['receivables']) : null;
          if (rc != null) {
            tiles.add(StatCard(label: 'Outstanding', value: Fmt.money(rc['outstanding']), icon: Icons.account_balance_wallet_outlined, onTap: () => go('/payments')));
            tiles.add(StatCard(label: 'Overdue', value: Fmt.money(rc['overdue']), icon: Icons.error_outline, color: Colors.red));
          }
          final ex = w['expenses'] is Map ? asMap(w['expenses']) : null;
          if (ex != null) tiles.add(StatCard(label: 'Expenses this month', value: Fmt.money(ex['total']), icon: Icons.receipt_outlined, onTap: () => go('/expenses')));
          final ass = w['assets'] is Map ? asMap(w['assets']) : null;
          if (ass != null) tiles.add(StatCard(label: 'Assets', value: _n(ass['total']), icon: Icons.laptop_outlined, onTap: () => go('/assets')));
          final rec = w['recruitment_pipeline'] is Map ? asMap(w['recruitment_pipeline']) : null;
          if (rec != null) tiles.add(StatCard(label: 'Open applicants', value: _n(rec['open_applicants']), icon: Icons.contacts_outlined, onTap: () => go('/recruitment/applicants')));
          final pay = w['payroll_summary'] is Map ? asMap(w['payroll_summary']) : null;
          final last = pay != null && pay['last_run'] is Map ? asMap(pay['last_run']) : null;
          if (last != null) tiles.add(StatCard(label: 'Last payroll net', value: Fmt.money(last['net']), icon: Icons.currency_rupee, onTap: () => go('/payroll/runs')));
          if (tiles.isNotEmpty) kids.add(_section(ctx, 'Overview', _grid(tiles)));

          final trend = w['attendance_trend'] is Map ? asMap(w['attendance_trend']) : null;
          if (trend != null) kids.add(_section(ctx, 'Attendance trend', Card(child: Padding(padding: const EdgeInsets.all(12), child: ApiChart(chart: trend)))));
          final mm = w['my_month'] is Map ? asMap(w['my_month']) : null;
          if (mm != null) {
            kids.add(_section(ctx, 'My month', Card(child: Padding(padding: const EdgeInsets.all(14), child: Wrap(spacing: 16, runSpacing: 6, children: [
              Text('Present ${_n(mm['present'])}'), Text('Half days ${_n(mm['half_days'])}'), Text('Absent ${_n(mm['absent'])}'),
              Text('On leave ${_n(mm['on_leave'])}'), Text('Late days ${_n(mm['late_days'])}'),
            ])))));
          }

          final bal = asMapList(w['my_leave_balance']);
          if (bal.isNotEmpty) {
            kids.add(_section(ctx, 'My leave balance', Card(child: Column(children: [
              for (final b in bal) ListTile(dense: true, title: Text('${b['leave_type']}'), subtitle: Text('Allocated ${_n(b['allocated'])} · Used ${_n(b['used'])} · Pending ${_n(b['pending'])}'), trailing: Text('${_n(b['available'])} left', style: const TextStyle(fontWeight: FontWeight.w700))),
            ]))));
          }

          final hol = asMapList(w['upcoming_holidays']);
          if (hol.isNotEmpty) {
            kids.add(_section(ctx, 'Upcoming holidays', Card(child: Column(children: [
              for (final h in hol.take(5)) ListTile(dense: true, leading: const Icon(Icons.celebration_outlined), title: Text('${h['name']}'), trailing: Text(Fmt.date(h['date']))),
            ]))));
          }

          final ann = asMapList(w['announcements']);
          if (ann.isNotEmpty) {
            kids.add(_section(ctx, 'Announcements', Card(child: Column(children: [
              for (final a in ann.take(5))
                ListTile(dense: true, leading: Icon(a['is_pinned'] == true ? Icons.push_pin_outlined : Icons.campaign_outlined), title: Text('${a['title']}'), trailing: StatusBadge(a['priority'] as String?), onTap: () => go('/announcements')),
            ]))));
          }

          final cel = w['celebrations'] is Map ? asMap(w['celebrations']) : null;
          if (cel != null) {
            final b = asMapList(cel['birthdays']);
            final an = asMapList(cel['anniversaries']);
            if (b.isNotEmpty || an.isNotEmpty) {
              kids.add(_section(ctx, 'Celebrations today', Card(child: Column(children: [
                for (final p in b) ListTile(dense: true, leading: const Text('🎂', style: TextStyle(fontSize: 20)), title: Text('${p['name']}'), subtitle: Text('${p['department'] ?? ''}')),
                for (final p in an) ListTile(dense: true, leading: const Text('🎉', style: TextStyle(fontSize: 20)), title: Text('${p['name']}'), subtitle: Text('${p['years'] ?? ''} year(s)')),
              ]))));
            }
          }

          if (kids.isEmpty) {
            kids.add(const Padding(padding: EdgeInsets.only(top: 60), child: Center(child: Text('Nothing to show on your dashboard yet.'))));
          }

          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.all(12), children: [
              Text('Hello, ${auth.profile?.firstName.isNotEmpty == true ? auth.profile!.firstName : auth.profile?.username ?? ''}', style: Theme.of(ctx).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
              Text(Fmt.date(d['generated_at']), style: Theme.of(ctx).textTheme.bodySmall),
              ...kids,
            ]),
          );
        },
      ),
    );
  }
}
