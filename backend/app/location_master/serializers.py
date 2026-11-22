from rest_framework import serializers
from .models import StateMaster, DistrictMaster, TalukaMaster


# =========================================================
# STATE CREATE SERIALIZER
# =========================================================
class StateCreateSerializer(serializers.ModelSerializer):
    # The live database has state_code NOT NULL + UNIQUE (the model says
    # optional). Require it here so a missing code is a 400, not a 500.
    state_code = serializers.CharField(max_length=5)

    class Meta:
        model = StateMaster
        fields = ['state_code', 'state_name']

    def validate_state_code(self, value):
        value = value.strip().upper()
        if StateMaster.objects.filter(state_code__iexact=value).exists():
            raise serializers.ValidationError("A state with this code already exists.")
        return value

    def validate_state_name(self, value):
        value = value.strip()
        if StateMaster.objects.filter(state_name__iexact=value).exists():
            raise serializers.ValidationError("A state with this name already exists.")
        return value


# =========================================================
# STATE LIST SERIALIZER
# =========================================================
class StateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = StateMaster
        fields = ['id', 'state_code', 'state_name']
        read_only_fields = ['id']


# =========================================================
# DISTRICT CREATE SERIALIZER
# =========================================================
class DistrictCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistrictMaster
        fields = ['state_id', 'district_name']


# =========================================================
# DISTRICT LIST SERIALIZER
# =========================================================
class DistrictListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistrictMaster
        fields = ['id', 'state_id', 'district_name']
        read_only_fields = ['id']


# =========================================================
# TALUKA CREATE SERIALIZER
# =========================================================
class TalukaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalukaMaster
        fields = ['district_id', 'taluka_name']

    def validate(self, data):
        district = DistrictMaster.objects.filter(id=data['district_id']).first()
        if not district:
            raise serializers.ValidationError("District not found.")
        # Automatically set state_id from the district
        data['state_id'] = district.state_id
        return data


# =========================================================
# TALUKA LIST SERIALIZER
# =========================================================
class TalukaListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalukaMaster
        fields = ['id', 'state_id', 'district_id', 'taluka_name']
        read_only_fields = ['id']