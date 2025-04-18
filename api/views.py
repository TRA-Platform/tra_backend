from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from webauth.permissions import AdminPermission, ManagerPermission, ModeratorPermission
from .models import (
    SrsTemplate, Project, Requirement, RequirementComment,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup, MockupHistory,
    UserStory, UserStoryComment, UserStoryHistory, UmlDiagram
)
from .serializers import (
    SrsTemplateSerializer, ProjectSerializer, RequirementSerializer, RequirementCommentSerializer,
    DevelopmentPlanSerializer, DevelopmentPlanVersionSerializer, MockupSerializer,
    UserStorySerializer, UserStoryCommentSerializer, UmlDiagramSerializer,
    ProjectListSerializer, RequirementDetailSerializer
)
from .tasks import (
    generate_requirements_task, export_srs_task, generate_development_plan_task,
    generate_mockups_task, generate_user_stories_task, generate_uml_diagrams_task
)


class SrsTemplateViewSet(viewsets.ModelViewSet):
    queryset = SrsTemplate.objects.all()
    serializer_class = SrsTemplateSerializer
    permission_classes = [IsAuthenticated, AdminPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'tags']

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        template = self.get_object()
        return Response({"preview": template.preview_image}, status=status.HTTP_200_OK)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'short_description', 'type_of_application', 'status']

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
        p.generation_status = "in_progress"
        p.generation_started_at = timezone.now()
        p.save()

        generate_requirements_task.delay(str(p.id))
        return Response({"status": "Requirements generation started"}, status=status.HTTP_202_ACCEPTED)

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
        return Response({"status": "SRS export started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_plan(self, request, pk=None):
        p = self.get_object()
        generate_development_plan_task.delay(str(p.id))
        return Response({"status": "Development plan generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_mockups(self, request, pk=None):
        p = self.get_object()
        generate_mockups_task.delay(str(p.id))
        return Response({"status": "Mockup generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_user_stories(self, request, pk=None):
        p = self.get_object()
        generate_user_stories_task.delay(str(p.id))
        return Response({"status": "User stories generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_uml_diagrams(self, request, pk=None):
        p = self.get_object()
        diagram_type = request.data.get("diagram_type", "class")
        generate_uml_diagrams_task.delay(str(p.id), diagram_type=diagram_type)
        return Response({"status": f"{diagram_type.capitalize()} diagram generation started"},
                        status=status.HTTP_202_ACCEPTED)


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.all()
    serializer_class = RequirementSerializer
    permission_classes = [IsAuthenticated, ModeratorPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'category', 'requirement_type', 'status']

    def get_queryset(self):
        queryset = Requirement.objects.all()

        # Filter by project ID if provided
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Filter by parent ID if provided
        parent_id = self.request.query_params.get('parent', None)
        if parent_id:
            if parent_id.lower() == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        # Filter by category if provided
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)

        # Filter by requirement_type if provided
        req_type = self.request.query_params.get('requirement_type', None)
        if req_type:
            queryset = queryset.filter(requirement_type=req_type)

        # Filter by status if provided
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            queryset = queryset.filter(project__created_by=u)

        return queryset

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return RequirementDetailSerializer
        return RequirementSerializer

    @action(detail=True, methods=["post"])
    def generate_user_stories(self, request, pk=None):
        requirement = self.get_object()
        generate_user_stories_task.delay(str(requirement.project.id), requirement_id=str(requirement.id))
        return Response({"status": "User stories generation started for this requirement"},
                        status=status.HTTP_202_ACCEPTED)


class UserStoryViewSet(viewsets.ModelViewSet):
    queryset = UserStory.objects.all()
    serializer_class = UserStorySerializer
    permission_classes = [IsAuthenticated, ModeratorPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['role', 'action', 'benefit', 'status']

    def get_queryset(self):
        queryset = UserStory.objects.all()

        # Filter by requirement ID if provided
        requirement_id = self.request.query_params.get('requirement', None)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)

        # Filter by status if provided
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            queryset = queryset.filter(requirement__project__created_by=u)

        return queryset

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        user_story = self.get_object()
        feedback = request.data.get("feedback", "")
        generate_user_stories_task.delay(
            str(user_story.requirement.project.id),
            requirement_id=str(user_story.requirement.id),
            user_story_id=str(user_story.id),
            feedback=feedback
        )
        return Response({"status": "User story regeneration started"}, status=status.HTTP_202_ACCEPTED)


class UserStoryCommentViewSet(viewsets.ModelViewSet):
    queryset = UserStoryComment.objects.all()
    serializer_class = UserStoryCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = UserStoryComment.objects.all()

        # Filter by user story ID if provided
        user_story_id = self.request.query_params.get('user_story', None)
        if user_story_id:
            queryset = queryset.filter(user_story_id=user_story_id)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            queryset = queryset.filter(user_story__requirement__project__created_by=u)

        return queryset


class RequirementCommentViewSet(viewsets.ModelViewSet):
    queryset = RequirementComment.objects.all()
    serializer_class = RequirementCommentSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated, ManagerPermission]

    def get_queryset(self):
        queryset = DevelopmentPlan.objects.all()

        # Filter by project ID if provided
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self)):
            queryset = queryset.filter(project__created_by=u)

        return queryset

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

    @action(detail=True, methods=["post"])
    def update_hourly_rates(self, request, pk=None):
        plan = self.get_object()
        hourly_rates = request.data.get("hourly_rates", {})
        plan.hourly_rates = hourly_rates
        plan.save()
        return Response({"status": "Hourly rates updated"}, status=status.HTTP_200_OK)


class DevelopmentPlanVersionViewSet(viewsets.ModelViewSet):
    queryset = DevelopmentPlanVersion.objects.all()
    serializer_class = DevelopmentPlanVersionSerializer
    permission_classes = [IsAuthenticated, ManagerPermission]

    def get_queryset(self):
        queryset = DevelopmentPlanVersion.objects.all()

        # Filter by plan ID if provided
        plan_id = self.request.query_params.get('plan', None)
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self)):
            queryset = queryset.filter(plan__project__created_by=u)

        return queryset


class UmlDiagramViewSet(viewsets.ModelViewSet):
    queryset = UmlDiagram.objects.all()
    serializer_class = UmlDiagramSerializer
    permission_classes = [IsAuthenticated, ModeratorPermission]

    def get_queryset(self):
        queryset = UmlDiagram.objects.all()

        # Filter by project ID if provided
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Filter by diagram type if provided
        diagram_type = self.request.query_params.get('diagram_type', None)
        if diagram_type:
            queryset = queryset.filter(diagram_type=diagram_type)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            queryset = queryset.filter(project__created_by=u)

        return queryset

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        diagram = self.get_object()
        generate_uml_diagrams_task.delay(
            str(diagram.project.id),
            diagram_type=diagram.diagram_type,
            diagram_id=str(diagram.id)
        )
        return Response({"status": "UML diagram regeneration started"}, status=status.HTTP_202_ACCEPTED)


class MockupViewSet(viewsets.ModelViewSet):
    queryset = Mockup.objects.all()
    serializer_class = MockupSerializer
    permission_classes = [IsAuthenticated, ModeratorPermission]

    def get_queryset(self):
        queryset = Mockup.objects.all()

        # Filter by project ID if provided
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Filter by requirement ID if provided
        requirement_id = self.request.query_params.get('requirement', None)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)

        # Filter by user story ID if provided
        user_story_id = self.request.query_params.get('user_story', None)
        if user_story_id:
            queryset = queryset.filter(user_story_id=user_story_id)

        # Apply user permissions
        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            queryset = queryset.filter(project__created_by=u)

        return queryset

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        mockup = self.get_object()
        feedback = request.data.get("feedback", "")

        if mockup.user_story:
            generate_mockups_task.delay(
                str(mockup.project.id),
                user_story_id=str(mockup.user_story.id),
                mockup_id=str(mockup.id),
                feedback=feedback
            )
        else:
            generate_mockups_task.delay(
                str(mockup.project.id),
                requirement_id=str(mockup.requirement.id) if mockup.requirement else None,
                mockup_id=str(mockup.id),
                feedback=feedback
            )

        return Response({"status": "Mockup regeneration started"}, status=status.HTTP_202_ACCEPTED)