from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from webauth.permissions import AdminPermission, ManagerPermission, ModeratorPermission, ProjectPermission
from .models import (
    SrsTemplate, Project, Requirement, RequirementComment,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup, MockupHistory,
    UserStory, UserStoryComment, UserStoryHistory, UmlDiagram, UML_DIAGRAM_TYPE_CHOICES, SRS_FORMAT_PDF,
    SRS_FORMAT_MARKDOWN, RequirementHistory, GENERATION_STATUS_PENDING, STATUS_ACTIVE, GENERATION_STATUS_IN_PROGRESS,
    STATUS_COMPLETED, GENERATION_STATUS_COMPLETED
)
from webauth.models import ProjectRole
from .serializers import (
    SrsTemplateSerializer, ProjectSerializer, RequirementSerializer, RequirementCommentSerializer,
    DevelopmentPlanSerializer, DevelopmentPlanVersionSerializer, MockupSerializer,
    UserStorySerializer, UserStoryCommentSerializer, UmlDiagramSerializer,
    ProjectListSerializer, RequirementDetailSerializer
)
from .tasks import (
    generate_requirements_task, export_srs_task, generate_development_plan_task,
    generate_mockups_task, generate_user_stories_task, generate_uml_diagrams_task, logger,
)
from django.db.models import Count, Q, F, Value, CharField
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User


class SrsTemplateViewSet(viewsets.ModelViewSet):
    queryset = SrsTemplate.objects.all()
    serializer_class = SrsTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'tags']

    def get_queryset(self):
        return SrsTemplate.objects.all()

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        template = self.get_object()
        return Response({"preview": template.preview_image}, status=status.HTTP_200_OK)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'short_description', 'type_of_application', 'status']

    def get_queryset(self):
        u = self.request.user

        if self.action == "list":
            base_queryset = Project.objects.select_related('created_by')
        else:
            base_queryset = Project.objects.select_related(
                'created_by',
                'srs_template',
                'development_plan'
            ).prefetch_related(
                'requirements__parent',
                'requirements__children',
                'requirements__user_stories__history__changed_by',
                'requirements__user_stories__comments__user',
                'requirements__user_stories__mockups',
                'requirements__mockups__created_by',
                'requirements__history__changed_by',
                'requirements__comments__user',
                'requirements__comments__responsible_user',
                'mockups__requirement',
                'mockups__user_story',
                'mockups__created_by',
                'uml_diagrams__plan_version',
                'exports__created_by',
                'exports__template',
                'roles__user',
                'development_plan__versions'
            )

        if u.is_superuser or AdminPermission().has_permission(self.request, self):
            return base_queryset
        if ManagerPermission().has_permission(self.request, self):
            return base_queryset
        if ModeratorPermission().has_permission(self.request, self):
            return base_queryset

        user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
        return (base_queryset.filter(id__in=list(user_projects)) |
                base_queryset.filter(created_by=u))

    def get_serializer_class(self):
        if self.action == "list":
            return ProjectListSerializer
        return ProjectSerializer

    def retrieve(self, request, pk=None, **kwargs):
        project_data = get_optimized_project_data(str(pk), request.user)
        return Response(project_data)

    @action(detail=True, methods=["get"])
    def optimized_data(self, request, pk=None):
        project_data = get_optimized_project_data(str(pk), request.user)

        if not project_data:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(project_data)

    @action(detail=True, methods=["post"])
    def generate_requirements(self, request, pk=None):
        p = self.get_object()
        p.generation_status = GENERATION_STATUS_IN_PROGRESS
        p.generation_started_at = timezone.now()
        p.save()

        generate_requirements_task.delay(str(p.id))
        return Response({"status": "Requirements generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def export_srs(self, request, pk=None):
        u = request.user
        p = self.get_object()
        fmt = request.data.get("format", SRS_FORMAT_MARKDOWN)
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
        requirement_id = request.data.get("requirement_id", None)
        generate_user_stories_task.delay(str(p.id), requirement_id)
        return Response({"status": "User stories generation started"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def generate_uml_diagrams(self, request, pk=None):
        p = self.get_object()
        diagram_type = request.data.get("diagram_type", None)
        if diagram_type:
            diagram_types = [diagram_type]
        else:
            diagram_types = [dt[0] for dt in UML_DIAGRAM_TYPE_CHOICES]
        for diagram_type in diagram_types:
            if diagram_type not in dict(UML_DIAGRAM_TYPE_CHOICES).keys():
                return Response({"error": f"Invalid diagram type: {diagram_type}"}, status=status.HTTP_400_BAD_REQUEST)
        for diagram_type in diagram_types:
            task_id = generate_uml_diagrams_task.delay(str(p.id), diagram_type=diagram_type)
            logger.info(f"Started task {task_id} for diagram type {diagram_type} for project {p.id}")
        return Response({"status": f"{diagram_type.capitalize()} diagram generation started"},
                        status=status.HTTP_202_ACCEPTED)


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.all()
    serializer_class = RequirementSerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'category', 'requirement_type', 'status']

    def get_queryset(self):
        queryset = Requirement.objects.select_related('project', 'parent').prefetch_related(
            'user_stories__history__changed_by',
            'user_stories__comments__user',
            'user_stories__mockups',
            'history__changed_by',
            'comments__user',
            'comments__responsible_user',
            'children',
            'mockups'
        )

        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        parent_id = self.request.query_params.get('parent', None)
        if parent_id:
            if parent_id.lower() == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        req_type = self.request.query_params.get('requirement_type', None)
        if req_type:
            queryset = queryset.filter(requirement_type=req_type)
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(project__id__in=list(user_projects)) | queryset.filter(project__created_by=u)

        return queryset

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return RequirementDetailSerializer
        return RequirementSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        user = request.user
        RequirementHistory.objects.create(
            requirement=instance,
            title=instance.title,
            description=instance.description,
            category=instance.category,
            requirement_type=instance.requirement_type,
            version_number=instance.version_number,
            changed_by=user,
            status=instance.status
        )

        instance.version_number += 1
        mockups = Mockup.objects.filter(requirement=instance)
        for mockup in mockups:
            mockup.needs_regeneration = True
            mockup.last_associated_change = timezone.now()
            mockup.save()
            generate_mockups_task.delay(
                str(mockup.project.id),
                requirement_id=str(mockup.requirement.id),
                mockup_id=str(mockup.id)
            )

        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_user_stories(self, request, pk=None):
        requirement = self.get_object()
        generate_user_stories_task.delay(str(requirement.project.id), requirement_id=str(requirement.id))
        return Response({"status": "User stories generation started for this requirement"},
                        status=status.HTTP_202_ACCEPTED)


class UserStoryViewSet(viewsets.ModelViewSet):
    queryset = UserStory.objects.all()
    serializer_class = UserStorySerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['role', 'action', 'benefit', 'status']

    def get_queryset(self):
        queryset = UserStory.objects.select_related(
            'requirement',
            'requirement__project'
        ).prefetch_related(
            'comments__user',
            'history__changed_by',
            'mockups'
        )

        requirement_id = self.request.query_params.get('requirement', None)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(requirement__project__id__in=list(user_projects)) | queryset.filter(
                requirement__project__created_by=u)

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
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = UserStoryComment.objects.select_related('user_story', 'user', 'user_story__requirement',
                                                           'user_story__requirement__project').all()
        user_story_id = self.request.query_params.get('user_story', None)
        if user_story_id:
            queryset = queryset.filter(user_story_id=user_story_id)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(user_story__requirement__project__id__in=list(user_projects)) | queryset.filter(
                user_story__requirement__project__created_by=u)

        return queryset


class RequirementCommentViewSet(viewsets.ModelViewSet):
    queryset = RequirementComment.objects.all()
    serializer_class = RequirementCommentSerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = RequirementComment.objects.select_related('requirement', 'user', 'responsible_user',
                                                             'requirement__project').all()
        requirement_id = self.request.query_params.get('requirement', None)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(requirement__project__id__in=list(user_projects)) | queryset.filter(
                requirement__project__created_by=u)

        return queryset


class DevelopmentPlanViewSet(viewsets.ModelViewSet):
    queryset = DevelopmentPlan.objects.all()
    serializer_class = DevelopmentPlanSerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = DevelopmentPlan.objects.select_related('project', 'project__created_by').prefetch_related(
            'versions').all()
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(project__id__in=list(user_projects)) | queryset.filter(project__created_by=u)

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
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = DevelopmentPlanVersion.objects.select_related('plan', 'plan__project',
                                                                 'created_by').prefetch_related('uml_diagrams').all()
        plan_id = self.request.query_params.get('plan', None)
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(plan__project__id__in=list(user_projects)) | queryset.filter(
                plan__project__created_by=u)

        return queryset


class UmlDiagramViewSet(viewsets.ModelViewSet):
    queryset = UmlDiagram.objects.all()
    serializer_class = UmlDiagramSerializer
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = UmlDiagram.objects.select_related('project', 'plan_version').all()
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        diagram_type = self.request.query_params.get('diagram_type', None)
        if diagram_type:
            queryset = queryset.filter(diagram_type=diagram_type)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(project__id__in=list(user_projects)) | queryset.filter(project__created_by=u)

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
    permission_classes = [IsAuthenticated,
                          ProjectPermission | ModeratorPermission | ManagerPermission | AdminPermission]

    def get_queryset(self):
        queryset = Mockup.objects.select_related('project', 'requirement', 'user_story', 'created_by').all()
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        requirement_id = self.request.query_params.get('requirement', None)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)
        user_story_id = self.request.query_params.get('user_story', None)
        if user_story_id:
            queryset = queryset.filter(user_story_id=user_story_id)

        u = self.request.user
        if not (u.is_superuser or AdminPermission().has_permission(self.request, self) or
                ManagerPermission().has_permission(self.request, self) or
                ModeratorPermission().has_permission(self.request, self)):
            user_projects = ProjectRole.objects.filter(user=u).values_list('project_id', flat=True)
            queryset = queryset.filter(project__id__in=list(user_projects)) | queryset.filter(project__created_by=u)

        return queryset

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        feedback = request.data.get("feedback", "")
        mockup = self.get_object()
        mockup.generation_status = GENERATION_STATUS_PENDING
        mockup.generation_started_at = timezone.now()
        mockup.generation_completed_at = None
        mockup.generation_error = ''
        mockup.needs_regeneration = False
        mockup.save()
        generate_mockups_task.delay(str(mockup.project_id), mockup_id=str(mockup.id), feedback=feedback)

        return Response(self.get_serializer(mockup).data)

    @action(detail=False, methods=['post'])
    def regenerate_all(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return Response(
                {'error': 'project_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        mockups = Mockup.objects.filter(
            project_id=project_id,
            status=STATUS_ACTIVE,
            needs_regeneration=True
        )
        for mockup in mockups:
            mockup.generation_status = GENERATION_STATUS_PENDING
            mockup.generation_started_at = timezone.now()
            mockup.generation_completed_at = None
            mockup.generation_error = ''
            mockup.needs_regeneration = False
            mockup.save()
            generate_mockups_task.delay(str(mockup.project_id), mockup_id=mockup.id)

        return Response(self.get_serializer(mockups, many=True).data)


def get_optimized_project_data(project_id, user):
    project = Project.objects.filter(id=project_id).select_related(
        'created_by',
        'srs_template',
        'development_plan'
    ).first()

    if not project:
        return None

    requirements = Requirement.objects.filter(project=project).annotate(
        user_stories_count=Count('user_stories'),
        mockups_count=Count('mockups'),
        comments_count=Count('comments')
    ).select_related(
        'parent'
    ).prefetch_related(
        'children',
        'user_stories',
        'mockups',
        'comments'
    )
    user_stories = UserStory.objects.filter(
        requirement__project=project
    ).select_related(
        'requirement'
    ).prefetch_related(
        'mockups',
        'comments'
    )
    mockups = Mockup.objects.filter(
        project=project
    ).select_related(
        'requirement',
        'user_story',
        'created_by'
    )
    uml_diagrams = UmlDiagram.objects.filter(
        project=project
    ).select_related(
        'plan_version'
    )
    development_plan = DevelopmentPlan.objects.filter(
        project=project
    ).prefetch_related(
        'versions'
    ).first()

    roles = ProjectRole.objects.filter(
        project=project
    ).select_related(
        'user'
    )

    def to_timestamp(dt):
        if dt is None:
            return None
        return int(dt.timestamp() * 1000)

    project_data = {
        'id': str(project.id),
        'name': project.name,
        'short_description': project.short_description,
        'type_of_application': project.type_of_application,
        'color_scheme': project.color_scheme,
        'language': project.language,
        'application_description': project.application_description,
        'target_users': project.target_users,
        'additional_requirements': project.additional_requirements,
        'non_functional_requirements': project.non_functional_requirements,
        'technology_stack': project.technology_stack,
        'operating_systems': project.operating_systems,
        'priority_modules': project.priority_modules,
        'deadline_start': to_timestamp(project.deadline_start),
        'deadline_end': to_timestamp(project.deadline_end),
        'preliminary_budget': project.preliminary_budget,
        'scope': project.scope,
        'generation_status': project.generation_status,
        'generation_started_at': to_timestamp(project.generation_started_at),
        'generation_completed_at': to_timestamp(project.generation_completed_at),
        'generation_error': project.generation_error,
        'status': project.status,
        'created_at': to_timestamp(project.created_at),
        'updated_at': to_timestamp(project.updated_at),
        'created_by': {
            'id': project.created_by.id,
            'username': project.created_by.username,
            'email': project.created_by.email,
            'first_name': project.created_by.first_name,
            'last_name': project.created_by.last_name,
        },
        'requirements_total': project.requirements_total,
        'requirements_completed': project.requirements_completed,
        'user_stories_total': project.user_stories_total,
        'user_stories_completed': project.user_stories_completed,
        'mockups_total': project.mockups_total,
        'mockups_completed': project.mockups_completed,
        'uml_diagrams_total': project.uml_diagrams_total,
        'uml_diagrams_completed': project.uml_diagrams_completed,
        'requirements': [{
            'id': str(req.id),
            'title': req.title,
            'handle': req.handle,
            'description': req.description,
            'category': req.category,
            'requirement_type': req.requirement_type,
            'version_number': req.version_number,
            'status': req.status,
            'created_at': to_timestamp(req.created_at),
            'updated_at': to_timestamp(req.updated_at),
            'parent_id': str(req.parent.id) if req.parent else None,
            'user_stories_count': req.user_stories_count,
            'mockups_count': req.mockups_count,
            'comments_count': req.comments_count,
            'mockups': [{
                'id': str(m.id),
                'name': m.name,
                'image': m.image,
                'requirement_id': str(m.requirement.id) if m.requirement else None,
                'user_story_id': str(m.user_story.id) if m.user_story else None,
                'version_number': m.version_number,
                'generation_status': m.generation_status,
                'status': m.status,
                'created_at': to_timestamp(m.created_at),
                'updated_at': to_timestamp(m.updated_at),
            } for m in filter(lambda x: x.requirement_id == req.id, mockups)],
            'user_stories': [{
                'id': str(us.id),
                'requirement_id': str(us.requirement.id),
                'role': us.role,
                'action': us.action,
                'benefit': us.benefit,
                'acceptance_criteria': us.acceptance_criteria,
                'version_number': us.version_number,
                'generation_status': us.generation_status,
                'status': us.status,
                'created_at': to_timestamp(us.created_at),
                'updated_at': to_timestamp(us.updated_at),
            } for us in filter(lambda x: x.requirement_id == req.id, user_stories)],
        } for req in requirements],
        'user_stories': [{
            'id': str(us.id),
            'requirement_id': str(us.requirement.id),
            'role': us.role,
            'action': us.action,
            'benefit': us.benefit,
            'acceptance_criteria': us.acceptance_criteria,
            'version_number': us.version_number,
            'generation_status': us.generation_status,
            'status': us.status,
            'created_at': to_timestamp(us.created_at),
            'updated_at': to_timestamp(us.updated_at),
        } for us in user_stories],
        'mockups': [{
            'id': str(m.id),
            'name': m.name,
            'image': m.image,
            'requirement_id': str(m.requirement.id) if m.requirement else None,
            'user_story_id': str(m.user_story.id) if m.user_story else None,
            'version_number': m.version_number,
            'generation_status': m.generation_status,
            'status': m.status,
            'created_at': to_timestamp(m.created_at),
            'updated_at': to_timestamp(m.updated_at),
        } for m in mockups],
        'uml_diagrams': [{
            'id': str(d.id),
            'name': d.name,
            'diagram_type': d.diagram_type,
            'content': d.content,
            'notes': d.notes,
            'generation_status': d.generation_status,
            'status': d.status,
            'created_at': to_timestamp(d.created_at),
            'updated_at': to_timestamp(d.updated_at),
        } for d in uml_diagrams],
        'development_plan': {
            'id': str(development_plan.id),
            'current_version_number': development_plan.current_version_number,
            'hourly_rates': development_plan.hourly_rates,
            'status': development_plan.status,
            'versions': [{
                'id': str(v.id),
                'version_number': v.version_number,
                'roles_and_hours': v.roles_and_hours,
                'estimated_cost': v.estimated_cost,
                'notes': v.notes,
                'status': v.status,
                'created_at': to_timestamp(v.created_at),
            } for v in development_plan.versions.all()] if development_plan else [],
        } if development_plan else None,
        'roles': [{
            'id': str(r.id),
            'user': {
                'id': r.user.id,
                'username': r.user.username,
                'email': r.user.email,
            },
            'role': r.role,
        } for r in roles],
    }

    return project_data
