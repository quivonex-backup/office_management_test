import 'package:flutter/material.dart';

/// Drawer menu + route permissions. Same permission codes as React config/menu.ts.
/// An item is shown when the user has ANY code in [anyOf] (empty = everybody).
class MenuItem {
  final String label, path;
  final String? divider;
  final IconData icon;
  final List<String>? anyOf;
  final bool employeeOnly;
  const MenuItem(this.label, this.path, this.icon, {this.anyOf, this.divider, this.employeeOnly = false});
}

class MenuGroup {
  final String title, section;
  final IconData icon;
  final bool hidden;
  final List<MenuItem> items;
  const MenuGroup(this.title, this.icon, this.section, this.items, {this.hidden = false});
}

const _applicant = ['applicant.view', 'applicant.create', 'applicant.update', 'applicant.status_update', 'verification.update', 'onboarding.complete'];
const _payrollView = ['payroll.view_all', 'payroll.generate', 'payroll.finalize', 'salary.assign'];

const List<MenuGroup> appMenu = [
  MenuGroup('Home', Icons.home_outlined, 'Workspace', [
    MenuItem('Dashboard', '/dashboard', Icons.dashboard_outlined),
    MenuItem('Reports', '/reports', Icons.bar_chart_outlined),
    MenuItem('Announcements', '/announcements', Icons.campaign_outlined, divider: 'Updates'),
    MenuItem('Notifications', '/notifications', Icons.notifications_outlined),
  ]),
  MenuGroup('People', Icons.people_outline, 'Workspace', [
    MenuItem('Employees', '/employees', Icons.people_outline, anyOf: ['employee.view_all', 'employee.view_team', 'employee.update']),
    MenuItem('Applicants', '/recruitment/applicants', Icons.contacts_outlined, anyOf: _applicant, divider: 'Recruitment'),
  ]),
  MenuGroup('Attendance', Icons.event_available_outlined, 'Workspace', [
    MenuItem('Attendance', '/attendance', Icons.event_available_outlined, anyOf: ['attendance.view_all', 'attendance.view_team']),
    MenuItem('Corrections', '/attendance/corrections', Icons.history_edu_outlined, anyOf: ['attendance.view_all', 'attendance.view_team', 'attendance.approve_correction']),
    MenuItem('Shifts', '/shifts', Icons.schedule_outlined, anyOf: ['settings.manage'], divider: 'Setup'),
    MenuItem('Shift assignments', '/shift-assignments', Icons.date_range_outlined, anyOf: ['settings.manage']),
    MenuItem('Weekly offs', '/weekly-offs', Icons.event_busy_outlined, anyOf: ['calendar.manage', 'settings.manage', 'attendance.view_all', 'attendance.view_team']),
    MenuItem('Attendance devices', '/attendance-devices', Icons.tablet_android_outlined, anyOf: ['attendance.device_manage']),
    MenuItem('Attendance settings', '/attendance-settings', Icons.tune_outlined, anyOf: ['settings.manage']),
  ]),
  MenuGroup('Leave & holidays', Icons.beach_access_outlined, 'Workspace', [
    MenuItem('Leave applications', '/leave/applications', Icons.beach_access_outlined, anyOf: ['leave.view_all', 'leave.view_team', 'leave.approve']),
    MenuItem('Leave balances', '/leave/balances', Icons.account_balance_wallet_outlined, anyOf: ['leave.view_all', 'leave.view_team', 'settings.manage']),
    MenuItem('Leave history', '/leave/history', Icons.receipt_long_outlined, anyOf: ['leave.view_all', 'settings.manage']),
    MenuItem('My calendar', '/my-calendar', Icons.calendar_month_outlined, employeeOnly: true, divider: 'Calendar'),
    MenuItem('Holidays', '/holidays', Icons.celebration_outlined),
    MenuItem('Leave types', '/leave/types', Icons.verified_outlined, anyOf: ['settings.manage'], divider: 'Setup'),
  ]),
  MenuGroup('Payroll', Icons.currency_rupee, 'Business', [
    MenuItem('Pay runs', '/payroll/runs', Icons.play_circle_outline, anyOf: ['payroll.view_all', 'payroll.generate', 'payroll.finalize']),
    MenuItem('Payments', '/payroll/payments', Icons.payments_outlined, anyOf: ['payroll.view_all', 'payroll.generate', 'payroll.finalize']),
    MenuItem('Salary assignments', '/payroll/assignments', Icons.manage_accounts_outlined, anyOf: ['salary.assign', 'payroll.view_all'], divider: 'Salary'),
    MenuItem('Salary structures', '/payroll/structures', Icons.layers_outlined, anyOf: ['salary.assign', 'payroll.generate']),
    MenuItem('Payroll settings', '/payroll/settings', Icons.tune_outlined, anyOf: ['settings.manage', 'payroll.generate'], divider: 'Setup'),
  ]),
  MenuGroup('Projects', Icons.work_outline, 'Business', [
    MenuItem('Projects', '/projects', Icons.work_outline),
    MenuItem('Tasks', '/projects/tasks', Icons.checklist_outlined),
    MenuItem('Team allocation', '/projects/team', Icons.groups_outlined, anyOf: ['project.manage']),
    MenuItem('Project chat', '/project-chat', Icons.forum_outlined),
    MenuItem('Clients', '/clients', Icons.business_outlined, anyOf: ['client.manage'], divider: 'Billing'),
    MenuItem('Project payments', '/payments', Icons.currency_rupee, anyOf: ['payment.manage']),
    MenuItem('Invoices and reminders', '/payments/invoices', Icons.description_outlined, anyOf: ['payment.manage']),
  ]),
  MenuGroup('Expenses', Icons.receipt_outlined, 'Business', [
    MenuItem('Expenses', '/expenses', Icons.receipt_outlined, anyOf: ['expense.manage']),
    MenuItem('Recurring expenses', '/expenses/recurring', Icons.repeat, anyOf: ['expense.manage']),
    MenuItem('Vendors', '/vendors', Icons.local_shipping_outlined, anyOf: ['vendor.manage', 'expense.manage']),
    MenuItem('Reimbursements', '/expenses/reimbursements', Icons.request_quote_outlined, anyOf: ['reimbursement.review', 'reimbursement.pay'], divider: 'Staff claims'),
  ]),
  MenuGroup('Office', Icons.support_agent_outlined, 'Business', [
    MenuItem('My tickets', '/helpdesk/my', Icons.support_agent_outlined, employeeOnly: true, divider: 'Helpdesk'),
    MenuItem('Helpdesk queue', '/helpdesk/queue', Icons.inbox_outlined, anyOf: ['ticket.manage', 'ticket.handle']),
    MenuItem('Ticket categories', '/helpdesk/categories', Icons.sell_outlined, anyOf: ['ticket.manage']),
    MenuItem('Asset register', '/assets', Icons.laptop_outlined, anyOf: ['asset.view', 'asset.manage'], divider: 'Assets'),
    MenuItem('My assets', '/my-assets', Icons.laptop_mac_outlined, employeeOnly: true),
    MenuItem('Asset categories', '/assets/categories', Icons.category_outlined, anyOf: ['asset.manage']),
    MenuItem('Front desk', '/visitors', Icons.door_front_door_outlined, anyOf: ['visitor.manage'], divider: 'Visitors'),
    MenuItem('My visitors', '/my-visitors', Icons.how_to_reg_outlined, employeeOnly: true),
  ]),
  MenuGroup('Organization', Icons.apartment_outlined, 'Admin', [
    MenuItem('Organization', '/organization', Icons.apartment_outlined, anyOf: ['org.manage']),
    MenuItem('Branches', '/branches', Icons.account_tree_outlined, anyOf: ['org.manage']),
    MenuItem('Departments', '/departments', Icons.hub_outlined, anyOf: ['org.manage']),
    MenuItem('Designations', '/designations', Icons.badge_outlined, anyOf: ['org.manage']),
    MenuItem('Access roles', '/access-roles', Icons.shield_outlined, anyOf: ['access.manage'], divider: 'Access'),
  ]),
  MenuGroup('Account', Icons.account_circle_outlined, 'Admin', hidden: true, [
    MenuItem('My profile', '/profile', Icons.account_circle_outlined),
    MenuItem('Change password', '/change-password', Icons.key_outlined),
    MenuItem('Appearance', '/appearance', Icons.palette_outlined),
  ]),
];

/// Extra routes that are not in the menu but need a permission (React ROUTE_PERMISSIONS).
const Map<String, List<String>> extraRoutePermissions = {
  '/employees/new': ['employee.update'],
  '/employees/edit': ['employee.update'],
  '/payroll/runs/new': ['payroll.generate'],
  '/recruitment/applicants/new': ['applicant.create'],
};

MenuItem? findMenuItem(String path) {
  for (final g in appMenu) {
    for (final i in g.items) {
      if (i.path == path) return i;
    }
  }
  return null;
}
