import json
import logging

from celery import current_app
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Project, Requirement, RequirementHistory,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup, SrsExport, REQUIREMENT_CATEGORY_CHOICES,
    REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL, REQUIREMENT_CATEGORY_UIUX,
    REQUIREMENT_CATEGORY_OTHER, STATUS_DRAFT, STATUS_ARCHIVED
)
from gpt.adapter import GptClient

app = current_app._get_current_object()
logger = logging.getLogger(__name__)


@app.task
def generate_requirements_task(project_id):
    logger.error(f"Generating requirements for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}
    available_categories = "|".join([
        REQUIREMENT_CATEGORY_FUNCTIONAL,
        REQUIREMENT_CATEGORY_NONFUNCTIONAL,
        REQUIREMENT_CATEGORY_UIUX,
        REQUIREMENT_CATEGORY_OTHER,
    ])
    prompt = (
        f"Project Name: {project.name}\n"
        f"Short Description: {project.short_description}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Additional: {project.additional_requirements}\n"
        f"NonFunctional: {project.non_functional_requirements}\n"
        f"TechStack: {project.technology_stack}\n"
        f"OS: {project.operating_system}\n"
        f"TargetUsers: {project.target_users}\n"
        f"PriorityModules: {project.priority_modules}\n"
        "Please produce a JSON with the following structure:\n"
        "{\n"
        "  \"requirements\": [\n"
        "    {\n"
        "      \"title\": \"...\",\n"
        "      \"description\": \"...\",\n"
        f"      \"category\": {available_categories},\n"
        "      \"suggested_status\": ,\n"
        "    },\n"
        "    ...\n"
        "  ],\n"
        f"{{'requirements': [{{'title': '...', 'description': '...', 'category': '...', 'suggested_status': '...'}}]}}"
    )
    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)
    if "error" in resp:
        return {"error": "Failed to generate", "detail": resp}
    data = resp.get("data") or resp.get("answer") or resp
    data = json.loads(data).get("requirements")
    logger.error(f"{data}")
    if not isinstance(data, list):
        return {"error": "Invalid GPT format", "detail": data}
    new_ids = []
    current_requirements = Requirement.objects.filter(
        project_id=project_id,
    )
    current_requirements.update(
        status=STATUS_ARCHIVED,
    )
    for item in data:
        t = item.get("title", "Untitled")
        d = item.get("description", "")
        c = item.get("category", REQUIREMENT_CATEGORY_FUNCTIONAL)
        r = Requirement.objects.create(
            project=project,
            title=t,
            description=d,
            category=c,
        )
        new_ids.append(str(r.id))
    return {"created_requirements": new_ids}


@app.task
def export_srs_task(project_id, created_by, fmt="pdf"):
    logger.error(f"Exporting SRS for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}
    export = SrsExport.objects.create(
        project=project,
        template_id=project.srs_template_id,
        fmt=fmt,
        created_by_id=created_by,
    )
    reqs = project.requirements.all().order_by("created_at")
    content = f"# SRS for {project.name}\n\n"
    content += f"**Short Description:** {project.short_description}\n\n"
    content += f"**Application Type:** {project.type_of_application}\n\n"
    content += f"**Language:** {project.language}\n\n"
    content += "## Requirements\n\n"
    for r in reqs:
        content += f"### {r.title}\n"
        content += f"- Category: **{r.category}**\n"
        content += f"- Status: **{r.status}**\n"
        content += f"- Description:\n\n```\n{r.description}\n```\n\n"
    export.content = content
    export.save()
    return {"success": True, "format": fmt, "markdown_content": content}


@app.task
def generate_development_plan_task(project_id):
    logger.error(f"Generating development plan for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    reqs = project.requirements.all()
    prompt_data = []
    for r in reqs:
        prompt_data.append({"title": r.title, "category": r.category, "description": r.description})

    prompt = (
        f"Project Name: {project.name}\n"
        f"Short Description: {project.short_description}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Additional: {project.additional_requirements}\n"
        f"NonFunctional: {project.non_functional_requirements}\n"
        f"TechStack: {project.technology_stack}\n"
        f"OS: {project.operating_system}\n"
        f"TargetUsers: {project.target_users}\n"
        f"PriorityModules: {project.priority_modules}\n"
        f"Preliminary budget: {project.preliminary_budget}\n"
        f"Deadline: {project.deadline}\n"
        f"Requirements: {prompt_data}\n"
        f"Generate a development plan in JSON with:\n"
        f"- 'roles_hours': an array of {{role, hours, cost}}\n"
        f"- 'notes': a summary\n"
        f"Base your plan on the above requirements."
    )
    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)
    if code != 200 or "error" in resp:
        return {"error": "Failed to generate plan", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    data = json.loads(data)
    logger.error(f"Dev plan {data}")
    if not isinstance(data, dict):
        return {"error": "Invalid GPT plan format", "detail": data}
    logger.error(f"Dev plan {data}")
    plan, _ = DevelopmentPlan.objects.get_or_create(project=project)
    last = plan.versions.order_by("-version_number").first()
    nv = last.version_number + 1 if last else 1

    roles_hours = data.get("roles_hours", [])
    notes = data.get("notes", "")
    total_cost = 0
    for item in roles_hours:
        c = item.get("cost", 0)
        try:
            total_cost += float(c)
        except:
            total_cost += 0

    dv = DevelopmentPlanVersion.objects.create(
        plan=plan,
        version_number=nv,
        roles_and_hours=str(roles_hours),
        estimated_cost=total_cost,
        notes=notes
    )
    plan.current_version_number = nv
    plan.save()

    return {"plan_version": dv.id, "roles_hours": roles_hours, "notes": notes}


@app.task
def generate_mockups_task(project_id):
    logger.error(f"Generating mockups for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    reqs = project.requirements.all()
    req_list = []
    for r in reqs:
        req_list.append({"id": str(r.id), "title": r.title, "description": r.description})

    prompt = (
        f"Project Name: {project.name}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Color Scheme: {project.color_scheme}\n"
        f"Requirements:\n{req_list}\n"
        f"Generate HTML mockups for the following requirement. Use tailwind, make it beautiful."
        f"Return JSON with 'screens': an array of {{'requirement_id': '...', 'name': '...', 'html': '...'}}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-3.5-turbo", is_json=True)
    if code != 200 or "error" in resp:
        return {"error": "Failed to generate mockups", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    data = json.loads(data)
    if not isinstance(data, dict):
        return {"error": "Invalid format", "detail": data}

    screens = data.get("screens", [])
    created = []
    for s in screens:
        rid = s.get("requirement_id")
        try:
            requirement = Requirement.objects.get(id=rid, project=project)
        except Requirement.DoesNotExist:
            requirement = None

        mk = Mockup.objects.create(
            project=project,
            requirement=requirement,
            name=s.get("name", "Untitled Mockup"),
            html_content=s.get("html", "")
        )
        created.append(str(mk.id))

    return {"generated_mockups": created}
