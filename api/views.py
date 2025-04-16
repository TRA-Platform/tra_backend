from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from webauth.permissions import AdminPermission, ManagerPermission, ModeratorPermission
from .models import (
    SrsTemplate, Project, Requirement, RequirementComment,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup
)
from .serializers import (
    SrsTemplateSerializer, ProjectSerializer, RequirementSerializer, RequirementCommentSerializer,
    DevelopmentPlanSerializer, DevelopmentPlanVersionSerializer, MockupSerializer, ProjectListSerializer
)
from .tasks import (
    generate_requirements_task, export_srs_task, generate_development_plan_task,
    generate_mockups_task
)


class SrsTemplateViewSet(viewsets.ModelViewSet):
    queryset = SrsTemplate.objects.all()
    serializer_class = SrsTemplateSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return Project.objects.all()
        if ManagerPermission().has_permission(self.request, self):
            return Project.objects.all()
        if ModeratorPermission().has_permission(self.request, self):
            return Project.objects.all()
        return Project.objects.filter(created_by=u)

    def get_serializer_class(self):
        if self.action == "list":
            return ProjectListSerializer
        return ProjectSerializer

    @action(detail=True, methods=["post"])
    def generate_requirements(self, request, pk=None):
        p = self.get_object()
        generate_requirements_task.delay(str(p.id))
        return Response({"status": "Generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def export_srs(self, request, pk=None):
        u = request.user
        p = self.get_object()
        fmt = request.data.get("format", "pdf")
        export_srs_task.delay(
            str(p.id),
            created_by=u.id,
            fmt=fmt
        )
        return Response({"status": "Export started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_plan(self, request, pk=None):
        p = self.get_object()
        generate_development_plan_task.delay(str(p.id))
        return Response({"status": "Plan generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_mockups(self, request, pk=None):
        p = self.get_object()
        generate_mockups_task.delay(str(p.id))
        return Response({"status": "Mockup generation started"}, status=status.HTTP_202_ACCEPTED)


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.all()
    serializer_class = RequirementSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return Requirement.objects.all()
        if ManagerPermission().has_permission(self.request, self):
            return Requirement.objects.all()
        if ModeratorPermission().has_permission(self.request, self):
            return Requirement.objects.all()
        return Requirement.objects.filter(project__created_by=u)


class RequirementCommentViewSet(viewsets.ModelViewSet):
    queryset = RequirementComment.objects.all()
    serializer_class = RequirementCommentSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return RequirementComment.objects.all()
        if ManagerPermission().has_permission(self.request, self):
            return RequirementComment.objects.all()
        if ModeratorPermission().has_permission(self.request, self):
            return RequirementComment.objects.all()
        return RequirementComment.objects.filter(requirement__project__created_by=u)


class DevelopmentPlanViewSet(viewsets.ModelViewSet):
    queryset = DevelopmentPlan.objects.all()
    serializer_class = DevelopmentPlanSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    @action(detail=True, methods=["post"])
    def new_version(self, request, pk=None):
        plan = self.get_object()
        data = request.data
        dv = plan.versions.order_by("-version_number").first()
        nv = dv.version_number + 1 if dv else 1
        obj = DevelopmentPlanVersion.objects.create(
            plan=plan,
            version_number=nv,
            roles_and_hours=data.get("roles_and_hours", ""),
            estimated_cost=data.get("estimated_cost", 0),
            notes=data.get("notes", ""),
            created_by=request.user
        )
        plan.current_version_number = nv
        plan.save()
        s = DevelopmentPlanVersionSerializer(obj)
        return Response(s.data, status=status.HTTP_201_CREATED)


class DevelopmentPlanVersionViewSet(viewsets.ModelViewSet):
    queryset = DevelopmentPlanVersion.objects.all()
    serializer_class = DevelopmentPlanVersionSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return DevelopmentPlanVersion.objects.all()
        if ManagerPermission().has_permission(self.request, self):
            return DevelopmentPlanVersion.objects.all()
        if ModeratorPermission().has_permission(self.request, self):
            return DevelopmentPlanVersion.objects.all()
        return DevelopmentPlanVersion.objects.filter(plan__project__created_by=u)


class MockupViewSet(viewsets.ModelViewSet):
    queryset = Mockup.objects.all()
    serializer_class = MockupSerializer
    permission_classes = [IsAuthenticated, ManagerPermission | AdminPermission | ModeratorPermission]

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return Mockup.objects.all()
        if ManagerPermission().has_permission(self.request, self):
            return Mockup.objects.all()
        if ModeratorPermission().has_permission(self.request, self):
            return Mockup.objects.all()
        return Mockup.objects.filter(project__created_by=u)
