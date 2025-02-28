import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import *
from .serializers import *
from .tasks import *

logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        elif self.action == 'create':
            return ProjectCreateSerializer
        return ProjectDetailSerializer

    @action(detail=True, methods=['post'])
    def generate_requirements(self, request, pk=None):
        project = self.get_object()
        try:
            for category in RequirementCategory.objects.all():
                generate_requirement_task.delay(project.id, category.id)
            logger.info(f"Started requirement generation for project {project.id}")
            return Response({'status': 'Requirements generation started'})
        except Exception as e:
            logger.error(f"Error starting requirement generation: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return RequirementListSerializer
        elif self.action == 'create':
            return RequirementCreateSerializer
        return RequirementDetailSerializer

    def perform_create(self, serializer):
        requirement = serializer.save()
        logger.info(f"Created new requirement {requirement.id}")
        RequirementChangeLog.objects.create(
            requirement=requirement,
            user=self.request.user,
            old_value='',
            new_value=serializer.data
        )


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        logger.info(f"User {self.request.user.id} added comment {comment.id}")


class WorkerTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkerTask.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkerTaskListSerializer
        return WorkerTaskDetailSerializer

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        task = self.get_object()
        if task.status == WorkerTask.FAILURE:
            if task.task_type == WorkerTask.GENERATE_REQ:
                generate_requirement_task.delay(task.project_id, task.requirement.category_id)
            elif task.task_type == WorkerTask.GENERATE_MOCKUP:
                generate_mockup_task.delay(task.project_id)
            elif task.task_type == WorkerTask.PROCESS_SRS:
                process_srs_template_task.delay(task.project_id)
            task.status = WorkerTask.PENDING
            task.save()
            logger.info(f"Retrying task {task.id}")
            return Response({'status': 'Task retried'})
        return Response({'error': 'Task cannot be retried'}, status=status.HTTP_400_BAD_REQUEST)
