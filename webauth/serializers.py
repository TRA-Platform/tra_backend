from django.db import transaction
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate

from rest_framework.authtoken.models import Token
from webauth.models import AdminMember, ManagerMember, ModeratorMember, ProjectRole

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    password = serializers.CharField(required=True, validators=[validate_password])
    password2 = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not authenticate(username=user.username, password=value):
            raise serializers.ValidationError('Old password is not correct')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs


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
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        if hasattr(user, 'admin'):
            token['role'] = AdminMember.ROLE_ID
        elif hasattr(user, 'manager'):
            token['role'] = ManagerMember.ROLE_ID
        elif hasattr(user, 'moderator'):
            token['role'] = ModeratorMember.ROLE_ID
        else:
            token['role'] = None

        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class RegisterAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        AdminMember.objects.create(user=user)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'username')


class ProjectRoleSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    user_email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = ProjectRole
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'user_id', 'user_email', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        if not self.instance and 'user_id' not in attrs and 'user_email' not in attrs:
            raise serializers.ValidationError("Either user_id or user_email must be provided")
        if 'role' in attrs and attrs['role'] not in dict(ProjectRole.ROLE_CHOICES).keys():
            raise serializers.ValidationError({"role": f"Invalid role choice. Must be one of {dict(ProjectRole.ROLE_CHOICES).keys()}"})
        
        return attrs

    def create(self, validated_data):
        user = None
        if 'user_id' in validated_data:
            user_id = validated_data.pop('user_id')
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_id": "User with this ID does not exist"})
        
        if not user and 'user_email' in validated_data:
            user_email = validated_data.pop('user_email')
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_email": "User with this email does not exist"})
        
        if not user:
            raise serializers.ValidationError("No valid user found")
        project_id = self.context.get('project_id')
        existing_role = ProjectRole.objects.filter(user=user, project_id=project_id).first()
        if existing_role:
            raise serializers.ValidationError({"user": "User already has a role in this project"})
        
        validated_data['user'] = user
        
        return super().create(validated_data)
