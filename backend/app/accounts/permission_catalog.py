"""
Fixed permission catalog and default access roles.

Pure Python (no model imports) so data migrations can use it.
Adding a code here + running `sync_permissions` (or a new data migration)
is the only way to introduce a permission.
"""

# (code, group, label)
PERMISSIONS = [
    ("dashboard.view", "Dashboard", "View dashboard"),

    ("applicant.view", "Recruitment", "View applicants"),
    ("applicant.create", "Recruitment", "Create applicant"),
    ("applicant.update", "Recruitment", "Update applicant"),
    ("applicant.status_update", "Recruitment", "Change applicant status"),
    ("verification.update", "Recruitment", "Update verification checklist and offers"),
    ("onboarding.complete", "Recruitment", "Complete onboarding / convert to employee"),

    ("employee.view_all", "Employees", "View all employees"),
    ("employee.view_team", "Employees", "View own team"),
    ("employee.update", "Employees", "Create / update / deactivate employee"),
    ("employee.create_user", "Employees", "Create user account"),

    ("attendance.view_self", "Attendance", "View own attendance"),
    ("attendance.view_team", "Attendance", "View team attendance"),
    ("attendance.view_all", "Attendance", "View all attendance"),
    ("attendance.correct", "Attendance", "Edit / correct attendance"),
    ("attendance.approve_correction", "Attendance", "Approve correction requests"),
    ("attendance.device_manage", "Attendance", "Manage attendance kiosk devices"),

    ("leave.apply", "Leave", "Apply for leave"),
    ("leave.view_team", "Leave", "View team leave"),
    ("leave.view_all", "Leave", "View all leave"),
    ("leave.approve", "Leave", "Approve / reject leave"),

    ("payroll.view_self", "Payroll", "View own payslips"),
    ("payroll.view_all", "Payroll", "View all payroll"),
    ("payroll.generate", "Payroll", "Generate payroll"),
    ("payroll.finalize", "Payroll", "Finalize payroll"),
    ("salary.assign", "Payroll", "Assign / revise salary"),

    ("reimbursement.review", "Expenses", "Approve / reject reimbursements"),
    ("reimbursement.pay", "Expenses", "Mark reimbursements paid"),
    ("expense.manage", "Expenses", "Manage company and recurring expenses"),

    ("client.manage", "Business", "Manage clients"),
    ("vendor.manage", "Business", "Manage vendors"),
    ("project.manage", "Business", "Manage projects, teams, project heads and tasks"),
    ("payment.manage", "Business", "Manage project payments and invoices"),

    ("ticket.manage", "Office", "Manage all helpdesk tickets and categories"),
    ("ticket.handle", "Office", "Handle helpdesk tickets of own department"),
    ("asset.view", "Office", "View company assets"),
    ("asset.manage", "Office", "Manage and assign company assets"),
    ("visitor.manage", "Office", "Manage the visitor log (front desk)"),

    ("org.manage", "Administration", "Manage branches, departments, designations"),
    ("access.manage", "Administration", "Manage access roles and assign them"),
    ("settings.manage", "Administration", "Manage settings"),
    ("calendar.manage", "Administration", "Manage holidays and weekly offs"),
    ("announcement.manage", "Administration", "Create and manage announcements"),
]

ALL_CODES = [code for code, _group, _label in PERMISSIONS]

# Self-service codes every employee has, with or without an access role.
SELF_SERVICE_CODES = [
    "dashboard.view",
    "attendance.view_self",
    "leave.apply",
    "payroll.view_self",
]

# Default access roles created for every organization.
DEFAULT_ACCESS_ROLES = {
    "HR Manager": {
        "description": "Recruitment, employees, leave and attendance",
        "codes": [
            "dashboard.view", "applicant.view", "applicant.create", "applicant.update",
            "applicant.status_update", "verification.update", "onboarding.complete",
            "employee.view_all", "employee.update", "employee.create_user",
            "attendance.view_self", "attendance.view_all", "attendance.correct",
            "attendance.approve_correction", "attendance.device_manage", "leave.apply", "leave.view_all",
            "leave.approve",
            "reimbursement.review", "payroll.view_self", "salary.assign",
            "calendar.manage", "announcement.manage",
            "ticket.manage", "asset.manage", "visitor.manage",
        ],
    },
    "HR Executive": {
        "description": "Applicant updates and onboarding",
        "codes": [
            "dashboard.view", "applicant.view", "applicant.create", "applicant.update",
            "applicant.status_update", "verification.update", "onboarding.complete",
            "employee.view_all", "attendance.view_self", "leave.apply", "payroll.view_self",
            "ticket.handle", "visitor.manage",
        ],
    },
    "Department Manager": {
        "description": "Own team and approvals",
        "codes": [
            "dashboard.view", "applicant.view", "employee.view_team", "attendance.view_self",
            "attendance.view_team", "attendance.approve_correction", "leave.apply",
            "leave.view_team", "leave.approve", "payroll.view_self",
        ],
    },
    "Payroll Manager": {
        "description": "Payroll and salary assignment",
        "codes": [
            "dashboard.view", "employee.view_all", "attendance.view_self", "attendance.view_all",
            "leave.apply", "leave.view_all", "reimbursement.pay", "payroll.view_self",
            "payroll.view_all", "payroll.generate", "payroll.finalize", "salary.assign",
            "expense.manage", "vendor.manage",
            "ticket.handle", "asset.view",
        ],
    },
}
