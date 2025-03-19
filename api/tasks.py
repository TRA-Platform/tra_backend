import json
import logging
from django.utils import timezone
from django.contrib.auth.models import User
from celery import current_app
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Project, Requirement, RequirementHistory,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup, SrsExport, REQUIREMENT_CATEGORY_CHOICES,
    REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL, REQUIREMENT_CATEGORY_UIUX,
    REQUIREMENT_CATEGORY_OTHER, STATUS_DRAFT, STATUS_ARCHIVED, STATUS_ACTIVE
)
from gpt.adapter import GptClient

app = current_app._get_current_object()
logger = logging.getLogger(__name__)


@app.task
def generate_requirements_task(project_id, user_id=None):
    """
    Generate requirements for a project using GPT-4o.
    Records proper history of requirement changes.

    Args:
        project_id: ID of the project to generate requirements for
        user_id: Optional user ID that initiated the request (for attribution)
    """
    logger.error(f"Generating requirements for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for attribution")
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
        f"Additional Requirements: {project.additional_requirements}\n"
        f"Non-Functional Requirements: {project.non_functional_requirements}\n"
        f"Technology Stack: {project.technology_stack}\n"
        f"Operating System: {project.operating_system}\n"
        f"Target Users: {project.target_users}\n"
        f"Priority Modules: {project.priority_modules}\n\n"
        f"Task: Generate comprehensive software requirements for this project.\n\n"
        f"Guidelines:\n"
        f"1. Create at least 20-30 well-defined requirements\n"
        f"2. Requirements should be specific, measurable, and testable\n"
        f"3. Use clear language and avoid ambiguity\n"
        f"4. Cover both functional and non-functional aspects\n"
        f"5. Ensure requirements are traceable\n"
        f"6. Cover all priority modules mentioned\n"
        f"7. Include UI/UX requirements if applicable\n"
        f"8. Consider security, performance, and scalability\n\n"
        f"Output requirements as JSON with the following structure:\n"
        "{\n"
        "  \"requirements\": [\n"
        "    {\n"
        "      \"title\": \"Short, descriptive title\",\n"
        "      \"description\": \"Detailed requirement description with acceptance criteria\",\n"
        f"      \"category\": One of [{available_categories}],\n"
        "      \"suggested_status\": \"draft\"\n"
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)
    if "error" in resp:
        return {"error": "Failed to generate requirements", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    try:
        parsed_data = json.loads(data) if isinstance(data, str) else data
        requirements = parsed_data.get("requirements", [])
    except (json.JSONDecodeError, AttributeError):
        return {"error": "Invalid response format from GPT", "detail": data}

    if not isinstance(requirements, list) or not requirements:
        return {"error": "No valid requirements generated", "detail": data}

    logger.error(f"Generated {len(requirements)} requirements for project {project_id}")

    current_requirements = Requirement.objects.filter(
        project_id=project_id,
        status__in=[STATUS_DRAFT, STATUS_ACTIVE]
    )

    for req in current_requirements:
        RequirementHistory.objects.create(
            requirement=req,
            title=req.title,
            description=req.description,
            category=req.category,
            version_number=req.version_number,
            changed_by=user,
            status=req.status,
            changed_at=timezone.now()
        )

    current_requirements.update(status=STATUS_ARCHIVED)

    new_ids = []
    for item in requirements:
        title = item.get("title", "Untitled")
        description = item.get("description", "")
        category = item.get("category", REQUIREMENT_CATEGORY_FUNCTIONAL)

        if category not in [REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL,
                            REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_OTHER]:
            category = REQUIREMENT_CATEGORY_FUNCTIONAL

        new_req = Requirement.objects.create(
            project=project,
            title=title,
            description=description,
            category=category,
            status=STATUS_DRAFT,
            version_number=1
        )

        RequirementHistory.objects.create(
            requirement=new_req,
            title=new_req.title,
            description=new_req.description,
            category=new_req.category,
            version_number=new_req.version_number,
            changed_by=user,
            status=new_req.status,
            changed_at=timezone.now()
        )

        new_ids.append(str(new_req.id))

    return {"created_requirements": new_ids, "count": len(new_ids)}


@app.task
def export_srs_task(project_id, created_by=None, fmt="pdf"):
    """
    Export a Software Requirements Specification (SRS) document for a project.

    Args:
        project_id: ID of the project
        created_by: User ID who initiated the export
        fmt: Format of the export (pdf, docx, html, md)
    """
    logger.error(f"Exporting SRS for project {project_id} in {fmt} format")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    export = SrsExport.objects.create(
        project=project,
        template_id=project.srs_template_id,
        fmt=fmt,
        created_by_id=created_by,
        status=STATUS_ACTIVE
    )

    reqs = project.requirements.filter(
        status__in=[STATUS_ACTIVE, STATUS_DRAFT]
    ).order_by('category', 'created_at')

    content = f"# Software Requirements Specification for {project.name}\n\n"
    content += f"## 1. Introduction\n\n"
    content += f"### 1.1 Project Overview\n\n"
    content += f"{project.short_description}\n\n"
    content += f"### 1.2 Document Purpose\n\n"
    content += f"This Software Requirements Specification (SRS) document describes the functional and non-functional requirements for the {project.name} project. It is intended to be used by the development team to implement the software system.\n\n"

    content += f"## 2. General Description\n\n"
    content += f"### 2.1 Product Perspective\n\n"
    content += f"**Application Type:** {project.type_of_application}\n\n"
    content += f"**Primary Language:** {project.language}\n\n"

    if project.target_users:
        content += f"### 2.2 User Classes and Characteristics\n\n"
        content += f"{project.target_users}\n\n"

    if project.technology_stack:
        content += f"### 2.3 Technology Stack\n\n"
        content += f"{project.technology_stack}\n\n"

    if project.operating_system:
        content += f"### 2.4 Operating Environment\n\n"
        content += f"{project.operating_system}\n\n"

    content += f"## 3. Specific Requirements\n\n"

    categories = {
        REQUIREMENT_CATEGORY_FUNCTIONAL: "Functional Requirements",
        REQUIREMENT_CATEGORY_NONFUNCTIONAL: "Non-Functional Requirements",
        REQUIREMENT_CATEGORY_UIUX: "UI/UX Requirements",
        REQUIREMENT_CATEGORY_OTHER: "Other Requirements"
    }

    grouped_reqs = {}
    for cat, cat_name in categories.items():
        grouped_reqs[cat] = list(reqs.filter(category=cat))

    section_num = 1
    for cat, cat_name in categories.items():
        if grouped_reqs[cat]:
            content += f"### 3.{section_num} {cat_name}\n\n"
            section_num += 1

            for i, r in enumerate(grouped_reqs[cat], 1):
                content += f"**REQ-{cat[:3].upper()}-{i:03d}: {r.title}**\n\n"
                content += f"*Status:* {r.status}\n\n"
                content += f"*Description:*\n\n{r.description}\n\n"
                content += f"*Version:* {r.version_number}\n\n"
                content += "---\n\n"

    if project.additional_requirements:
        content += f"## 4. Additional Requirements\n\n"
        content += f"{project.additional_requirements}\n\n"

    if project.non_functional_requirements:
        content += f"## 5. Non-Functional Constraints\n\n"
        content += f"{project.non_functional_requirements}\n\n"

    if project.priority_modules:
        content += f"## 6. Priority Modules\n\n"
        content += f"{project.priority_modules}\n\n"

    export.content = content
    export.save()

    return {"success": True, "format": fmt, "export_id": str(export.id)}


@app.task
def generate_development_plan_task(project_id, user_id=None):
    """
    Generate a development plan for a project based on its requirements.

    Args:
        project_id: ID of the project
        user_id: Optional user ID that initiated the request (for attribution)
    """
    logger.error(f"Generating development plan for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for attribution")
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    reqs = project.requirements.filter(status__in=[STATUS_ACTIVE, STATUS_DRAFT])
    if not reqs.exists():
        return {"error": "No active or draft requirements found for this project"}

    prompt_data = []
    for r in reqs:
        prompt_data.append({
            "id": str(r.id),
            "title": r.title,
            "category": r.category,
            "description": r.description
        })

    prompt = (
        f"Project Name: {project.name}\n"
        f"Short Description: {project.short_description}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Technology Stack: {project.technology_stack}\n"
        f"Operating System: {project.operating_system}\n"
        f"Target Users: {project.target_users}\n"
        f"Priority Modules: {project.priority_modules}\n"
        f"Preliminary Budget: {project.preliminary_budget if project.preliminary_budget else 'Not specified'}\n"
        f"Deadline: {project.deadline.strftime('%Y-%m-%d') if project.deadline else 'Not specified'}\n\n"
        f"Requirements ({len(prompt_data)}):\n"
        f"{json.dumps(prompt_data, indent=2)}\n\n"
        f"Task: Create a detailed development plan for this project based on the provided requirements.\n\n"
        f"Guidelines:\n"
        f"1. Break down the work by appropriate roles (developers, designers, QA, etc.)\n"
        f"2. Estimate hours for each role based on the complexity of requirements\n"
        f"3. Determine a reasonable hourly cost for each role\n"
        f"4. Provide a comprehensive plan that covers all phases of development\n"
        f"5. Include time for planning, development, testing, and deployment\n"
        f"6. Consider dependencies between requirements\n"
        f"7. Account for project management overhead\n"
        f"8. Be realistic about timelines and costs\n\n"
        f"Output your development plan as JSON with the following structure:\n"
        "{\n"
        "  \"roles_hours\": [\n"
        "    {\n"
        "      \"role\": \"Role title (e.g., Senior Developer)\",\n"
        "      \"hours\": Number of hours,\n"
        "      \"cost\": Hourly rate * hours\n"
        "    },\n"
        "    ...\n"
        "  ],\n"
        "  \"notes\": \"Detailed explanation of the development approach, timeline considerations, risk factors, etc.\"\n"
        "}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)
    # resp, code = client.get_request(request_id="21")
    if code != 200 or "error" in resp:
        logger.error(' {"error": "Failed to generate development plan", "detail": resp}')

    data = resp.get("data") or resp.get("answer") or resp
    try:
        parsed_data = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, AttributeError):
        logger.error(' {"error": "Invalid response format from GPT", "detail": data}')

    if not isinstance(parsed_data, dict):
        logger.error(' {"error": "Invalid plan format", "detail": data}')
    logger.error(f"Generated development plan for project {project_id}")
    plan, created = DevelopmentPlan.objects.get_or_create(
        project=project,
        defaults={'status': STATUS_DRAFT, 'current_version_number': 0}
    )

    last = plan.versions.order_by("-version_number").first()
    next_version = last.version_number + 1 if last else 1

    roles_hours = parsed_data.get("roles_hours", [])
    notes = parsed_data.get("notes", "")
    total_cost = 0

    formatted_roles_hours = []
    for item in roles_hours:
        role = item.get("role", "")
        hours = float(item.get("hours", 0))
        cost = float(item.get("cost", 0))

        formatted_item = {
            "role": role,
            "hours": hours,
            "cost": cost
        }
        formatted_roles_hours.append(formatted_item)
        total_cost += cost

    dv = DevelopmentPlanVersion.objects.create(
        plan=plan,
        version_number=next_version,
        roles_and_hours=json.dumps(formatted_roles_hours),
        estimated_cost=total_cost,
        notes=notes,
        created_by=user,
        status=STATUS_DRAFT
    )

    plan.current_version_number = next_version
    if plan.status == STATUS_ARCHIVED:
        plan.status = STATUS_DRAFT
    plan.save()

    return {
        "success": True,
        "plan_id": str(plan.id),
        "version_id": str(dv.id),
        "version_number": next_version,
        "total_cost": total_cost,
        "roles_count": len(formatted_roles_hours)
    }


@app.task
def generate_mockups_task(project_id, user_id=None):
    """
    Generate HTML mockups for a project's requirements.

    Args:
        project_id: ID of the project
        user_id: Optional user ID that initiated the request (for attribution)
    """
    logger.error(f"Generating mockups for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for attribution")
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    reqs = project.requirements.filter(
        status__in=[STATUS_ACTIVE, STATUS_DRAFT],
        category__in=[REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_FUNCTIONAL]
    )

    if not reqs.exists():
        return {"error": "No suitable UI/UX or functional requirements found for mockups"}

    req_list = []
    for r in reqs:
        req_list.append({
            "id": str(r.id),
            "title": r.title,
            "category": r.category,
            "description": r.description
        })

    prompt = (
        f"Project Name: {project.name}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Color Scheme: {project.color_scheme if project.color_scheme else 'Default (blues and grays)'}\n\n"
        f"UI/UX and Functional Requirements ({len(req_list)}):\n"
        f"{json.dumps(req_list, indent=2)}\n\n"
        f"Task: Create HTML mockups for the key screens/components of this application based on the requirements.\n\n"
        f"Guidelines:\n"
        f"1. Create clean, modern, and responsive HTML mockups\n"
        f"2. Use Tailwind CSS for styling (it's already available)\n"
        f"3. Create at least one mockup per key requirement\n"
        f"4. Focus on the most important UI elements\n"
        f"5. Include navigation elements where appropriate\n"
        f"6. Use placeholder content where needed but keep it realistic\n"
        f"7. Include appropriate form elements for user interactions\n"
        f"8. Ensure the design is cohesive across different mockups\n"
        f"9. Keep accessibility in mind (contrast, readable text)\n"
        f"10. Use the project's color scheme if specified\n\n"
        f"Output your mockups as JSON with the following structure:\n"
        "{\n"
        "  \"screens\": [\n"
        "    {\n"
        "      \"requirement_id\": \"ID of the requirement\",\n"
        "      \"name\": \"Descriptive name for the mockup\",\n"
        "      \"html\": \"Complete HTML for the mockup\"\n"
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)
    # resp, code = client.get_request(request_id="20")
    if code != 200 or "error" in resp:
        return {"error": "Failed to generate mockups", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    try:
        parsed_data = json.loads(data) if isinstance(data, str) else data
        screens = parsed_data.get("screens", [])
    except (json.JSONDecodeError, AttributeError):
        return {"error": "Invalid response format from GPT", "detail": data}

    if not isinstance(screens, list) or not screens:
        return {"error": "No valid mockups generated", "detail": data}

    logger.error(f"Generated {len(screens)} mockups for project {project_id}")

    Mockup.objects.filter(project_id=project_id).update(status=STATUS_ARCHIVED)

    created = []
    for s in screens:
        try:
            rid = s.get("requirement_id")
            requirement = None

            if rid:
                try:
                    requirement = Requirement.objects.get(id=rid, project=project)
                except Requirement.DoesNotExist:
                    pass

            mockup_name = s.get("name", "Untitled Mockup")
            html_content = s.get("html", "")

            html_content = html_content.replace("<script", "<!-- script").replace("</script>", "<!-- /script -->")
            html_content = f"""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8"/>
                    <title>Demo</title>
                    <script src="https://cdn.tailwindcss.com/"></script>
                </head>
                <body class="bg-gray-100 text-gray-800">
                {html_content}
                </body>
                </html>
            """
            mk = Mockup.objects.create(
                project=project,
                requirement=requirement,
                name=mockup_name,
                html_content=html_content,
                status=STATUS_ACTIVE
            )
            created.append(str(mk.id))

        except Exception as e:
            logger.error(f"Error creating mockup: {str(e)}")
            continue

    return {
        "success": True,
        "generated_mockups": created,
        "count": len(created)
    }
