from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from django.conf import settings

from webauth.models import AdminMember, ManagerMember, ModeratorMember, ProjectRole

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


class ProjectPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if hasattr(view, "action"):
            if view.action == 'list':
                return True
            if view.action == 'create':
                return True
        project_id = self._get_project_id(view, request)
        if not project_id:
            return True
        try:
            project_role = ProjectRole.objects.get(
                user=request.user,
                project_id=project_id
            )
            if request.method in SAFE_METHODS:
                return True
                
            if project_role.role in ['OWNER', 'ADMIN']:
                return True
                
            if project_role.role == 'MANAGER':
                return request.method not in ['DELETE']
                
            if project_role.role == 'MEMBER':
                return request.method in ['POST', 'PUT', 'PATCH']
                
            return False
            
        except ProjectRole.DoesNotExist:
            from api.models import Project
            if hasattr(view, 'get_object'):
                try:
                    obj = view.get_object()
                    if hasattr(obj, 'project'):
                        return obj.project.created_by == request.user
                    elif hasattr(obj, 'requirement') and hasattr(obj.requirement, 'project'):
                        return obj.requirement.project.created_by == request.user
                    elif hasattr(obj, 'user_story') and hasattr(obj.user_story, 'requirement') and hasattr(obj.user_story.requirement, 'project'):
                        return obj.user_story.requirement.project.created_by == request.user
                    elif hasattr(obj, 'plan') and hasattr(obj.plan, 'project'):
                        return obj.plan.project.created_by == request.user
                    elif hasattr(obj, 'created_by'):
                        return obj.created_by == request.user
                except:
                    pass
            return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        project_id = self._get_project_id_from_object(obj)
        if not project_id:
            if hasattr(obj, 'created_by'):
                return obj.created_by == request.user
            return False

        try:
            project_role = ProjectRole.objects.get(
                user=request.user,
                project_id=project_id
            )
            if request.method in SAFE_METHODS:
                return True
                
            if project_role.role in ['OWNER', 'ADMIN']:
                return True
                
            if project_role.role == 'MANAGER':
                return request.method not in ['DELETE']
                
            if project_role.role == 'MEMBER':
                return request.method in ['POST', 'PUT', 'PATCH']
                
            return False
            
        except ProjectRole.DoesNotExist:
            if hasattr(obj, 'project') and hasattr(obj.project, 'created_by'):
                return obj.project.created_by == request.user
            elif hasattr(obj, 'requirement') and hasattr(obj.requirement, 'project') and hasattr(obj.requirement.project, 'created_by'):
                return obj.requirement.project.created_by == request.user
            elif hasattr(obj, 'user_story') and hasattr(obj.user_story, 'requirement') and hasattr(obj.user_story.requirement, 'project') and hasattr(obj.user_story.requirement.project, 'created_by'):
                return obj.user_story.requirement.project.created_by == request.user
            elif hasattr(obj, 'created_by'):
                return obj.created_by == request.user
            
            return False
    
    def _get_project_id(self, view, request):
        project_id = view.kwargs.get('project_id')
        if project_id:
            return project_id
        project_id = request.data.get('project')
        if project_id:
            return project_id
        project_id = request.query_params.get('project')
        if project_id:
            return project_id
        if hasattr(view, 'get_object') and view.__class__.__name__ == 'ProjectViewSet':
            pk = view.kwargs.get('pk')
            if pk:
                return pk
                
        return None
    
    def _get_project_id_from_object(self, obj):
        if hasattr(obj, 'id') and obj.__class__.__name__ == 'Project':
            return obj.id
        if hasattr(obj, 'project_id'):
            return obj.project_id
        if hasattr(obj, 'project'):
            return obj.project.id
        if hasattr(obj, 'requirement') and hasattr(obj.requirement, 'project'):
            return obj.requirement.project.id
        if hasattr(obj, 'user_story') and hasattr(obj.user_story, 'requirement') and hasattr(obj.user_story.requirement, 'project'):
            return obj.user_story.requirement.project.id
        if hasattr(obj, 'plan') and hasattr(obj.plan, 'project'):
            return obj.plan.project.id
        return None


class DebugPermission(BasePermission):
    def has_permission(self, request, view):
        if settings.DEBUG and request.user.is_authenticated:
            return True
        return False
