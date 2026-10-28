from django.db import models

class StateMaster(models.Model):
    state_code = models.CharField(max_length=5, blank=True, null=True)
    state_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    flag = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'state_master'
        ordering = ['state_name']

    def __str__(self):
        return self.state_name


class DistrictMaster(models.Model):
    state = models.ForeignKey(
        StateMaster,
        on_delete=models.CASCADE,
        db_column='state_id'
    )
    district_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    flag = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'district_master'
        ordering = ['district_name']

    def __str__(self):
        return self.district_name


class TalukaMaster(models.Model):
    district = models.ForeignKey(
        DistrictMaster,
        on_delete=models.CASCADE,
        db_column='district_id'
    )
    state = models.ForeignKey(
        StateMaster,
        on_delete=models.CASCADE,
        db_column='state_id'
    )
    taluka_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    flag = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'taluka_master'
        ordering = ['taluka_name']

    def __str__(self):
        return self.taluka_name