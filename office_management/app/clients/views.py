from django.db import transaction
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Client, ClientDocument
from .serializers import (
    ClientCreateSerializer,
    ClientListSerializer,
    ClientDetailSerializer,
    ClientUpdateSerializer,
)
from common.services import get_user_organization
from common.s3_utils import upload_to_s3, delete_from_s3
from common.code_generators import generate_client_code
from app.audit.services import log_activity



# =========================================================
# CREATE CLIENT
# =========================================================
class ClientCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = ClientCreateSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        client.client_code = generate_client_code()
        client.save(update_fields=["client_code", "updated_at"])

        files = request.FILES.getlist("documents")
        uploaded_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="clients/documents",
            )

            document = ClientDocument.objects.create(
                client=client,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            uploaded_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name,
            })

        log_activity(
            request=request,
            action="CREATE",
            module="CLIENT",
            object_type="Client",
            object_id=client.id,
            description=f"Client {client.client_code} created.",
            new_data={
                "client_code": client.client_code,
                "client_name": client.client_name,
                "company_name": client.company_name,
                "organization_id": organization.id,
                "mobile": client.mobile,
                "email": client.email,
                "gst_number": client.gst_number,
                "address": client.address,
                "state": client.state,
                "district": client.district,
                "taluka": client.taluka,
                "pincode": client.pincode,
                "notes": client.notes,
                "documents": uploaded_documents,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Client created successfully.",
                "data": ClientDetailSerializer(
                    client,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# CLIENT LIST
# =========================================================
class ClientListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        clients = Client.objects.filter(
            organization=organization,
            is_active=True,
        )

        # SEARCH
        search = request.data.get("search")
        if search:
            search = search.strip()
            clients = clients.filter(
                Q(client_code__icontains=search)
                | Q(client_name__icontains=search)
                | Q(company_name__icontains=search)
                | Q(mobile__icontains=search)
                | Q(email__icontains=search)
                | Q(gst_number__icontains=search)
            )

        clients = clients.order_by("-created_at")
        serializer = ClientListSerializer(clients, many=True, context={"request": request})

        return Response(
            {
                "status": True,
                "message": "Clients fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CLIENT DETAIL
# =========================================================
class ClientDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        client_id = request.data.get("client_id")
        if not client_id:
            return Response(
                {"status": False, "message": "client_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = Client.objects.filter(
            id=client_id,
            organization=organization,
            is_active=True,
        ).first()

        if not client:
            return Response(
                {"status": False, "message": "Client not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientDetailSerializer(
            client,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Client details fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE CLIENT
# =========================================================
class ClientUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]


    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        client_id = request.data.get("client_id")
        if not client_id:
            return Response(
                {"status": False, "message": "client_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = Client.objects.filter(
            id=client_id,
            organization=organization,
            is_active=True,
        ).first()

        if not client:
            return Response(
                {"status": False, "message": "Client not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "client_name": client.client_name,
            "company_name": client.company_name,
            "mobile": client.mobile,
            "email": client.email,
            "gst_number": client.gst_number,
            "address": client.address,
            "state": client.state,
            "district": client.district,
            "taluka": client.taluka,
            "pincode": client.pincode,
            "notes": client.notes,
        }

        serializer = ClientUpdateSerializer(
            client,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = serializer.save(updated_by=request.user)

        remove_document_ids = request.data.getlist("remove_document_ids")
        removed_documents = []

        for document_id in remove_document_ids:
            document = ClientDocument.objects.filter(
                id=document_id,
                client=client,
            ).first()

            if not document:
                continue

            removed_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name if document.file else None,
            })

            if document.file:
                delete_from_s3(document.file)

            document.delete()

        files = request.FILES.getlist("documents")
        added_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="clients/documents",
            )

            document = ClientDocument.objects.create(
                client=client,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            added_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name,
            })

        new_data = {
            "client_name": client.client_name,
            "company_name": client.company_name,
            "mobile": client.mobile,
            "email": client.email,
            "gst_number": client.gst_number,
            "address": client.address,
            "state": client.state,
            "district": client.district,
            "taluka": client.taluka,
            "pincode": client.pincode,
            "notes": client.notes,
        }

        if added_documents:
            new_data["documents_added"] = added_documents

        if removed_documents:
            new_data["documents_removed"] = removed_documents

        log_activity(
            request=request,
            action="UPDATE",
            module="CLIENT",
            object_type="Client",
            object_id=client.id,
            description=f"Client {client.client_code} updated.",
            old_data=old_data,
            new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Client updated successfully.",
                "data": ClientDetailSerializer(
                    client,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE CLIENT / SOFT DELETE
# =========================================================
class ClientDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        client_id = request.data.get("client_id")
        if not client_id:
            return Response(
                {"status": False, "message": "client_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = Client.objects.filter(
            id=client_id,
            organization=organization,
            is_active=True,
        ).first()

        if not client:
            return Response(
                {"status": False, "message": "Client not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {"is_active": client.is_active}

        client.is_active = False
        client.updated_by = request.user
        client.save(
            update_fields=["is_active", "updated_by", "updated_at"]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="CLIENT",
            object_type="Client",
            object_id=client.id,
            description=f"Client {client.client_code} deactivated.",
            old_data=old_data,
            new_data={"is_active": False},
        )

        return Response(
            {"status": True, "message": "Client deactivated successfully."},
            status=status.HTTP_200_OK,
        )
