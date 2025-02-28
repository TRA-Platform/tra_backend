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

from webauth.models import AdminMember
from webauth.permissions import AdminPermission
from webauth.serializers import MyTokenObtainPairSerializer
from webauth.serializers import RegisterSerializer, ChangePasswordSerializer, RegisterAdminSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_me(request, *args, **kwargs):
    user = request.user

    data = {
        "username": user.username,
        "first_name": user.first_name,
        "email": user.email,
    }
    if hasattr(user, 'admin'):
        data["object_id"] = user.admin.id
        data["role"] = AdminMember.ROLE_ID

    data["user_id"] = user.id

    return Response(data, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AdminPermission,)
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
            # Check old password
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.data.get('password'))
            user.save()
            update_session_auth_hash(request, user)
            return Response({'status': 'Password changed successfully'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
