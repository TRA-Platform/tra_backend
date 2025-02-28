import logging
import traceback

from celery import current_app

from celery import shared_task
from .models import WorkerTask, Project, Requirement, RequirementCategory, ProjectMockup
from django.utils import timezone
import time
import requests
import json

app = current_app._get_current_object()
logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3)
def generate_requirement_task(self, project_id, category_id):
    task_obj = WorkerTask.objects.create(
        task_type=WorkerTask.GENERATE_REQ,
        project_id=project_id,
        status=WorkerTask.STARTED,
        started_at=timezone.now()
    )

    try:
        project = Project.objects.get(id=project_id)
        category = RequirementCategory.objects.get(id=category_id)

        prompt = f"Generate {category.name} requirement for project: {project.name}\nDescription: {project.description}"

        response = requests.post(
            'https://api.llm-provider.com/generate',
            headers={'Authorization': 'Bearer API_KEY'},
            json={'prompt': prompt, 'max_tokens': 500},
            timeout=30
        )
        response.raise_for_status()

        generated_text = response.json()['choices'][0]['text']

        Requirement.objects.create(
            project=project,
            category=category,
            title=f"AI-Generated {category.name} Requirement",
            description=generated_text,
            ai_generated=True
        )

        task_obj.status = WorkerTask.SUCCESS
        task_obj.result = {'message': 'Requirement generated successfully'}
        task_obj.completed_at = timezone.now()
        task_obj.save()

        return str(task_obj.id)

    except Exception as e:
        task_obj.status = WorkerTask.FAILURE
        task_obj.error = str(e)
        task_obj.completed_at = timezone.now()
        task_obj.save()
        self.retry(countdown=2 ** self.request.retries)


@app.task(bind=True)
def process_srs_template_task(self, project_id):
    task_obj = WorkerTask.objects.create(
        task_type=WorkerTask.PROCESS_SRS,
        project_id=project_id,
        status=WorkerTask.STARTED,
        started_at=timezone.now()
    )

    try:
        project = Project.objects.get(id=project_id)
        requirements = project.requirement_set.all()

        srs_content = f"# {project.name} SRS Document\n\n"
        srs_content += f"## Requirements\n\n"

        for req in requirements:
            srs_content += f"### {req.title}\n{req.description}\n\n"

        project.template.content = srs_content
        project.template.save()

        task_obj.status = WorkerTask.SUCCESS
        task_obj.result = {'document_size': len(srs_content)}
        task_obj.completed_at = timezone.now()
        task_obj.save()

        return str(task_obj.id)

    except Exception as e:
        task_obj.status = WorkerTask.FAILURE
        task_obj.error = str(e)
        task_obj.completed_at = timezone.now()
        task_obj.save()
        raise e


@app.task(bind=True)
def generate_mockup_task(project_id):
    task_obj = WorkerTask.objects.create(
        task_type=WorkerTask.GENERATE_MOCKUP,
        project_id=project_id,
        status=WorkerTask.STARTED,
        started_at=timezone.now()
    )

    try:
        project = Project.objects.get(id=project_id)
        html_content = "<!DOCTYPE html><html><body><h1>Generated Mockup</h1></body></html>"

        if hasattr(project, 'projectmockup'):
            mockup = project.projectmockup
            mockup.html_content = html_content
        else:
            mockup = ProjectMockup(project=project, html_content=html_content)

        mockup.save()

        task_obj.status = WorkerTask.SUCCESS
        task_obj.result = {'html_size': len(html_content)}
        task_obj.completed_at = timezone.now()
        task_obj.save()

        return str(task_obj.id)

    except Exception as e:
        task_obj.status = WorkerTask.FAILURE
        task_obj.error = str(e)
        task_obj.completed_at = timezone.now()
        task_obj.save()
        raise e
