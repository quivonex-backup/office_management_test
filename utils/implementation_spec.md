# Implementation spec (batches 1-4) - companion to backend_gap_plan.md v5

Base: repo main @ e67416b. All endpoints POST, JWT, envelope `{status, message, data, errors?}`. `organization_id` in the body only for multi-org users (existing `get_user_organization`). "NEW" = new endpoint, "UPD" = existing endpoint gets additive fields only (old clients keep working). Endpoint names for NEW ones are proposals; recruitment names come from the owner.

Test method: SQLite settings override + Django test client inside a rolled-back transaction (verified 22 Nov: `manage.py check` clean, all existing migrations apply, `makemigrations --check` = no drift). S3, email, Firebase, face match are stubbed in tests. MySQL itself is not exercised.

---
## Batch 1 - org masters + access

### Models
| App | Model | Status | Fields |
|---|---|---|---|
| accounts | Role, User | unchanged | - |
| accounts | Branch | NEW | organization FK, name, code?, address?, city?, state FK StateMaster?, latitude?, longitude?, allowed_radius_meters? (null = org setting), is_active, created_by/updated_by, timestamps; unique(organization, name) |
| accounts | Permission | NEW | code (unique), group, label. Seeded by data migration with the 28 codes. |
| accounts | AccessRole | NEW | organization FK, name, description?, is_active, audit fields; unique(organization, name) |
| accounts | AccessRolePermission | NEW | access_role FK, permission FK; unique pair |
| employees | Department | NEW | organization FK, name, code?, is_active, audit; unique(organization, name) |
| employees | Designation | NEW | organization FK, name, is_active, audit; unique(organization, name) |
| employees | Employee | UPD | + branch FK?, department_ref FK?, designation_ref FK?, access_role FK?, reports_to FK self? (all SET_NULL). Text `department`/`designation` kept, filled from the master on save. |

Migrations: accounts 0008 (models) + 0009 (seed permissions; default AccessRoles for every existing organization); employees 0xxx (models + fields).

### Common
- `common/permissions.py`: `get_permission_codes(user, organization)` (owner = all codes), `has_perm(request, organization, code)`, `permission_denied(code)` -> 403 `{"status": false, "message": "You do not have permission to perform this action."}`.
- `common/services.py`: `get_team_employee_ids(employee)` (iterative, includes self), `would_create_cycle(employee, new_manager)`.
- `accounts/services.py`: `seed_organization_defaults(organization)`: 4 default AccessRoles (HR Manager, HR Executive, Department Manager, Payroll Manager) from the zip matrix. Called from organization create and from the data migration.

### NEW endpoints
| Endpoint | Perm | Request | data |
|---|---|---|---|
| accounts/branch/list/ | member | `{search?, is_active?}` | `[{id, name, code, address, city, state_id, state_name, latitude, longitude, allowed_radius_meters, is_active, employee_count}]` |
| accounts/branch/create/ | org.manage | `{name, code?, address?, city?, state_id?, latitude?, longitude?, allowed_radius_meters?}` | branch object |
| accounts/branch/update/ | org.manage | `{branch_id, ...changed fields}` | branch object |
| accounts/branch/deactivate/ | org.manage | `{branch_id}` | `{id, is_active}`; refused while active employees use it |
| employees/department/list/ | member | `{search?, is_active?}` | `[{id, name, code, is_active, employee_count}]` |
| employees/department/create/ update/ deactivate/ | org.manage | `{name, code?}` / `{department_id, ...}` / `{department_id}` | department object |
| employees/designation/list/ | member | `{search?, is_active?}` | `[{id, name, is_active, employee_count}]` |
| employees/designation/create/ update/ deactivate/ | org.manage | `{name}` / `{designation_id, name?}` / `{designation_id}` | designation object |
| accounts/permission/list/ | access.manage | `{}` | `[{code, group, label}]` |
| accounts/access-role/list/ | access.manage | `{}` | `[{id, name, description, is_active, permission_codes[], employee_count}]` |
| accounts/access-role/create/ | access.manage | `{name, description?, permission_codes[]}` | access role object |
| accounts/access-role/update/ | access.manage | `{access_role_id, name?, description?, permission_codes?}` (codes = full replacement) | access role object |
| accounts/access-role/deactivate/ | access.manage | `{access_role_id}` | refused while assigned to active employees |

### UPD endpoints
| Endpoint | Change |
|---|---|
| accounts/my-profile/ | data + `account_role` ("Admin"/"Employee"), `is_org_owner`, `organization {id, name}`, `employee {id, employee_code, full_name, branch {id,name}, department {id,name}, designation {id,name}, reports_to {id, full_name}}` (null if none), `access_role {id, name}` (null), `permissions[]` |
| employees/create/, employees/update/ | accept `branch_id`, `department_id`, `designation_id`, `access_role_id` (needs access.manage), `reports_to_id` (same org, active, no cycle) ; require employee.update (create also employee.update) |
| employees/list/, employees/detail/ | rows + `branch {id,name}`, `department_ref {id,name}`, `designation_ref {id,name}`, `access_role {id,name}`, `reports_to {id, full_name}`; filters `branch_id`, `department_id`, `designation_id`, `access_role_id`, `reports_to_id` |
| accounts/organization/create/ | also calls `seed_organization_defaults` |
| accounts/organization/assign-owner/ | old owner downgraded to Employee role (no Accountant role needed) |

---
## Batch 2 - enforcement + scope + branch GPS
- `common/services.py resolve_scope(request, organization, requested, view_self, view_team, view_all)` -> (scope_applied, employee_ids or None=all). Default when `scope` omitted: widest allowed (keeps current admin behaviour for admins).
- `scope` + `scope_applied` in data meta on: attendance/list, attendance/corrections/list, leave/applications/list, leave/balances/list, expenses/reimbursements/list, employees/list (employee.view_team / view_all). payroll/records/list: self | all.
- Permission checks (one line each): attendance settings/shifts/assignments/bulk-mark-absent (settings.manage / attendance.correct), corrections/review (attendance.approve_correction + in scope), leave types/balances adjust/initialize (settings.manage), leave review (leave.approve + in scope, not own), reimbursements review/mark-paid (new codes reimbursement.review, reimbursement.pay; not own), payroll runs/generate (payroll.generate), finalize (payroll.finalize), assignments (salary.assign), records/payments list (payroll.view_all).
- `attendance/services.py verify_office_location(..., employee=None)`: branch lat/long/radius first, organization fallback. `process_attendance_punch` passes employee. Punch response: + `branch {id,name}` in verification details.
- New permission codes added by migration: reimbursement.review, reimbursement.pay.

## Batch 3 - CTC + recruitment
Payroll (UPD, backwards compatible):
- EmployeeSalaryAssignment + `annual_ctc?`, `monthly_gross?`; SalaryStructureComponent + `is_balancing`; PayrollSettings + `ctc_includes_employer_contributions` (default True).
- `_resolve_component_amounts(structure, monthly_gross=None)`, `compute_payslip_data` reads assignment gross, `simulate_payslip(..., monthly_gross=None)`.
- UPD: payroll/assignments/create, bulk-assign, list (+ annual_ctc, monthly_gross); payroll/calculator/ (+ monthly_gross or annual_ctc, returns + `ctc_breakup {monthly_gross, employer_pf, employer_esi, annual_ctc}`); payroll/structures/create|update (+ is_balancing per component).
Recruitment app (NEW): models Applicant, ApplicantDocument, ApplicantInterview, ApplicantStatusHistory, ApplicantOffer, ApplicantCheck. Endpoints (owner's names): applicant/create, list, detail, update, status-update, verification, onboarding, convert. Detail returns everything for the 3 tabs in one call: `{applicant, documents[], interviews[], history[], current_offer, offers[], verification_checks[], onboarding_checks[], employee_id, allowed_actions[]}`. `allowed_actions` lets the UI show one main button. Full request/response tables written at the start of batch 3.

## Batch 4 - cleanup
- `employee_code` unique per organization (+ username prefixed with organization_code for new accounts).
- EmployeeDeactivate closes open shift + salary assignments.
- `bulk_mark_absent` rejects to_date >= today.
- Re-enable `attendance/tasks.py` auto-absent + beat schedule note.
- Audit logs in leave, attendance, reimbursement views.

## Delivery per batch
Changed files as a zip (same paths as the repo) + new migrations + `tests_batchN.py` script output + updated `admin.txt` sections for the UI developer.
