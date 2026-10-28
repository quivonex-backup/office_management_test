from rest_framework import serializers
from .models import Client, ClientDocument


# =========================================================
# CLIENT DOCUMENT SERIALIZER
# =========================================================
class ClientDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientDocument
        fields = ['id', 'title', 'file', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


# =========================================================
# CLIENT CREATE SERIALIZER
# =========================================================
class ClientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            'client_name',
            'company_name',
            'mobile',
            'email',
            'gst_number',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'notes',
        ]


# =========================================================
# CLIENT LIST SERIALIZER
# =========================================================
class ClientListSerializer(serializers.ModelSerializer):
    documents = ClientDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'client_code',
            'client_name',
            'company_name',
            'mobile',
            'email',
            'gst_number',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'notes',
            'documents',
            'is_active',
            'created_at',
        ]


# =========================================================
# CLIENT DETAIL SERIALIZER
# =========================================================
class ClientDetailSerializer(serializers.ModelSerializer):
    documents = ClientDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'client_code',
            'client_name',
            'company_name',
            'mobile',
            'email',
            'gst_number',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'notes',
            'is_active',
            'documents',
            'created_at',
            'updated_at',
        ]


# =========================================================
# CLIENT UPDATE SERIALIZER
# =========================================================
class ClientUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            'client_name',
            'company_name',
            'mobile',
            'email',
            'gst_number',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'notes',
        ]
        extra_kwargs = {
            'client_name': {'required': False},
        }