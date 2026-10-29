from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q


# =========================================================
# WEEKLY OFF RULE
# =========================================================

class WeeklyOffRule(models.Model):

    shift = models.ForeignKey("attendance.Shift", on_delete=models.CASCADE, related_name="weekly_off_rules")

    # Monday = 0, Tuesday = 1, ... Sunday = 6
    day_of_week = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])

    # NULL = every occurrence of the weekday. 1-5 = first through fifth occurrence.
    week_of_month = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="weekly_off_rules_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="weekly_off_rules_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "weekly_off_rules"
        ordering = ["-effective_from", "day_of_week"]
        indexes = [models.Index(fields=["shift", "day_of_week", "effective_from"])]
        constraints = [
            models.CheckConstraint(
                condition=(Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from"))),
                name="valid_weekly_off_date_range",
            ),
        ]

    def __str__(self):
        return f"{self.shift.name} - Day {self.day_of_week} - {self.effective_from}"

# NOTE: day_of_week: Monday = 0, Tuesday = 1, … Sunday = 6.
# NOTE: week_of_month: 1) null: every occurrence of that weekday; 2) 1–5: only that occurrence of the weekday in the month.

# =========================================================
# CALENDAR HOLIDAY
# =========================================================

class CalendarHoliday(models.Model):

    HOLIDAY_TYPE_CHOICES = [
        ("PUBLIC", "Public Holiday"),
        ("NATIONAL", "National Holiday"),
        ("FESTIVAL", "Festival"),
        ("COMPANY", "Company Holiday"),
        ("OTHER", "Other"),
    ]

    PAY_TYPE_CHOICES = [
        ("PAID", "Paid"),
        ("UNPAID", "Unpaid"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="calendar_holidays")

    date = models.DateField()
    name = models.CharField(max_length=200)

    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPE_CHOICES, default="PUBLIC")
    pay_type = models.CharField(max_length=10, choices=PAY_TYPE_CHOICES, default="PAID")

    is_optional = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_holidays_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_holidays_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_holidays"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "date"], name="unique_holiday_per_org_date"),
        ]
        indexes = [models.Index(fields=["organization", "date", "is_active"])]

    def __str__(self):
        return f"{self.name} - {self.date}"