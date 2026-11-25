class AppConstants {
  AppConstants._();
  static const defaultPageSize = 15;
  static const dateFormat = 'dd MMM yyyy';
  static const timeFormat = 'hh:mm a';
  static const dateTimeFormat = 'dd MMM yyyy, hh:mm a';
  static const apiDateFormat = 'yyyy-MM-dd';

  // Enumerations used by forms (from the React models).
  static const assetStatuses = ['AVAILABLE', 'ASSIGNED', 'IN_REPAIR', 'RETIRED', 'LOST'];
  static const editableAssetStatuses = ['AVAILABLE', 'IN_REPAIR', 'RETIRED', 'LOST'];
  static const conditions = ['NEW', 'GOOD', 'FAIR', 'DAMAGED'];
  static const ticketStatuses = ['OPEN', 'IN_PROGRESS', 'ON_HOLD', 'RESOLVED', 'CLOSED'];
  static const ticketPriorities = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];
  static const visitPurposes = ['MEETING', 'INTERVIEW', 'CLIENT', 'VENDOR', 'DELIVERY', 'PERSONAL', 'OTHER'];
  static const idTypes = ['AADHAAR', 'PAN', 'DL', 'PASSPORT', 'VOTER_ID', 'OTHER'];
  static const weekDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  static const holidayTypes = ['PUBLIC', 'NATIONAL', 'FESTIVAL', 'COMPANY', 'OTHER'];
  static const priorities = ['low', 'medium', 'high', 'urgent'];
  static const projectStatuses = ['new', 'in_progress', 'testing', 'completed', 'on_hold', 'cancelled'];
  static const taskStatuses = ['TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE'];
  static const expenseTypes = ['food', 'travel', 'utilities', 'rent', 'software', 'cloud', 'equipment', 'office', 'maintenance', 'telephone', 'marketing', 'professional_services', 'other'];
  static const recurringTypes = ['electricity', 'rent', 'cloud', 'internet', 'software', 'telephone', 'other'];
  static const payMethods = ['cash', 'bank_transfer', 'upi', 'card', 'cheque', 'other'];
  static const txMethods = ['CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE', 'CARD', 'ONLINE', 'OTHER'];
  static const announcementPriorities = ['NORMAL', 'HIGH', 'URGENT'];
  static const applicantStatuses = ['PENDING', 'SHORTLISTED', 'SELECTED', 'REJECTED', 'WITHDRAWN'];
  static const attendanceStatuses = ['PRESENT', 'HALF_DAY', 'INCOMPLETE', 'PENDING_REVIEW', 'ABSENT', 'ON_LEAVE', 'WEEKLY_OFF', 'HOLIDAY'];
}
