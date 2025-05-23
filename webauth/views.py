from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User

import jwt
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes

from webauth.models import AdminMember, ProjectRole
from webauth.permissions import AdminPermission, ProjectPermission
from webauth.serializers import (
    MyTokenObtainPairSerializer,
    RegisterSerializer,
    ChangePasswordSerializer,
    RegisterAdminSerializer,
    ProjectRoleSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_me(request, *args, **kwargs):
    user = request.user

    data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": 1,
    }
    if hasattr(user, 'admin'):
        data["object_id"] = user.admin.id
        data["role"] = AdminMember.ROLE_ID

    data["user_id"] = user.id

    return Response(data, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class RegisterAdminView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AdminPermission,)
    serializer_class = RegisterAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class MyObtainTokenPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        stay_signed = False

        if "stay_signed" in request.data and request.data["stay_signed"]:
            stay_signed = True

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        data = serializer.validated_data

        data.update({"stay_signed": stay_signed})

        decoded = jwt.decode(str(data["access"]), algorithms=["HS256"], options={"verify_signature": False})
        data.update({"username": decoded['username'], "role": decoded['role']})

        return Response(data, status=status.HTTP_200_OK)


class ChangePasswordView(generics.CreateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.data.get('password'))
            user.save()
            update_session_auth_hash(request, user)
            return Response({'status': 'Password changed successfully'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectRoleView(generics.ListCreateAPIView):
    serializer_class = ProjectRoleSerializer
    permission_classes = (IsAuthenticated, ProjectPermission)

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return ProjectRole.objects.filter(project_id=project_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['project_id'] = self.kwargs.get('project_id')
        return context

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        user = self.request.user
        if not user.is_superuser:
            try:
                user_role = ProjectRole.objects.get(user=user, project_id=project_id)
                if user_role.role not in ['OWNER', 'ADMIN', 'MANAGER']:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to add users to this project")
                
            except ProjectRole.DoesNotExist:
                from api.models import Project
                project = Project.objects.get(id=project_id)
                if project.created_by != user:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to add users to this project")
                ProjectRole.objects.create(
                    user=user,
                    project_id=project_id,
                    role='OWNER'
                )
        
        serializer.save(project_id=project_id)


class ProjectRoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectRoleSerializer
    permission_classes = (IsAuthenticated, ProjectPermission)

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return ProjectRole.objects.filter(project_id=project_id)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['project_id'] = self.kwargs.get('project_id')
        return context
        
    def update(self, request, *args, **kwargs):
        user = self.request.user
        project_id = self.kwargs.get('project_id')
        
        if not user.is_superuser:
            try:
                user_role = ProjectRole.objects.get(user=user, project_id=project_id)
                if user_role.role not in ['OWNER', 'ADMIN']:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to update user roles in this project")
            except ProjectRole.DoesNotExist:
                from api.models import Project
                project = Project.objects.get(id=project_id)
                if project.created_by != user:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to update user roles in this project")
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        user = self.request.user
        project_id = self.kwargs.get('project_id')
        project_role = self.get_object()
        if not user.is_superuser:
            try:
                user_role = ProjectRole.objects.get(user=user, project_id=project_id)
                if user_role.role not in ['OWNER', 'ADMIN'] or (project_role.role in ['OWNER', 'ADMIN'] and user_role.role != 'OWNER'):
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to remove users from this project")

            except ProjectRole.DoesNotExist:
                from api.models import Project
                project = Project.objects.get(id=project_id)
                if project.created_by != user:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("You don't have permission to remove users from this project")
                    
        return super().destroy(request, *args, **kwargs)
