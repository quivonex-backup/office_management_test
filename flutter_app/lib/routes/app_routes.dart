import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../constants/app_menu.dart';
import '../constants/app_strings.dart';
import '../providers/auth_provider.dart';
import '../screens/assets/asset_screens.dart';
import '../screens/attendance/attendance_screens.dart';
import '../screens/business/business_screens.dart';
import '../screens/communications/communications_screens.dart';
import '../screens/dashboard/dashboard_screen.dart';
import '../screens/employees/employee_screens.dart';
import '../screens/helpdesk/helpdesk_screens.dart';
import '../screens/leave/leave_screens.dart';
import '../screens/organization/organization_screens.dart';
import '../screens/other/recruitment_screens.dart';
import '../screens/payroll/payroll_screens.dart';
import '../screens/reports/report_screens.dart';
import '../screens/settings/appearance_screen.dart';
import '../screens/settings/change_password_screen.dart';
import '../screens/settings/profile_screen.dart';
import '../screens/visitors/visitor_screens.dart';
import '../widgets/navigation/app_scaffold.dart';

/// Route paths = the React paths. Every page is wrapped in [RouteGuard], which applies the same
/// permission rule as the drawer (menu `anyOf` / `employeeOnly`, plus [extraRoutePermissions]).
class AppRoutes {
  AppRoutes._();

  static const home = '/dashboard';

  static final Map<String, WidgetBuilder> _pages = {
    '/dashboard': (_) => const DashboardScreen(),
    '/reports': (_) => const ReportHubScreen(),
    '/announcements': (_) => const AnnouncementsScreen(),
    '/notifications': (_) => const NotificationsScreen(),
    '/employees': (_) => const EmployeeListScreen(),
    '/recruitment/applicants': (_) => const ApplicantsScreen(),
    '/attendance': (_) => const AttendanceRegisterScreen(),
    '/attendance/corrections': (_) => const CorrectionsScreen(),
    '/shifts': (_) => const ShiftsScreen(),
    '/shift-assignments': (_) => const ShiftAssignmentsScreen(),
    '/weekly-offs': (_) => const WeeklyOffsScreen(),
    '/attendance-devices': (_) => const AttendanceDevicesScreen(),
    '/attendance-settings': (_) => const AttendanceSettingsScreen(),
    '/leave/applications': (_) => const LeaveApplicationsScreen(),
    '/leave/balances': (_) => const LeaveBalancesScreen(),
    '/leave/history': (_) => const LeaveHistoryScreen(),
    '/my-calendar': (_) => const MyCalendarScreen(),
    '/holidays': (_) => const HolidaysScreen(),
    '/leave/types': (_) => const LeaveTypesScreen(),
    '/payroll/runs': (_) => const PayrollRunsScreen(),
    '/payroll/payments': (_) => const PayrollPaymentsScreen(),
    '/payroll/assignments': (_) => const SalaryAssignmentsScreen(),
    '/payroll/structures': (_) => const SalaryStructuresScreen(),
    '/payroll/settings': (_) => const PayrollSettingsScreen(),
    '/projects': (_) => const ProjectsScreen(),
    '/projects/tasks': (_) => const TasksScreen(),
    '/projects/team': (_) => const TeamAllocationScreen(),
    '/project-chat': (_) => const ProjectChatScreen(),
    '/clients': (_) => const ClientsScreen(),
    '/payments': (_) => const ProjectPaymentsScreen(),
    '/payments/invoices': (_) => const InvoicesScreen(),
    '/expenses': (_) => const ExpensesScreen(),
    '/expenses/recurring': (_) => const RecurringExpensesScreen(),
    '/vendors': (_) => const VendorsScreen(),
    '/expenses/reimbursements': (_) => const ReimbursementsScreen(),
    '/helpdesk/my': (_) => const MyTicketsScreen(),
    '/helpdesk/queue': (_) => const HelpdeskQueueScreen(),
    '/helpdesk/categories': (_) => const TicketCategoriesScreen(),
    '/assets': (_) => const AssetsScreen(),
    '/my-assets': (_) => const MyAssetsScreen(),
    '/assets/categories': (_) => const AssetCategoriesScreen(),
    '/visitors': (_) => const FrontDeskScreen(),
    '/my-visitors': (_) => const MyVisitorsScreen(),
    '/organization': (_) => const OrganizationScreen(),
    '/branches': (_) => const BranchesScreen(),
    '/departments': (_) => const DepartmentsScreen(),
    '/designations': (_) => const DesignationsScreen(),
    '/access-roles': (_) => const AccessRolesScreen(),
    '/profile': (_) => const ProfileScreen(),
    '/change-password': (_) => const ChangePasswordScreen(),
    '/appearance': (_) => const AppearanceScreen(),
  };

  static const login = '/login';
  static const forgotPassword = '/forgot-password';
  static const selectOrganization = '/select-organization';
  static const noAccess = '/no-access';
  static const splash = '/splash';

  /// Signed-in pages: path -> screen.
  static Map<String, WidgetBuilder> get pages => _pages;
}

class RouteGuard extends StatelessWidget {
  final String path;
  final Widget child;
  const RouteGuard({super.key, required this.path, required this.child});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final item = findMenuItem(path);
    final extra = extraRoutePermissions[path];
    final allowed = (item == null || ((!item.employeeOnly || auth.hasEmployee) && auth.canAny(item.anyOf))) && (extra == null || auth.canAny(extra));
    if (allowed) return child;
    return const AppScaffold(
      title: 'No access',
      body: Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.lock_outline, size: 48),
            SizedBox(height: 12),
            Text(AppStrings.forbidden, textAlign: TextAlign.center),
          ]),
        ),
      ),
    );
  }
}
