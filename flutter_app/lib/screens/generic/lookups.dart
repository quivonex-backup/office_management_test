import '../../api/api_response.dart';
import '../../services/other_services/accounts_service.dart';
import '../../services/other_services/assets_service.dart';
import '../../services/other_services/business_service.dart';
import '../../services/other_services/attendance_service.dart';
import '../../services/other_services/employees_service.dart';
import '../../services/other_services/helpdesk_service.dart';
import '../../services/other_services/leave_service.dart';
import '../../services/other_services/location_service.dart';
import '../../utils/helpers.dart';
import '../../widgets/forms/opt.dart';

/// Dropdown option loaders for forms and filters.
class Lookups {
  Lookups._();

  static Future<List<Opt>> _from(Future<ApiResult<dynamic>> f, String Function(Map<String, dynamic>) label, {bool Function(Map<String, dynamic>)? where}) async {
    final r = await f;
    final list = asMapList(r.data);
    return [
      for (final m in list)
        if (m['id'] != null && (where == null || where(m))) Opt(m['id'], label(m)),
    ];
  }

  static Future<List<Opt>> branches() => _from(AccountsService.branchList(isActive: true), (m) => '${m['name']}');
  static Future<List<Opt>> departments() => _from(EmployeesService.departmentList(isActive: true), (m) => '${m['name']}');
  static Future<List<Opt>> designations() => _from(EmployeesService.designationList(isActive: true), (m) => '${m['name']}');
  static Future<List<Opt>> accessRoles() => _from(AccountsService.accessRoleList(isActive: true), (m) => '${m['name']}');
  static Future<List<Opt>> employees() => _from(EmployeesService.list(), (m) => '${m['employee_code'] ?? ''} — ${m['full_name'] ?? ''}');
  static Future<List<Opt>> shifts() => _from(AttendanceService.shiftList(isActive: true), (m) => '${m['name']}');
  static Future<List<Opt>> leaveTypes() => _from(LeaveService.typeList(), (m) => '${m['name']}', where: (m) => m['is_active'] != false);
  static Future<List<Opt>> clients() => _from(BusinessService.clientList(), (m) => '${m['client_name']}', where: (m) => m['is_active'] != false);
  static Future<List<Opt>> vendors() => _from(BusinessService.vendorList(), (m) => '${m['vendor_name']}', where: (m) => m['is_active'] != false);
  static Future<List<Opt>> projects() => _from(BusinessService.projectList(), (m) => '${m['project_name']}');
  static Future<List<Opt>> ticketCategories() => _from(HelpdeskService.categoryOptions(), (m) => '${m['name']}');
  static Future<List<Opt>> assetCategories() => _from(AssetsService.categoryList(), (m) => '${m['name']}', where: (m) => m['is_active'] != false);
  static Future<List<Opt>> states() async {
    final list = await LocationService.stateItems();
    return [for (final m in list) Opt(m['id'], '${m['state_name']}')];
  }

  static List<Opt> strings(List<String> values, {bool pretty = true}) =>
      [for (final v in values) Opt(v, pretty ? Fmt.label(v) : v)];

  static List<Opt> weekDays() => const [
        Opt(0, 'Monday'), Opt(1, 'Tuesday'), Opt(2, 'Wednesday'), Opt(3, 'Thursday'), Opt(4, 'Friday'), Opt(5, 'Saturday'), Opt(6, 'Sunday'),
      ];
}
