from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StateMaster, DistrictMaster, TalukaMaster
from .serializers import (
    StateCreateSerializer,
    StateListSerializer,
    DistrictCreateSerializer,
    DistrictListSerializer,
    TalukaCreateSerializer,
    TalukaListSerializer,
)
from app.audit.services import log_activity


# =========================================================
# STATE CREATE
# =========================================================
class StateCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = StateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": False,
                "message": "Validation failed.",
                "errors": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        state = serializer.save()

        # Audit log
        log_activity(
            request=request,
            action="CREATE",
            module="LOCATION",
            object_type="State",
            object_id=state.id,
            description=f"State '{state.state_name}' created.",
            new_data=StateListSerializer(state).data,
        )

        return Response({
            "status": True,
            "message": "State created successfully.",
            "data": StateListSerializer(state).data,
        }, status=status.HTTP_201_CREATED)


# =========================================================
# STATE DEACTIVATE
# =========================================================
class StateDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        state_id = request.data.get("state_id")
        if not state_id:
            return Response({
                "status": False,
                "message": "state_id is required.",
            }, status=status.HTTP_400_BAD_REQUEST)

        state = StateMaster.objects.filter(id=state_id, is_active=True).first()
        if not state:
            return Response({
                "status": False,
                "message": "State not found.",
            }, status=status.HTTP_404_NOT_FOUND)

        old_data = {"is_active": state.is_active, "state_name": state.state_name}

        state.is_active = False
        state.save(update_fields=["is_active"])

        log_activity(
            request=request,
            action="DELETE",
            module="LOCATION",
            object_type="State",
            object_id=state.id,
            description=f"State '{state.state_name}' deactivated.",
            old_data=old_data,
            new_data={"is_active": False},
        )

        return Response({
            "status": True,
            "message": "State deactivated successfully.",
        })


# =========================================================
# STATE LIST
# =========================================================
class StateListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        states = StateMaster.objects.filter(is_active=True)
        search = request.data.get("search")
        if search:
            states = states.filter(
                Q(state_name__icontains=search) |
                Q(state_code__icontains=search)
            )
        states = states.order_by("state_name")
        serializer = StateListSerializer(states, many=True)
        return Response({
            "status": True,
            "message": "States fetched successfully.",
            "data": serializer.data,
        })


# =========================================================
# DISTRICT CREATE
# =========================================================
class DistrictCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = DistrictCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": False,
                "message": "Validation failed.",
                "errors": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        district = serializer.save()

        log_activity(
            request=request,
            action="CREATE",
            module="LOCATION",
            object_type="District",
            object_id=district.id,
            description=f"District '{district.district_name}' created.",
            new_data=DistrictListSerializer(district).data,
        )

        return Response({
            "status": True,
            "message": "District created successfully.",
            "data": DistrictListSerializer(district).data,
        }, status=status.HTTP_201_CREATED)


# =========================================================
# DISTRICT DEACTIVATE
# =========================================================
class DistrictDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        district_id = request.data.get("district_id")
        if not district_id:
            return Response({
                "status": False,
                "message": "district_id is required.",
            }, status=status.HTTP_400_BAD_REQUEST)

        district = DistrictMaster.objects.filter(id=district_id, is_active=True).first()
        if not district:
            return Response({
                "status": False,
                "message": "District not found.",
            }, status=status.HTTP_404_NOT_FOUND)

        old_data = {"is_active": district.is_active, "district_name": district.district_name}

        district.is_active = False
        district.save(update_fields=["is_active"])

        log_activity(
            request=request,
            action="DELETE",
            module="LOCATION",
            object_type="District",
            object_id=district.id,
            description=f"District '{district.district_name}' deactivated.",
            old_data=old_data,
            new_data={"is_active": False},
        )

        return Response({
            "status": True,
            "message": "District deactivated successfully.",
        })


# =========================================================
# DISTRICT LIST
# =========================================================
class DistrictListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        districts = DistrictMaster.objects.filter(is_active=True)
        state_id = request.data.get("state_id")
        if state_id:
            districts = districts.filter(state_id=state_id)
        search = request.data.get("search")
        if search:
            districts = districts.filter(district_name__icontains=search)
        districts = districts.order_by("district_name")
        serializer = DistrictListSerializer(districts, many=True)
        return Response({
            "status": True,
            "message": "Districts fetched successfully.",
            "data": serializer.data,
        })


# =========================================================
# TALUKA CREATE
# =========================================================
class TalukaCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = TalukaCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": False,
                "message": "Validation failed.",
                "errors": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        taluka = serializer.save()

        log_activity(
            request=request,
            action="CREATE",
            module="LOCATION",
            object_type="Taluka",
            object_id=taluka.id,
            description=f"Taluka '{taluka.taluka_name}' created.",
            new_data=TalukaListSerializer(taluka).data,
        )

        return Response({
            "status": True,
            "message": "Taluka created successfully.",
            "data": TalukaListSerializer(taluka).data,
        }, status=status.HTTP_201_CREATED)


# =========================================================
# TALUKA DEACTIVATE
# =========================================================
class TalukaDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        taluka_id = request.data.get("taluka_id")
        if not taluka_id:
            return Response({
                "status": False,
                "message": "taluka_id is required.",
            }, status=status.HTTP_400_BAD_REQUEST)

        taluka = TalukaMaster.objects.filter(id=taluka_id, is_active=True).first()
        if not taluka:
            return Response({
                "status": False,
                "message": "Taluka not found.",
            }, status=status.HTTP_404_NOT_FOUND)

        old_data = {"is_active": taluka.is_active, "taluka_name": taluka.taluka_name}

        taluka.is_active = False
        taluka.save(update_fields=["is_active"])

        log_activity(
            request=request,
            action="DELETE",
            module="LOCATION",
            object_type="Taluka",
            object_id=taluka.id,
            description=f"Taluka '{taluka.taluka_name}' deactivated.",
            old_data=old_data,
            new_data={"is_active": False},
        )

        return Response({
            "status": True,
            "message": "Taluka deactivated successfully.",
        })


# =========================================================
# TALUKA LIST
# =========================================================
class TalukaListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        talukas = TalukaMaster.objects.filter(is_active=True)
        district_id = request.data.get("district_id")
        if district_id:
            talukas = talukas.filter(district_id=district_id)
        search = request.data.get("search")
        if search:
            talukas = talukas.filter(taluka_name__icontains=search)
        talukas = talukas.order_by("taluka_name")
        serializer = TalukaListSerializer(talukas, many=True)
        return Response({
            "status": True,
            "message": "Talukas fetched successfully.",
            "data": serializer.data,
        })