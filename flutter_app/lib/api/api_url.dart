import '../config/app_config.dart';

/// ONE place for the server address and every endpoint path (ported 1:1 from
/// the React project's src/config/api.ts). Every endpoint in this backend is POST.
class ApiUrls {
  ApiUrls._();

  /// Backend root WITH a trailing slash. Change for your deployment.
  /// (Android emulator reaching a PC's localhost: http://10.0.2.2:8000/)
  static const String baseUrl = AppConfig.apiBaseUrl;

  /// Prefix for relative file paths such as "users/profile/abc.jpg" (S3/CDN).
  /// Values that already start with http(s):// are used as they are.
  static const String mediaBaseUrl = '';

  /// Paths that must NOT get "organization_id" in the body.
  static const List<String> noOrgIdPrefixes = [
    'accounts/login/',
    'accounts/refresh-token/',
    'accounts/send-otp/',
    'accounts/verify-otp/',
    'accounts/forgot-password/',
    'accounts/change-password/',
    'accounts/my-profile/update/',
    'accounts/organization/my-organizations/',
    'location_master/',
  ];

  /// Paths that never get a Bearer token and never trigger a refresh.
  static const List<String> publicPaths = [
    'accounts/login/',
    'accounts/refresh-token/',
    'accounts/send-otp/',
    'accounts/verify-otp/',
    'accounts/forgot-password/',
  ];

  // ---- accounts: auth
  static const login = 'accounts/login/';
  static const refresh = 'accounts/refresh-token/';
  static const sendOtp = 'accounts/send-otp/';
  static const verifyOtp = 'accounts/verify-otp/';
  static const forgotPassword = 'accounts/forgot-password/';
  static const changePassword = 'accounts/change-password/';
  static const myProfile = 'accounts/my-profile/';
  static const myProfileUpdate = 'accounts/my-profile/update/';
  // ---- accounts: organization
  static const myOrganizations = 'accounts/organization/my-organizations/';
  static const organizationUpdate = 'accounts/organization/update/';
  // ---- accounts: branches
  static const branchList = 'accounts/branch/list/';
  static const branchCreate = 'accounts/branch/create/';
  static const branchUpdate = 'accounts/branch/update/';
  static const branchDeactivate = 'accounts/branch/deactivate/';
  // ---- accounts: access roles
  static const permissionList = 'accounts/permission/list/';
  static const accessRoleList = 'accounts/access-role/list/';
  static const accessRoleCreate = 'accounts/access-role/create/';
  static const accessRoleUpdate = 'accounts/access-role/update/';
  static const accessRoleDeactivate = 'accounts/access-role/deactivate/';
  // ---- employees
  static const employeeList = 'employees/list/';
  static const employeeDetail = 'employees/detail/';
  static const employeeCreate = 'employees/create/';
  static const employeeUpdate = 'employees/update/';
  static const employeeMyProfile = 'employees/my-profile/';
  static const employeeCreateUser = 'employees/create-user/';
  static const employeeDeactivate = 'employees/deactivate/';
  static const employeeReactivate = 'employees/reactivate/';
  static const employeeDocUpload = 'employees/document/upload/';
  static const employeeDocDelete = 'employees/document/delete/';
  static const departmentList = 'employees/department/list/';
  static const departmentCreate = 'employees/department/create/';
  static const departmentUpdate = 'employees/department/update/';
  static const departmentDeactivate = 'employees/department/deactivate/';
  static const designationList = 'employees/designation/list/';
  static const designationCreate = 'employees/designation/create/';
  static const designationUpdate = 'employees/designation/update/';
  static const designationDeactivate = 'employees/designation/deactivate/';
  // ---- attendance
  static const attSettings = 'attendance/settings/';
  static const deviceList = 'attendance/device/list/';
  static const deviceCreate = 'attendance/device/create/';
  static const deviceUpdate = 'attendance/device/update/';
  static const deviceResetPassword = 'attendance/device/reset-password/';
  static const deviceDeactivate = 'attendance/device/deactivate/';
  static const shiftList = 'attendance/shifts/list/';
  static const shiftCreate = 'attendance/shifts/create/';
  static const shiftUpdate = 'attendance/shifts/update/';
  static const shiftDeactivate = 'attendance/shifts/deactivate/';
  static const assignList = 'attendance/shift-assignments/list/';
  static const assignCreate = 'attendance/shift-assignments/create/';
  static const assignUpdate = 'attendance/shift-assignments/update/';
  static const assignBulk = 'attendance/shift-assignments/bulk-assign/';
  static const assignPattern = 'attendance/shift-assignments/bulk-assign-pattern/';
  static const assignBulkClose = 'attendance/shift-assignments/bulk-close/';
  static const attList = 'attendance/list/';
  static const attBulkAbsent = 'attendance/bulk-mark-absent/';
  static const correctionList = 'attendance/corrections/list/';
  static const correctionReview = 'attendance/corrections/review/';
  static const correctionMissedDay = 'attendance/corrections/missed-day/';
  static const correctionCancel = 'attendance/corrections/cancel/';
  // ---- leave
  static const leaveTypeList = 'leave/types/list/';
  static const leaveTypeCreate = 'leave/types/create/';
  static const leaveTypeUpdate = 'leave/types/update/';
  static const leaveTypeDeactivate = 'leave/types/deactivate/';
  static const leaveBalanceList = 'leave/balances/list/';
  static const leaveBalanceInit = 'leave/balances/initialize/';
  static const leaveBalanceCarry = 'leave/balances/carry-forward/';
  static const leaveBalanceAdjust = 'leave/balances/adjust/';
  static const leaveAppList = 'leave/applications/list/';
  static const leaveAppReview = 'leave/applications/review/';
  static const leaveAppCancel = 'leave/applications/cancel/organization/';
  static const leaveTxnList = 'leave/transactions/list/';
  // ---- calendar
  static const weeklyOffList = 'calendar/weekly-offs/list/';
  static const weeklyOffCreate = 'calendar/weekly-offs/create/';
  static const weeklyOffBulkCreate = 'calendar/weekly-offs/bulk-create/';
  static const weeklyOffUpdate = 'calendar/weekly-offs/update/';
  static const weeklyOffDeactivate = 'calendar/weekly-offs/deactivate/';
  static const calendarEmployee = 'calendar/employee/';
  static const holidayList = 'calendar/holidays/list/';
  static const holidayCreate = 'calendar/holidays/create/';
  static const holidayUpdate = 'calendar/holidays/update/';
  static const holidayDeactivate = 'calendar/holidays/deactivate/';
  static const holidayImport = 'calendar/holidays/bulk-import/';
  // ---- payroll + reports
  static const payrollSettings = 'payroll/settings/';
  static const dashboard = 'reports/dashboard/';
  static const reportList = 'reports/list/';
  static const reportBase = 'reports/'; // + key + '/'
  static const payrollStatutory = 'payroll/statutory-settings/';
  static const componentList = 'payroll/components/list/';
  static const componentCreate = 'payroll/components/create/';
  static const componentDetail = 'payroll/components/detail/';
  static const componentUpdate = 'payroll/components/update/';
  static const componentDeactivate = 'payroll/components/deactivate/';
  static const structureList = 'payroll/structures/list/';
  static const structureCreate = 'payroll/structures/create/';
  static const structureUpdate = 'payroll/structures/update/';
  static const structureDeactivate = 'payroll/structures/deactivate/';
  static const salaryAssignList = 'payroll/assignments/list/';
  static const salaryAssignCreate = 'payroll/assignments/create/';
  static const salaryAssignUpdate = 'payroll/assignments/update/';
  static const salaryAssignBulk = 'payroll/assignments/bulk-assign/';
  static const salaryAssignBulkClose = 'payroll/assignments/bulk-close/';
  static const runPreview = 'payroll/runs/preview/';
  static const runCreate = 'payroll/runs/create/';
  static const runList = 'payroll/runs/list/';
  static const runDetail = 'payroll/runs/detail/';
  static const runGenerate = 'payroll/runs/generate/';
  static const runFinalize = 'payroll/runs/finalize/';
  static const runReopen = 'payroll/runs/reopen/';
  static const recordList = 'payroll/records/list/';
  static const recordUpdate = 'payroll/records/update-deductions/';
  static const paymentRecord = 'payroll/payments/record/';
  static const paymentBulk = 'payroll/payments/bulk-record/';
  static const paymentList = 'payroll/payments/list/';
  static const paymentVoid = 'payroll/payments/void/';
  static const payslipDownload = 'payroll/payslips/download/';
  static const payrollCalculator = 'payroll/calculator/';
  // ---- recruitment
  static const applicantCreate = 'recruitment/applicant/create/';
  static const applicantList = 'recruitment/applicant/list/';
  static const applicantDetail = 'recruitment/applicant/detail/';
  static const applicantUpdate = 'recruitment/applicant/update/';
  static const applicantStatus = 'recruitment/applicant/status-update/';
  static const applicantVerification = 'recruitment/applicant/verification/';
  static const applicantOnboarding = 'recruitment/applicant/onboarding/';
  static const applicantConvert = 'recruitment/applicant/convert/';
  static const offerLetterDownload = 'recruitment/applicant/offer-letter/download/';
  // ---- clients, vendors
  static const clientCreate = 'clients/create/';
  static const clientList = 'clients/list/';
  static const clientDetail = 'clients/detail/';
  static const clientUpdate = 'clients/update/';
  static const clientDeactivate = 'clients/deactivate/';
  static const vendorCreate = 'vendors/create/';
  static const vendorList = 'vendors/list/';
  static const vendorDetail = 'vendors/detail/';
  static const vendorUpdate = 'vendors/update/';
  static const vendorDeactivate = 'vendors/deactivate/';
  // ---- projects
  static const projectCreate = 'projects/create/';
  static const projectList = 'projects/list/';
  static const projectDetail = 'projects/detail/';
  static const projectUpdate = 'projects/update/';
  static const projectDeactivate = 'projects/deactivate/';
  static const teamCreate = 'projects/team-allocation/create/';
  static const teamList = 'projects/team-allocation/list/';
  static const teamDetail = 'projects/team-allocation/detail/';
  static const teamUpdate = 'projects/team-allocation/update/';
  static const teamDeactivate = 'projects/team-allocation/deactivate/';
  static const projectTeam = 'projects/team-allocation/project-team/';
  static const employeeProjects = 'projects/team-allocation/employee-projects/';
  static const assignHead = 'projects/team-allocation/assign-head/';
  static const myProjects = 'projects/my-projects/';
  static const myProjectsHead = 'projects/my-projects-as-head/';
  static const myProjectDetail = 'projects/my-project-detail/';
  static const myTasks = 'projects/task/my-tasks/';
  static const taskCreate = 'projects/task/create/';
  static const taskList = 'projects/task/list/';
  static const taskDetail = 'projects/task/detail/';
  static const taskUpdate = 'projects/task/update/';
  static const taskStatus = 'projects/task/status-update/';
  static const taskDeactivate = 'projects/task/deactivate/';
  // ---- expenses
  static const expenseCreate = 'expenses/create/';
  static const expenseList = 'expenses/list/';
  static const expenseDetail = 'expenses/detail/';
  static const expenseUpdate = 'expenses/update/';
  static const expenseDeactivate = 'expenses/deactivate/';
  static const recurringCreate = 'expenses/recurring/create/';
  static const recurringList = 'expenses/recurring/list/';
  static const recurringDetail = 'expenses/recurring/detail/';
  static const recurringUpdate = 'expenses/recurring/update/';
  static const recurringDeactivate = 'expenses/recurring/deactivate/';
  static const entryCreate = 'expenses/recurring/entries/create/';
  static const entryUpdate = 'expenses/recurring/entries/update/';
  static const entryDeactivate = 'expenses/recurring/entries/deactivate/';
  static const reimbList = 'expenses/reimbursements/list/';
  static const reimbDetail = 'expenses/reimbursements/detail/';
  static const reimbReview = 'expenses/reimbursements/review/';
  static const reimbPay = 'expenses/reimbursements/mark-paid/';
  // ---- project payments
  static const ppCreate = 'payments/project/payment-create/';
  static const ppList = 'payments/project/payment-list/';
  static const ppDetail = 'payments/project/payment-detail/';
  static const ppUpdate = 'payments/project/payment-update/';
  static const ppCancel = 'payments/project/payment-cancel/';
  static const txCreate = 'payments/project/transaction/create/';
  static const txUpdate = 'payments/project/transaction/update/';
  static const ppByProject = 'payments/project/payments-details-by-project/';
  static const ppReminder = 'payments/payment-reminder/';
  static const ppInvoice = 'payments/project-invoice/pdf-download/';
  // ---- communications
  static const notifList = 'communications/notifications/list/';
  static const notifRead = 'communications/notifications/mark-read/';
  static const notifReadAll = 'communications/notifications/mark-all-read/';
  static const notifCount = 'communications/notifications/unread-count/';
  static const notifDelete = 'communications/notifications/delete/';
  static const annCreate = 'communications/announcements/create/';
  static const annList = 'communications/announcements/list/';
  static const annUpdate = 'communications/announcements/update/';
  static const annDeactivate = 'communications/announcements/deactivate/';
  static const annMy = 'communications/announcements/my/';
  static const chatMessages = 'communications/project-chat/messages/';
  static const chatSend = 'communications/project-chat/send/';
  static const chatDelete = 'communications/project-chat/delete/';
  static const chatSettings = 'communications/project-chat/settings/';
  // ---- helpdesk
  static const tkCatCreate = 'helpdesk/category/create/';
  static const tkCatList = 'helpdesk/category/list/';
  static const tkCatUpdate = 'helpdesk/category/update/';
  static const tkCatDeactivate = 'helpdesk/category/deactivate/';
  static const tkCatOptions = 'helpdesk/category/options/';
  static const tkCreate = 'helpdesk/ticket/create/';
  static const tkMy = 'helpdesk/ticket/my-tickets/';
  static const tkList = 'helpdesk/ticket/list/';
  static const tkDetail = 'helpdesk/ticket/detail/';
  static const tkAssign = 'helpdesk/ticket/assign/';
  static const tkUpdate = 'helpdesk/ticket/update/';
  static const tkStatus = 'helpdesk/ticket/status-update/';
  static const tkComment = 'helpdesk/ticket/comment/';
  // ---- assets
  static const asCatCreate = 'assets/category/create/';
  static const asCatList = 'assets/category/list/';
  static const asCatUpdate = 'assets/category/update/';
  static const asCatDeactivate = 'assets/category/deactivate/';
  static const asCreate = 'assets/asset/create/';
  static const asList = 'assets/asset/list/';
  static const asDetail = 'assets/asset/detail/';
  static const asUpdate = 'assets/asset/update/';
  static const asAssign = 'assets/asset/assign/';
  static const asReturn = 'assets/asset/return/';
  static const asDeactivate = 'assets/asset/deactivate/';
  static const asMy = 'assets/asset/my-assets/';
  // ---- visitors
  static const vsCreate = 'visitors/visit/create/';
  static const vsList = 'visitors/visit/list/';
  static const vsDetail = 'visitors/visit/detail/';
  static const vsUpdate = 'visitors/visit/update/';
  static const vsCheckOut = 'visitors/visit/check-out/';
  static const vsDeactivate = 'visitors/visit/deactivate/';
  static const vsLookup = 'visitors/visit/lookup/';
  static const vsMy = 'visitors/visit/my-visitors/';
  // ---- location master (read only)
  static const stateList = 'location_master/states/list/';
  static const districtList = 'location_master/districts/list/';
  static const talukaList = 'location_master/talukas/list/';

  /// Full URL for a media path returned by the server.
  static String media(String? path) {
    if (path == null || path.isEmpty) return '';
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    final base = mediaBaseUrl.isNotEmpty ? mediaBaseUrl : baseUrl;
    return base + (path.startsWith('/') ? path.substring(1) : path);
  }
}
