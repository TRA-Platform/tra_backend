from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from django.conf import settings

from webauth.models import AdminMember, ManagerMember, ModeratorMember

class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS or (request.user.is_superuser and request.user.is_authenticated):
            return True
        return False


class AdminPermission(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True
        is_admin = AdminMember.objects.filter(user=request.user).exists()
        return is_admin


class ManagerPermission(BasePermission):
    def has_permission(self, request, view):
        is_manager = ManagerMember.objects.filter(user=request.user).exists()
        return is_manager or request.user.is_superuser


class ModeratorPermission(BasePermission):
    def has_permission(self, request, view):
        is_moderator = ModeratorMember.objects.filter(user=request.user).exists()
        return is_moderator or request.user.is_superuser


class DebugPermission(BasePermission):
    def has_permission(self, request, view):
        if settings.DEBUG and request.user.is_authenticated:
            return True
        return False
