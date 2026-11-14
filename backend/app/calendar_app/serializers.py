from django.db.models import Q
from rest_framework import serializers

from .models import WeeklyOffRule, CalendarHoliday


# =========================================================
# WEEKLY OFF RULE SERIALIZER
# =========================================================

class WeeklyOffRuleSerializer(serializers.ModelSerializer):

    shift_name = serializers.CharField(
        source="shift.name",
        read_only=True,
    )

    class Meta:
        model = WeeklyOffRule
        fields = [
            "id",
            "shift",
            "shift_name",
            "day_of_week",
            "week_of_month",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "shift_name",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_shift(self, shift):
        organization = self.context.get("organization")

        if organization and shift.organization_id != organization.id:
            raise serializers.ValidationError(
                "Selected shift does not belong to this organization."
            )

        if not shift.is_active:
            raise serializers.ValidationError(
                "Cannot assign a weekly-off rule to an inactive shift."
            )

        return shift

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        shift = attrs.get(
            "shift",
            instance.shift if instance else None,
        )
        day_of_week = attrs.get(
            "day_of_week",
            instance.day_of_week if instance else None,
        )
        week_of_month = attrs.get(
            "week_of_month",
            instance.week_of_month if instance else None,
        )
        effective_from = attrs.get(
            "effective_from",
            instance.effective_from if instance else None,
        )
        effective_to = attrs.get(
            "effective_to",
            instance.effective_to if instance else None,
        )

        if effective_from and effective_to:
            if effective_to < effective_from:
                raise serializers.ValidationError({
                    "effective_to": (
                        "Effective-to date cannot be before "
                        "effective-from date."
                    )
                })

        if not all([
            shift,
            day_of_week is not None,
            effective_from,
        ]):
            return attrs

        # A general weekday rule conflicts with every specific
        # occurrence of that weekday during overlapping dates.
        overlapping_rules = WeeklyOffRule.objects.filter(
            shift=shift,
            day_of_week=day_of_week,
            is_active=True,
            effective_from__lte=effective_to
            if effective_to else effective_from,
        ).exclude(
            pk=instance.pk if instance else None,
        )

        if week_of_month is None:
            overlapping_rules = overlapping_rules.filter(
                Q(week_of_month__isnull=True)
                | Q(week_of_month__gte=1)
            )
        else:
            overlapping_rules = overlapping_rules.filter(
                Q(week_of_month__isnull=True)
                | Q(week_of_month=week_of_month)
            )

        # Date ranges overlap if the existing rule has not ended
        # before the new rule starts, and the new rule does not end
        # before the existing rule starts.
        overlapping_rules = overlapping_rules.filter(
            Q(effective_to__isnull=True)
            | Q(effective_to__gte=effective_from)
        )

        if effective_to:
            overlapping_rules = overlapping_rules.filter(
                effective_from__lte=effective_to
            )

        if overlapping_rules.exists():
            raise serializers.ValidationError(
                "This rule conflicts with an existing active weekly-off "
                "rule for the same shift and weekday. Use non-overlapping "
                "effective dates or update the existing rule."
            )

        return attrs


# =========================================================
# CALENDAR HOLIDAY READ SERIALIZER
# =========================================================

class CalendarHolidaySerializer(serializers.ModelSerializer):

    class Meta:
        model = CalendarHoliday
        fields = [
            "id",
            "date",
            "name",
            "holiday_type",
            "pay_type",
            "is_optional",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# =========================================================
# CALENDAR HOLIDAY CREATE / UPDATE SERIALIZER
# =========================================================

class CalendarHolidayWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = CalendarHoliday
        fields = [
            "date",
            "name",
            "holiday_type",
            "pay_type",
            "is_optional",
            "description",
        ]

    def validate(self, attrs):
        organization = self.context.get("organization")
        instance = getattr(self, "instance", None)

        holiday_date = attrs.get(
            "date",
            instance.date if instance else None,
        )

        if organization and holiday_date:
            duplicate = CalendarHoliday.objects.filter(
                organization=organization,
                date=holiday_date,
            )

            if instance:
                duplicate = duplicate.exclude(pk=instance.pk)

            if duplicate.exists():
                raise serializers.ValidationError({
                    "date": (
                        "A holiday already exists for this date "
                        "in this organization."
                    )
                })

        return attrs


# =========================================================
# EMPLOYEE CALENDAR DAY SERIALIZER
# =========================================================

class EmployeeCalendarRequestSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)

    def validate(self, attrs):
        if attrs["date_to"] < attrs["date_from"]:
            raise serializers.ValidationError({
                "date_to": "End date must be on or after start date."
            })

        if (attrs["date_to"] - attrs["date_from"]).days > 366:
            raise serializers.ValidationError({
                "date_to": "Maximum calendar range is 367 days."
            })

        return attrs


class EmployeeCalendarDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    day_type = serializers.ChoiceField(choices=[
        ("WORKING_DAY", "Working Day"),
        ("WEEKLY_OFF", "Weekly Off"),
        ("HOLIDAY", "Holiday"),
        ("NO_SHIFT_ASSIGNED", "No Shift Assigned"),
    ])
    is_working_day = serializers.BooleanField()
    shift_id = serializers.IntegerField(allow_null=True)
    shift_name = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    shift_start_time = serializers.TimeField(allow_null=True)
    shift_end_time = serializers.TimeField(allow_null=True)
    holiday_name = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    holiday_type = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    pay_type = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    is_optional = serializers.BooleanField()
    weekly_off_rule_id = serializers.IntegerField(allow_null=True)
    week_of_month = serializers.IntegerField(allow_null=True)
