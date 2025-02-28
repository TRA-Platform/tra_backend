from django.db import transaction
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import time
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate

from rest_framework.authtoken.models import Token
from webauth.models import AdminMember


class TraderChangeSerializer(serializers.Serializer):
    email = serializers.CharField(required=False, write_only=True)
    phone = serializers.CharField(required=False, write_only=True)
    username = serializers.CharField(required=False, write_only=True)
    telegram = serializers.CharField(required=False, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    password2 = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not authenticate(username=user.username, password=value):
            raise serializers.ValidationError('Old password is not correct')
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Passwords must match.'})
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    stay_signed = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        data = super(CustomTokenObtainPairSerializer, self).validate(attrs)
        return data


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    stay_signed_in = serializers.BooleanField(default=False)
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    default_error_messages = {
        "no_active_account": ("The password is wrong or the user doesn't exist")
    }

    @classmethod
    def get_token(cls, user):
        token = super(MyTokenObtainPairSerializer, cls).get_token(user)
        token['username'] = user.username
        token['role'] = 1
        if hasattr(user, 'admin'):
            token['role'] = 9

        return token


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    access = serializers.SerializerMethodField(read_only=True)
    refresh = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', "access", "refresh")

    def get_refresh(self, obj):
        token = MyTokenObtainPairSerializer.get_token(obj)
        return str(token)

    def get_access(self, obj):
        token = MyTokenObtainPairSerializer.get_token(obj)
        access_token = token.access_token
        return str(access_token)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
        )

        user.set_password(validated_data['password'])
        user.save()
        return user


class RegisterAdminSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    first_name = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'password', 'password2', 'email')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create(
                first_name=validated_data['first_name'],
                username=validated_data['username'],
                email=validated_data['email'],
            )

            user.set_password(validated_data['password'])
            user.save()

            admin = AdminMember.objects.create(user=user)
            admin.save()

            for team in validated_data['controlled_teams']:
                team.admins.add(admin)

            return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'username')
