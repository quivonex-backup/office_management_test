import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../constants/app_colors.dart';
import '../../constants/app_menu.dart';
import '../../providers/auth_provider.dart';
import '../../services/other_services/business_service.dart';
import '../../services/other_services/reports_service.dart';
import '../../utils/helpers.dart';
import '../../utils/responsive_helper.dart';
import '../../widgets/cards/api_chart.dart';
import '../../widgets/cards/gradient_stat_card.dart';
import '../../widgets/cards/stat_card.dart';
import '../../widgets/common/api_builder.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/navigation/app_scaffold.dart';

/// One call (reports/dashboard/) returns every widget this user may see; a widget the
/// server does not send is simply not drawn (same rule as the React dashboard).
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  String _n(dynamic v) => v == null ? '0' : Fmt.number(v);

  String _greeting() {
    final h = DateTime.now().hour;
    return h < 12 ? 'Good Morning' : (h < 17 ? 'Good Afternoon' : 'Good Evening');
  }

  Widget _title(BuildContext c, String t, {String? action, VoidCallback? onAction, IconData? icon}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          if (icon != null)
            Container(
              padding: const EdgeInsets.all(8),
              margin: const EdgeInsets.only(right: 10),
              decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, size: 20, color: Theme.of(c).colorScheme.primary),
            ),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
          if (action != null)
            InkWell(
              onTap: onAction,
              child: Text(action, style: TextStyle(color: Theme.of(c).colorScheme.primary, fontWeight: FontWeight.w600, fontSize: 13)),
            ),
        ]),
      );

  Widget _section(BuildContext c, String title, Widget child) => Padding(
        padding: const EdgeInsets.only(top: 22),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [_title(c, title), child]),
      );

  Widget _grid(List<Widget> kids, {double extent = 96, int mobile = 2, int tablet = 3, int desktop = 4}) => LayoutBuilder(
        builder: (context, box) => GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: kids.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: Responsive.columns(box.maxWidth, mobile: mobile, tablet: tablet, desktop: desktop),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            mainAxisExtent: extent,
          ),
          itemBuilder: (_, i) => kids[i],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scheme = Theme.of(context).colorScheme;
    void go(String path) => context.go(path);
    final p = auth.profile;
    final name = (p?.firstName.isNotEmpty ?? false) ? p!.firstName : (p?.username ?? '');

    return AppScaffold(
      title: 'Dashboard',
      hideTitleBar: true,
      body: ApiBuilder(
        load: () => ReportsService.dashboard(),
        builder: (ctx, r, reload) {
          final d = asMap(r.data);
          final w = asMap(d['widgets']);
          final kids = <Widget>[];

          // ---- greeting
          kids.add(Container(
            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 20),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              gradient: const LinearGradient(colors: [Color(0xFFEFE9FF), Color(0xFFF7F3FF)]),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${_greeting()}, $name 👋', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                  const SizedBox(height: 4),
                  const Text("Here is what's happening with your office today.", style: TextStyle(color: AppColors.textMuted, fontSize: 13.5)),
                ]),
              ),
              Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  gradient: const LinearGradient(colors: [Color(0xFFA78BFA), Color(0xFF7C3AED)], begin: Alignment.topLeft, end: Alignment.bottomRight),
                ),
                child: const Icon(Icons.auto_graph, color: Colors.white),
              ),
            ]),
          ));

          // ---- gradient stat cards (real numbers from the dashboard API)
          final cards = <Widget>[];
          final pr = w['projects'] is Map ? asMap(w['projects']) : null;
          if (pr != null) {
            final by = asMap(pr['by_status']);
            final total = by.values.fold<num>(0, (a, b) => a + (b is num ? b : 0));
            cards.add(GradientStatCard(label: 'Total Projects', value: _n(total), subtitle: '${_n(by['in_progress'])} in progress', subtitleIcon: Icons.folder_copy_outlined, colors: AppColors.gradRed, onTap: () => go('/projects')));
          }
          final hc = w['headcount'] is Map ? asMap(w['headcount']) : null;
          if (hc != null) {
            cards.add(GradientStatCard(label: 'Employees', value: _n(hc['total']), subtitle: '${_n(hc['joined_this_month'])} joined this month', subtitleIcon: Icons.groups_outlined, colors: AppColors.gradBlue, onTap: () => go('/employees')));
          }
          final ex = w['expenses'] is Map ? asMap(w['expenses']) : null;
          if (ex != null) {
            cards.add(GradientStatCard(label: 'Expenses (${ex['month'] ?? 'this month'})', value: Fmt.money(ex['total'], digits: 0), subtitle: 'This month', subtitleIcon: Icons.receipt_long_outlined, colors: AppColors.gradGreen, onTap: () => go('/expenses')));
            cards.add(GradientStatCard(label: 'Unpaid Expenses', value: Fmt.money(ex['unpaid'], digits: 0), subtitle: 'This month', subtitleIcon: Icons.hourglass_bottom, colors: AppColors.gradOrange, onTap: () => go('/expenses')));
          }
          if (cards.isNotEmpty) kids.add(Padding(padding: const EdgeInsets.only(top: 18), child: _grid(cards, extent: 124)));

          // ---- quick actions (only the ones this user may open)
          const actionDefs = [
            ('Add Expense', Icons.add_card_outlined, '/expenses', true),
            ('New Payment', Icons.credit_card_outlined, '/payments', true),
            ('View Reports', Icons.bar_chart_outlined, '/reports', false),
            ('New Employee', Icons.person_add_alt_1_outlined, '/employees', true),
            ('New Client', Icons.apartment_outlined, '/clients', true),
            ('New Project', Icons.folder_copy_outlined, '/projects', true),
            ('Team Allocation', Icons.groups_outlined, '/projects/team', false),
          ];
          final quick = <Widget>[];
          for (final a in actionDefs) {
            final it = findMenuItem(a.$3);
            if (it == null || (it.employeeOnly && !auth.hasEmployee) || !auth.canAny(it.anyOf)) continue;
            quick.add(Material(
              color: Theme.of(ctx).cardTheme.color,
              borderRadius: BorderRadius.circular(16),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => go(a.$4 ? '${a.$3}?new=1' : a.$3),
                child: Ink(
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.border.withValues(alpha: 0.7))),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(12)),
                      child: Icon(a.$2, color: Colors.white, size: 20),
                    ),
                    const SizedBox(height: 8),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      child: Text(a.$1, textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w500)),
                    ),
                  ]),
                ),
              ),
            ));
          }
          if (quick.isNotEmpty) {
            kids.add(_section(ctx, 'Quick Actions', _grid(quick, extent: 96, mobile: 3, tablet: 4, desktop: quick.length.clamp(1, 7).toInt())));
          }

          // ---- ongoing projects + recent expenses (real lists)
          final left = pr != null ? _OngoingProjects(onAll: () => go('/projects')) : null;
          final right = ex != null ? _RecentExpenses(onAll: () => go('/expenses')) : null;
          if (left != null || right != null) {
            kids.add(Padding(
              padding: const EdgeInsets.only(top: 22),
              child: LayoutBuilder(builder: (context, box) {
                final wide = box.maxWidth >= 860 && left != null && right != null;
                if (wide) {
                  return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(flex: 6, child: left),
                    const SizedBox(width: 16),
                    Expanded(flex: 5, child: right),
                  ]);
                }
                return Column(children: [if (left != null) left, if (left != null && right != null) const SizedBox(height: 18), if (right != null) right]);
              }),
            ));
          }

          // ---- the other dashboard widgets (same data as before, new look)
          final my = w['my_today'] is Map ? asMap(w['my_today']) : null;
          if (my != null) {
            final shift = my['shift'] is Map ? asMap(my['shift']) : null;
            kids.add(_section(
              ctx,
              'My day',
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
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
            ], extent: 78)));
          }

          final tiles = <Widget>[];
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
          if (pr != null) {
            tiles.add(StatCard(label: 'Open tasks', value: _n(pr['open_tasks']), icon: Icons.checklist_outlined, onTap: () => go('/projects/tasks')));
            tiles.add(StatCard(label: 'Overdue tasks', value: _n(pr['overdue_tasks']), icon: Icons.warning_amber_outlined, color: Colors.red));
          }
          final rc = w['receivables'] is Map ? asMap(w['receivables']) : null;
          if (rc != null) {
            tiles.add(StatCard(label: 'Outstanding', value: Fmt.money(rc['outstanding']), icon: Icons.account_balance_wallet_outlined, onTap: () => go('/payments')));
            tiles.add(StatCard(label: 'Overdue', value: Fmt.money(rc['overdue']), icon: Icons.error_outline, color: Colors.red));
          }
          final ass = w['assets'] is Map ? asMap(w['assets']) : null;
          if (ass != null) tiles.add(StatCard(label: 'Assets', value: _n(ass['total']), icon: Icons.laptop_outlined, onTap: () => go('/assets')));
          final rec = w['recruitment_pipeline'] is Map ? asMap(w['recruitment_pipeline']) : null;
          if (rec != null) tiles.add(StatCard(label: 'Open applicants', value: _n(rec['open_applicants']), icon: Icons.contacts_outlined, onTap: () => go('/recruitment/applicants')));
          final pay = w['payroll_summary'] is Map ? asMap(w['payroll_summary']) : null;
          final last = pay != null && pay['last_run'] is Map ? asMap(pay['last_run']) : null;
          if (last != null) tiles.add(StatCard(label: 'Last payroll net', value: Fmt.money(last['net']), icon: Icons.currency_rupee, onTap: () => go('/payroll/runs')));
          if (tiles.isNotEmpty) kids.add(_section(ctx, 'Overview', _grid(tiles, extent: 78)));

          final trend = w['attendance_trend'] is Map ? asMap(w['attendance_trend']) : null;
          if (trend != null) kids.add(_section(ctx, 'Attendance trend', Card(child: Padding(padding: const EdgeInsets.all(14), child: ApiChart(chart: trend)))));
          final mm = w['my_month'] is Map ? asMap(w['my_month']) : null;
          if (mm != null) {
            kids.add(_section(ctx, 'My month', Card(child: Padding(padding: const EdgeInsets.all(16), child: Wrap(spacing: 16, runSpacing: 6, children: [
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
                for (final x in b) ListTile(dense: true, leading: const Text('🎂', style: TextStyle(fontSize: 20)), title: Text('${x['name']}'), subtitle: Text('${x['department'] ?? ''}')),
                for (final x in an) ListTile(dense: true, leading: const Text('🎉', style: TextStyle(fontSize: 20)), title: Text('${x['name']}'), subtitle: Text('${x['years'] ?? ''} year(s)')),
              ]))));
            }
          }

          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(padding: const EdgeInsets.fromLTRB(20, 18, 20, 28), children: kids),
          );
        },
      ),
    );
  }
}

/// "Ongoing Projects": projects with status in_progress (real list, newest first).
class _OngoingProjects extends StatelessWidget {
  final VoidCallback onAll;
  const _OngoingProjects({required this.onAll});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(8),
            margin: const EdgeInsets.only(right: 10),
            decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(10)),
            child: Icon(Icons.rocket_launch_outlined, size: 20, color: scheme.primary),
          ),
          const Expanded(child: Text('Ongoing Projects', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
          InkWell(onTap: onAll, child: Text('See All', style: TextStyle(color: scheme.primary, fontWeight: FontWeight.w600, fontSize: 13))),
        ]),
      ),
      ApiBuilder(
        load: () => BusinessService.projectList({'status': 'in_progress'}),
        builder: (ctx, r, _) {
          final rows = asMapList(r.data).take(4).toList();
          if (rows.isEmpty) return const Card(child: Padding(padding: EdgeInsets.all(20), child: Center(child: Text('No ongoing projects.'))));
          return Column(children: [
            for (final p in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${p['project_name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                          const SizedBox(height: 2),
                          Text('${p['client_name'] ?? ''}', style: const TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
                          if (p['deadline'] != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text('Deadline: ${Fmt.date(p['deadline'])}', style: const TextStyle(fontSize: 12.5))),
                        ]),
                      ),
                      StatusBadge(p['status'] as String?),
                    ]),
                  ),
                ),
              ),
          ]);
        },
      ),
    ]);
  }
}

/// "Recent Expenses": latest 5 by expense date (real list).
class _RecentExpenses extends StatelessWidget {
  final VoidCallback onAll;
  const _RecentExpenses({required this.onAll});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(8),
            margin: const EdgeInsets.only(right: 10),
            decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(10)),
            child: Icon(Icons.receipt_long_outlined, size: 20, color: scheme.primary),
          ),
          const Expanded(child: Text('Recent Expenses', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
          InkWell(onTap: onAll, child: Text('See All', style: TextStyle(color: scheme.primary, fontWeight: FontWeight.w600, fontSize: 13))),
        ]),
      ),
      ApiBuilder(
        load: () => BusinessService.expenseList(),
        builder: (ctx, r, _) {
          final rows = List<Map<String, dynamic>>.of(asMapList(r.data))..sort((a, b) => '${b['expense_date']}'.compareTo('${a['expense_date']}'));
          final top = rows.take(5).toList();
          if (top.isEmpty) return const Card(child: Padding(padding: EdgeInsets.all(20), child: Center(child: Text('No expenses yet.'))));
          return Card(
            child: Column(children: [
              for (var i = 0; i < top.length; i++) ...[
                if (i > 0) const Divider(),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  child: Row(children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(color: AppColors.forStatus(top[i]['payment_status']?.toString()).withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
                      child: Icon(top[i]['payment_status'] == 'paid' ? Icons.check_circle_outline : Icons.schedule, color: AppColors.forStatus(top[i]['payment_status']?.toString())),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${top[i]['title']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text('${top[i]['expense_type_display'] ?? ''} · ${Fmt.date(top[i]['expense_date'])}', style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                      ]),
                    ),
                    Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Text(Fmt.money(top[i]['amount']), style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      StatusBadge((top[i]['payment_status'] as String?)?.toUpperCase()),
                    ]),
                  ]),
                ),
              ],
            ]),
          );
        },
      ),
    ]);
  }
}
