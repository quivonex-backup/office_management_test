from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q


# =========================================================
# ATTENDANCE SETTINGS
# =========================================================

class AttendanceSettings(models.Model):

    organization = models.OneToOneField(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_settings",
    )

    # Photo and location verification
    photo_required = models.BooleanField(default=True)
    location_required = models.BooleanField(default=True)
    allowed_radius_meters = models.PositiveIntegerField(default=100)
    max_gps_accuracy_meters = models.PositiveIntegerField(default=50)

    # Face verification threshold (0-100)
    face_match_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=35.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Default shift timings
    default_start_time = models.TimeField(default="09:00")
    default_end_time = models.TimeField(default="18:00")

    # Late and early departure
    late_grace_minutes = models.PositiveIntegerField(default=15)
    early_departure_grace_minutes = models.PositiveIntegerField(default=0)

    # Half-day rules (organization-wise)
    
    # Minimum net working minutes required to avoid half-day based on work duration.
    half_day_threshold_minutes = models.PositiveIntegerField(default=240, validators=[MinValueValidator(0)])

    # Early departure minutes beyond this threshold can trigger half-day.
    early_departure_half_day_threshold_minutes = models.PositiveIntegerField(default=120, validators=[MinValueValidator(0)])

    # Late arrival minutes beyond this threshold can trigger half-day.
    late_half_day_threshold_minutes = models.PositiveIntegerField(default=120, validators=[MinValueValidator(0)])

    # Automatic absent/finalization settings
    auto_mark_absent = models.BooleanField(default=False)
    absent_after_minutes = models.PositiveIntegerField(default=30)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_settings_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_settings_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Attendance Settings - {self.organization}"


# =========================================================
# SHIFT
# =========================================================

class Shift(models.Model):

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_shifts",
    )

    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()

    crosses_midnight = models.BooleanField(default=False)


    late_grace_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    early_departure_grace_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_shifts_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_attendance_shift_name_per_org",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT
# =========================================================

class EmployeeShiftAssignment(models.Model):

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="employee_shift_assignments",
    )

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="shift_assignments",
    )

    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_shifts_assigned",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from"]
        indexes = [
            models.Index(
                fields=["organization", "employee", "effective_from"]
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=models.F("effective_from"))
                ),
                name="valid_employee_shift_date_range",
            )
        ]

    def __str__(self):
        return f"{self.employee} - {self.shift.name}"


# =========================================================
# ATTENDANCE RECORD
# =========================================================

class AttendanceRecord(models.Model):

    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("HALF_DAY", "Half Day"),
        ("INCOMPLETE", "Incomplete"),
        ("PENDING_REVIEW", "Pending Review"),
        ("ABSENT", "Absent"),
        ("ON_LEAVE", "On Leave"),
        ("WEEKLY_OFF", "Weekly Off"),
        ("HOLIDAY", "Holiday"),
    ]

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )

    shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )

    work_date = models.DateField()

    # Scheduled shift snapshot
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    late_grace_minutes = models.PositiveIntegerField(default=15)
    early_departure_grace_minutes = models.PositiveIntegerField(default=0)

    # Check-in and check-out
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    # Calculated attendance minutes
    net_work_minutes = models.PositiveIntegerField(default=0)

    late_minutes = models.PositiveIntegerField(default=0)
    early_departure_minutes = models.PositiveIntegerField(default=0)

    # Actual overtime: minutes after the scheduled shift end
    overtime_minutes = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="INCOMPLETE",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee", "work_date"],
                name="unique_employee_attendance_per_day",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "work_date"]),
            models.Index(fields=["employee", "work_date"]),
            models.Index(fields=["organization", "status", "work_date"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.work_date} - {self.status}"


# =========================================================
# ATTENDANCE PUNCH (PHOTO + LOCATION)
# =========================================================

class AttendancePunch(models.Model):

    PUNCH_TYPE_CHOICES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("FAILED", "Failed"),
        ("MANUAL", "Manual"),
    ]

    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="punches",
    )

    punch_type = models.CharField(
        max_length=20,
        choices=PUNCH_TYPE_CHOICES,
    )

    punched_at = models.DateTimeField()

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    gps_accuracy_meters = models.FloatField(null=True, blank=True)
    office_distance_meters = models.FloatField(null=True, blank=True)

    location_verified = models.BooleanField(default=False)

    selfie = models.ImageField(
        upload_to="attendance/selfies/%Y/%m/",
        null=True,
        blank=True,
    )

    face_similarity = models.FloatField(null=True, blank=True)
    face_verified = models.BooleanField(default=False)

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="PENDING",
    )

    verification_details = models.JSONField(default=dict, blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_punches_recorded",
    )

    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["punched_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["attendance", "punch_type"],
                name="unique_attendance_punch_type",
            )
        ]

    def __str__(self):
        return f"{self.attendance.employee} - {self.punch_type} - {self.punched_at}"


# =========================================================
# ATTENDANCE CORRECTION
# =========================================================

class AttendanceCorrection(models.Model):

    FIELD_CHOICES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
        ("STATUS", "Attendance Status"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("APPLIED", "Applied"),
    ]

    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="corrections",
    )

    punch = models.ForeignKey(
        AttendancePunch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corrections",
    )

    field_name = models.CharField(
        max_length=20,
        choices=FIELD_CHOICES,
    )

    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField()

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="attendance_corrections_requested",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_corrections_reviewed",
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Correction #{self.pk} - {self.field_name} - {self.status}"
