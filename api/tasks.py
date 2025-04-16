import json
import logging
from django.utils import timezone
from django.contrib.auth.models import User
from celery import current_app
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Project, Requirement, RequirementHistory, UserStory, UserStoryHistory,
    DevelopmentPlan, DevelopmentPlanVersion, Mockup, MockupHistory,
    SrsExport, UmlDiagram, REQUIREMENT_CATEGORY_CHOICES,
    REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL,
    REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_OTHER, STATUS_DRAFT,
    STATUS_ARCHIVED, STATUS_ACTIVE, GENERATION_STATUS_PENDING,
    GENERATION_STATUS_IN_PROGRESS, GENERATION_STATUS_COMPLETED,
    GENERATION_STATUS_FAILED
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
        project.generation_status = GENERATION_STATUS_IN_PROGRESS
        project.generation_started_at = timezone.now()
        project.save()

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
        f"Operating Systems: {', '.join(project.operating_systems) if project.operating_systems else 'Not specified'}\n"
        f"Target Users: {project.target_users}\n"
        f"Priority Modules: {project.priority_modules}\n"
        f"Scope: {project.scope}\n\n"
        f"Task: Generate comprehensive software requirements for this project.\n\n"
        f"Guidelines:\n"
        f"1. Create at least 20-30 well-defined requirements\n"
        f"2. Requirements should be specific, measurable, and testable\n"
        f"3. Use clear language and avoid ambiguity\n"
        f"4. Cover both functional and non-functional aspects\n"
        f"5. Ensure requirements are traceable\n"
        f"6. Cover all priority modules mentioned\n"
        f"7. Include UI/UX requirements if applicable\n"
        f"8. Consider security, performance, and scalability\n"
        f"9. Organize requirements into a hierarchical structure with parent-child relationships\n"
        f"10. Categorize requirements by type (feature, constraint, quality, etc.)\n\n"
        f"Output requirements as JSON with the following structure:\n"
        "{\n"
        "  \"requirements\": [\n"
        "    {\n"
        "      \"title\": \"Short, descriptive title\",\n"
        "      \"description\": \"Detailed requirement description with acceptance criteria\",\n"
        f"      \"category\": One of [{available_categories}],\n"
        "      \"requirement_type\": \"feature|constraint|quality|interface|security|performance|other\",\n"
        "      \"parent_id\": null or \"index of parent requirement in this array (0-based)\",\n"
        "      \"suggested_status\": \"draft\"\n"
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)

    success = True

    try:
        if "error" in resp:
            project.generation_status = GENERATION_STATUS_FAILED
            project.generation_error = f"Failed to generate requirements: {resp.get('error', 'Unknown error')}"
            project.generation_completed_at = timezone.now()
            project.save()
            return {"error": "Failed to generate requirements", "detail": resp}

        data = resp.get("data") or resp.get("answer") or resp
        parsed_data = json.loads(data) if isinstance(data, str) else data
        requirements = parsed_data.get("requirements", [])

        if not isinstance(requirements, list) or not requirements:
            project.generation_status = GENERATION_STATUS_FAILED
            project.generation_error = "No valid requirements generated"
            project.generation_completed_at = timezone.now()
            project.save()
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
                requirement_type=req.requirement_type,
                version_number=req.version_number,
                changed_by=user,
                status=req.status,
            )

        current_requirements.update(status=STATUS_ARCHIVED)

        # First pass: create all requirements without parent relationships
        new_requirements = []
        for i, item in enumerate(requirements):
            title = item.get("title", "Untitled")
            description = item.get("description", "")
            category = item.get("category", REQUIREMENT_CATEGORY_FUNCTIONAL)
            requirement_type = item.get("requirement_type", "feature")

            if category not in [REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL,
                                REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_OTHER]:
                category = REQUIREMENT_CATEGORY_FUNCTIONAL

            new_req = Requirement.objects.create(
                project=project,
                title=title,
                description=description,
                category=category,
                requirement_type=requirement_type,
                status=STATUS_DRAFT,
                version_number=1
            )

            RequirementHistory.objects.create(
                requirement=new_req,
                title=new_req.title,
                description=new_req.description,
                category=new_req.category,
                requirement_type=new_req.requirement_type,
                version_number=new_req.version_number,
                changed_by=user,
                status=new_req.status,
            )

            new_requirements.append(new_req)

        # Second pass: set parent relationships
        for i, item in enumerate(requirements):
            parent_idx = item.get("parent_id")
            if parent_idx is not None and isinstance(parent_idx, int) and 0 <= parent_idx < len(new_requirements):
                if parent_idx != i:  # Prevent self-reference
                    new_requirements[i].parent = new_requirements[parent_idx]
                    new_requirements[i].save()

        # Mark project as completed
        project.generation_status = GENERATION_STATUS_COMPLETED
        project.generation_completed_at = timezone.now()
        project.save()

        # Generate user stories for the requirements
        generate_user_stories_task.delay(str(project.id))

        return {"created_requirements": [str(req.id) for req in new_requirements], "count": len(new_requirements)}
    except Exception as e:
        logger.error(f"Error generating requirements: {str(e)}")
        project.generation_status = GENERATION_STATUS_FAILED
        project.generation_error = str(e)
        project.generation_completed_at = timezone.now()
        project.save()
        return {"error": f"Error generating requirements: {str(e)}"}


@app.task
def generate_user_stories_task(project_id, requirement_id=None, user_story_id=None, feedback=None, user_id=None):
    """
    Generate user stories for requirements in a project.

    Args:
        project_id: ID of the project
        requirement_id: Optional ID of a specific requirement to generate stories for
        user_story_id: Optional ID of a specific user story to regenerate
        feedback: Optional feedback for regenerating a user story
        user_id: Optional user ID that initiated the request (for attribution)
    """
    logger.error(f"Generating user stories for project {project_id}")
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

    # Determine which requirements to process
    if user_story_id:
        # Regenerate a specific user story
        try:
            user_story = UserStory.objects.get(id=user_story_id)
            requirement = user_story.requirement

            user_story.generation_status = GENERATION_STATUS_IN_PROGRESS
            user_story.generation_started_at = timezone.now()
            user_story.save()

            # Create history record before modifying
            UserStoryHistory.objects.create(
                user_story=user_story,
                role=user_story.role,
                action=user_story.action,
                benefit=user_story.benefit,
                acceptance_criteria=user_story.acceptance_criteria,
                version_number=user_story.version_number,
                changed_by=user,
                status=user_story.status
            )

            requirements_to_process = [requirement]
            regenerate_story = user_story
        except ObjectDoesNotExist:
            return {"error": "User story not found"}
    elif requirement_id:
        # Generate user stories for a specific requirement
        try:
            requirement = Requirement.objects.get(id=requirement_id, project_id=project_id)
            requirements_to_process = [requirement]
            regenerate_story = None
        except ObjectDoesNotExist:
            return {"error": "Requirement not found"}
    else:
        # Generate user stories for all active requirements in the project
        requirements_to_process = Requirement.objects.filter(
            project_id=project_id,
            status__in=[STATUS_DRAFT, STATUS_ACTIVE],
            category=REQUIREMENT_CATEGORY_FUNCTIONAL  # Only generate for functional requirements
        )
        regenerate_story = None

    created_stories = []

    for requirement in requirements_to_process:
        # Prepare prompt for generating user stories
        prompt = (
            f"Project: {project.name}\n"
            f"Requirement ID: {requirement.id}\n"
            f"Requirement Title: {requirement.title}\n"
            f"Requirement Description: {requirement.description}\n"
            f"Requirement Category: {requirement.category}\n"
            f"Requirement Type: {requirement.requirement_type}\n\n"
        )

        if regenerate_story:
            prompt += (
                f"Current User Story:\n"
                f"As a {regenerate_story.role}, I want to {regenerate_story.action} so that {regenerate_story.benefit}\n\n"
                f"User Feedback: {feedback or 'Please improve this user story.'}\n\n"
                f"Task: Regenerate this user story based on the feedback and the requirement details.\n"
            )
        else:
            prompt += (
                f"Task: Generate user stories for this requirement.\n\n"
                f"Guidelines:\n"
                f"1. Create 1-3 user stories that capture the requirement from different user perspectives\n"
                f"2. Follow the format: 'As a [role], I want to [action] so that [benefit]'\n"
                f"3. The role should be specific and relevant to the project\n"
                f"4. The action should be clear and concise\n"
                f"5. The benefit should explain the value the user gets\n"
                f"6. Include acceptance criteria for each user story\n"
            )

        prompt += (
            f"\nOutput your user stories as JSON with the following structure:\n"
            "{\n"
            "  \"user_stories\": [\n"
            "    {\n"
            "      \"role\": \"The type of user\",\n"
            "      \"action\": \"What the user wants to do\",\n"
            "      \"benefit\": \"The value or benefit they receive\",\n"
            "      \"acceptance_criteria\": [\"Criterion 1\", \"Criterion 2\", ...]\n"
            "    },\n"
            "    ...\n"
            "  ]\n"
            "}"
        )

        client = GptClient()
        resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)

        if "error" in resp:
            if regenerate_story:
                regenerate_story.generation_status = GENERATION_STATUS_FAILED
                regenerate_story.generation_error = f"Failed to regenerate user story: {resp.get('error', 'Unknown error')}"
                regenerate_story.generation_completed_at = timezone.now()
                regenerate_story.save()
            return {"error": "Failed to generate user stories", "detail": resp}

        data = resp.get("data") or resp.get("answer") or resp
        try:
            parsed_data = json.loads(data) if isinstance(data, str) else data
            stories = parsed_data.get("user_stories", [])
        except (json.JSONDecodeError, AttributeError):
            if regenerate_story:
                regenerate_story.generation_status = GENERATION_STATUS_FAILED
                regenerate_story.generation_error = "Invalid response format from GPT"
                regenerate_story.generation_completed_at = timezone.now()
                regenerate_story.save()
            return {"error": "Invalid response format from GPT", "detail": data}

        if not isinstance(stories, list) or not stories:
            if regenerate_story:
                regenerate_story.generation_status = GENERATION_STATUS_FAILED
                regenerate_story.generation_error = "No valid user stories generated"
                regenerate_story.generation_completed_at = timezone.now()
                regenerate_story.save()
            return {"error": "No valid user stories generated", "detail": data}

        # Process generated stories
        for story_data in stories:
            role = story_data.get("role", "")
            action = story_data.get("action", "")
            benefit = story_data.get("benefit", "")
            acceptance_criteria = story_data.get("acceptance_criteria", [])

            if regenerate_story:
                # Update existing user story
                regenerate_story.role = role
                regenerate_story.action = action
                regenerate_story.benefit = benefit
                regenerate_story.acceptance_criteria = acceptance_criteria
                regenerate_story.version_number += 1
                regenerate_story.generation_status = GENERATION_STATUS_COMPLETED
                regenerate_story.generation_completed_at = timezone.now()
                regenerate_story.save()
                created_stories.append(str(regenerate_story.id))
            else:
                # Create new user story
                new_story = UserStory.objects.create(
                    requirement=requirement,
                    role=role,
                    action=action,
                    benefit=benefit,
                    acceptance_criteria=acceptance_criteria,
                    status=STATUS_DRAFT,
                    generation_status=GENERATION_STATUS_COMPLETED,
                    generation_completed_at=timezone.now()
                )
                created_stories.append(str(new_story.id))

    return {"created_user_stories": created_stories, "count": len(created_stories)}


@app.task
def export_srs_task(project_id, created_by=None, fmt="pdf"):
    """
    Export a Software Requirements Specification (SRS) document for a project.
    Now includes user stories in the export.

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
    ).order_by('category', 'requirement_type', 'created_at')

    content = f"# Software Requirements Specification for {project.name}\n\n"
    content += f"## 1. Introduction\n\n"
    content += f"### 1.1 Project Overview\n\n"
    content += f"{project.short_description}\n\n"

    if project.scope:
        content += f"### 1.2 Project Scope\n\n"
        content += f"{project.scope}\n\n"

    content += f"### 1.3 Document Purpose\n\n"
    content += f"This Software Requirements Specification (SRS) document describes the functional and non-functional requirements for the {project.name} project. It is intended to be used by the development team to implement the software system.\n\n"

    content += f"## 2. General Description\n\n"
    content += f"### 2.1 Product Perspective\n\n"
    content += f"**Application Type:** {project.type_of_application}\n\n"
    content += f"**Primary Language:** {project.language}\n\n"

    if project.operating_systems:
        content += f"**Operating Systems:** {', '.join(project.operating_systems)}\n\n"

    if project.target_users:
        content += f"### 2.2 User Classes and Characteristics\n\n"
        content += f"{project.target_users}\n\n"

    if project.technology_stack:
        content += f"### 2.3 Technology Stack\n\n"
        content += f"{project.technology_stack}\n\n"

    deadline_info = []
    if project.deadline_start:
        deadline_start_str = project.deadline_start.strftime("%Y-%m-%d")
        deadline_info.append(f"Start: {deadline_start_str}")
    if project.deadline_end:
        deadline_end_str = project.deadline_end.strftime("%Y-%m-%d")
        deadline_info.append(f"End: {deadline_end_str}")

    if deadline_info:
        content += f"### 2.4 Project Timeline\n\n"
        content += f"{' | '.join(deadline_info)}\n\n"

    content += f"## 3. Specific Requirements\n\n"

    categories = {
        REQUIREMENT_CATEGORY_FUNCTIONAL: "Functional Requirements",
        REQUIREMENT_CATEGORY_NONFUNCTIONAL: "Non-Functional Requirements",
        REQUIREMENT_CATEGORY_UIUX: "UI/UX Requirements",
        REQUIREMENT_CATEGORY_OTHER: "Other Requirements"
    }

    section_num = 1

    # Group requirements by category
    for cat, cat_name in categories.items():
        cat_reqs = list(reqs.filter(category=cat))
        if not cat_reqs:
            continue

        content += f"### 3.{section_num} {cat_name}\n\n"
        section_num += 1

        # First, get top-level requirements (no parent)
        top_level_reqs = [r for r in cat_reqs if r.parent is None]

        # Process each top-level requirement and its children recursively
        for i, req in enumerate(top_level_reqs, 1):
            content = _add_requirement_to_srs(content, req, cat_reqs, i, "", cat[:3].upper())

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


def _add_requirement_to_srs(content, requirement, all_reqs, req_num, prefix, cat_prefix):
    """Helper function to recursively add requirements to the SRS document"""
    # Create requirement number with prefix
    req_id = f"{prefix}{req_num}"

    # Add the requirement
    content += f"#### REQ-{cat_prefix}-{req_id}: {requirement.title}\n\n"
    content += f"*Status:* {requirement.status}\n\n"
    content += f"*Type:* {requirement.requirement_type}\n\n"
    content += f"*Description:*\n\n{requirement.description}\n\n"
    content += f"*Version:* {requirement.version_number}\n\n"

    # Add user stories if any
    user_stories = requirement.user_stories.filter(status__in=[STATUS_ACTIVE, STATUS_DRAFT])
    if user_stories.exists():
        content += f"*User Stories:*\n\n"
        for i, story in enumerate(user_stories, 1):
            content += f"- As a {story.role}, I want to {story.action} so that {story.benefit}\n"
            if story.acceptance_criteria:
                content += f"  *Acceptance Criteria:*\n"
                for criterion in story.acceptance_criteria:
                    content += f"  - {criterion}\n"
            content += "\n"

    content += "---\n\n"

    # Find and process children
    children = [r for r in all_reqs if r.parent and r.parent.id == requirement.id]
    for i, child in enumerate(children, 1):
        # Create a new prefix for the child based on the parent's prefix
        child_prefix = f"{req_id}."
        content = _add_requirement_to_srs(content, child, all_reqs, i, child_prefix, cat_prefix)

    return content


@app.task
def generate_development_plan_task(project_id, user_id=None):
    """
    Generate a development plan for a project based on its requirements.
    Now includes UML diagram generation.

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
            "requirement_type": r.requirement_type,
            "description": r.description
        })

    prompt = (
        f"Project Name: {project.name}\n"
        f"Short Description: {project.short_description}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Technology Stack: {project.technology_stack}\n"
        f"Operating Systems: {', '.join(project.operating_systems) if project.operating_systems else 'Not specified'}\n"
        f"Target Users: {project.target_users}\n"
        f"Priority Modules: {project.priority_modules}\n"
        f"Preliminary Budget: {project.preliminary_budget if project.preliminary_budget else 'Not specified'}\n"
        f"Deadline: {'From ' + project.deadline_start.strftime('%Y-%m-%d') if project.deadline_start else ''} {'To ' + project.deadline_end.strftime('%Y-%m-%d') if project.deadline_end else ''}\n\n"
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
        "  \"hourly_rates\": {\"Role title\": hourly rate, ...},\n"
        "  \"notes\": \"Detailed explanation of the development approach, timeline considerations, risk factors, etc.\"\n"
        "}"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)

    if code != 200 or "error" in resp:
        logger.error(' {"error": "Failed to generate development plan", "detail": resp}')
        return {"error": "Failed to generate development plan", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    try:
        parsed_data = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, AttributeError):
        logger.error(' {"error": "Invalid response format from GPT", "detail": data}')
        return {"error": "Invalid response format from GPT", "detail": data}

    if not isinstance(parsed_data, dict):
        logger.error(' {"error": "Invalid plan format", "detail": data}')
        return {"error": "Invalid plan format", "detail": data}

    logger.error(f"Generated development plan for project {project_id}")
    plan, created = DevelopmentPlan.objects.get_or_create(
        project=project,
        defaults={'status': STATUS_DRAFT, 'current_version_number': 0}
    )

    # Update hourly rates if provided
    hourly_rates = parsed_data.get("hourly_rates", {})
    if hourly_rates:
        plan.hourly_rates = hourly_rates
        plan.save()

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

    # Generate UML diagrams
    generate_uml_diagrams_task.delay(project_id, plan_version_id=str(dv.id))

    return {
        "success": True,
        "plan_id": str(plan.id),
        "version_id": str(dv.id),
        "version_number": next_version,
        "total_cost": total_cost,
        "roles_count": len(formatted_roles_hours)
    }


@app.task
def generate_uml_diagrams_task(project_id, diagram_type="class", diagram_id=None, plan_version_id=None):
    """
    Generate UML diagrams for a project.

    Args:
        project_id: ID of the project
        diagram_type: Type of diagram to generate (class, sequence, activity, etc.)
        diagram_id: Optional ID of a specific diagram to regenerate
        plan_version_id: Optional ID of a development plan version to attach the diagram to
    """
    logger.error(f"Generating {diagram_type} UML diagram for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    plan_version = None
    if plan_version_id:
        try:
            plan_version = DevelopmentPlanVersion.objects.get(id=plan_version_id)
        except ObjectDoesNotExist:
            logger.warning(f"Plan version {plan_version_id} not found")

    # If regenerating an existing diagram
    if diagram_id:
        try:
            diagram = UmlDiagram.objects.get(id=diagram_id)
            diagram.generation_status = GENERATION_STATUS_IN_PROGRESS
            diagram.generation_started_at = timezone.now()
            diagram.save()
        except ObjectDoesNotExist:
            return {"error": "Diagram not found"}
    else:
        # Create new diagram
        diagram = UmlDiagram.objects.create(
            project=project,
            plan_version=plan_version,
            name=f"{diagram_type.capitalize()} Diagram for {project.name}",
            diagram_type=diagram_type,
            generation_status=GENERATION_STATUS_IN_PROGRESS,
            generation_started_at=timezone.now(),
            status=STATUS_DRAFT
        )

    # Get requirements for the project
    reqs = project.requirements.filter(status__in=[STATUS_ACTIVE, STATUS_DRAFT])

    # Prepare requirements data for the prompt
    req_data = []
    for req in reqs:
        req_data.append({
            "id": str(req.id),
            "title": req.title,
            "description": req.description,
            "category": req.category,
            "requirement_type": req.requirement_type
        })

    # Create prompt based on diagram type
    prompt = (
        f"Project Name: {project.name}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Technology Stack: {project.technology_stack}\n\n"
        f"Requirements:\n{json.dumps(req_data, indent=2)}\n\n"
        f"Task: Create a {diagram_type} UML diagram for this project based on the requirements.\n\n"
    )

    if diagram_type.lower() == "class":
        prompt += (
            "Guidelines for Class Diagram:\n"
            "1. Identify the main classes in the system\n"
            "2. Define attributes and methods for each class\n"
            "3. Establish relationships between classes (association, inheritance, composition, etc.)\n"
            "4. Use proper UML notation\n"
            "5. Focus on the most important classes and relationships\n"
            "6. Consider design patterns where appropriate\n\n"
        )
    elif diagram_type.lower() == "sequence":
        prompt += (
            "Guidelines for Sequence Diagram:\n"
            "1. Identify the main actors and objects\n"
            "2. Show the sequence of interactions for a key use case\n"
            "3. Include method calls, returns, and messages\n"
            "4. Show the timeline of events from top to bottom\n"
            "5. Focus on the most important interactions\n\n"
        )
    elif diagram_type.lower() == "activity":
        prompt += (
            "Guidelines for Activity Diagram:\n"
            "1. Show the flow of activities from start to finish\n"
            "2. Include decision points, forks, and joins\n"
            "3. Represent the business process or workflow\n"
            "4. Use swim lanes for different actors if appropriate\n"
            "5. Focus on the most important activities\n\n"
        )
    else:
        prompt += (
            f"Guidelines for {diagram_type.capitalize()} Diagram:\n"
            "1. Use proper UML notation\n"
            "2. Focus on the most important elements\n"
            "3. Provide a clear and concise diagram\n\n"
        )

    prompt += (
        "Output in PlantUML code format, which uses simple text notation to create UML diagrams.\n"
        "Provide only the PlantUML code without any explanations or additional text.\n"
        "Start with @startuml and end with @enduml.\n"
    )

    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=False)

    if "error" in resp:
        diagram.generation_status = GENERATION_STATUS_FAILED
        diagram.generation_error = f"Failed to generate UML diagram: {resp.get('error', 'Unknown error')}"
        diagram.generation_completed_at = timezone.now()
        diagram.save()
        return {"error": "Failed to generate UML diagram", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp

    if not data or not isinstance(data, str):
        diagram.generation_status = GENERATION_STATUS_FAILED
        diagram.generation_error = "Invalid or empty response"
        diagram.generation_completed_at = timezone.now()
        diagram.save()
        return {"error": "Invalid UML diagram content", "detail": data}

    # Extract PlantUML code
    plantuml_code = data
    if "@startuml" not in plantuml_code:
        plantuml_code = "@startuml\n" + plantuml_code
    if "@enduml" not in plantuml_code:
        plantuml_code += "\n@enduml"

    # Update the diagram
    diagram.content = plantuml_code
    diagram.generation_status = GENERATION_STATUS_COMPLETED
    diagram.generation_completed_at = timezone.now()
    diagram.save()

    return {
        "success": True,
        "diagram_id": str(diagram.id),
        "diagram_type": diagram_type
    }


@app.task
def generate_mockups_task(project_id, user_story_id=None, requirement_id=None, mockup_id=None, feedback=None):
    """
    Generate HTML mockups for a project's user stories or requirements.

    Args:
        project_id: ID of the project
        user_story_id: Optional ID of a specific user story to generate mockups for
        requirement_id: Optional ID of a specific requirement to generate mockups for
        mockup_id: Optional ID of a specific mockup to regenerate
        feedback: Optional feedback for regeneration
    """
    logger.error(f"Generating mockups for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    # If regenerating a specific mockup
    if mockup_id:
        try:
            mockup = Mockup.objects.get(id=mockup_id)
            mockup.generation_status = GENERATION_STATUS_IN_PROGRESS
            mockup.generation_started_at = timezone.now()
            mockup.save()

            # Create history record
            MockupHistory.objects.create(
                mockup=mockup,
                html_content=mockup.html_content,
                version_number=mockup.version_number,
                status=mockup.status
            )

            if mockup.user_story:
                user_stories = [mockup.user_story]
                requirements = []
            elif mockup.requirement:
                requirements = [mockup.requirement]
                user_stories = []
            else:
                mockup.generation_status = GENERATION_STATUS_FAILED
                mockup.generation_error = "Mockup has no associated user story or requirement"
                mockup.generation_completed_at = timezone.now()
                mockup.save()
                return {"error": "Mockup has no associated user story or requirement"}

            regenerate_mockup = mockup
        except ObjectDoesNotExist:
            return {"error": "Mockup not found"}
    else:
        regenerate_mockup = None

        # Determine what to generate mockups for
        if user_story_id:
            try:
                user_story = UserStory.objects.get(id=user_story_id)
                user_stories = [user_story]
                requirements = []
            except ObjectDoesNotExist:
                return {"error": "User story not found"}
        elif requirement_id:
            try:
                requirement = Requirement.objects.get(id=requirement_id)
                requirements = [requirement]
                user_stories = []
            except ObjectDoesNotExist:
                return {"error": "Requirement not found"}
        else:
            # Generate for all active user stories
            user_stories = UserStory.objects.filter(
                requirement__project_id=project_id,
                status__in=[STATUS_ACTIVE, STATUS_DRAFT]
            )

            # If no user stories, use UI/UX requirements
            if not user_stories.exists():
                requirements = project.requirements.filter(
                    status__in=[STATUS_ACTIVE, STATUS_DRAFT],
                    category__in=[REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_FUNCTIONAL]
                )
            else:
                requirements = []

    created_mockups = []

    # Process user stories first
    for user_story in user_stories:
        prompt = _create_mockup_prompt(
            project=project,
            user_story=user_story,
            requirement=user_story.requirement,
            regenerate_mockup=regenerate_mockup if regenerate_mockup and regenerate_mockup.user_story == user_story else None,
            feedback=feedback
        )

        mockup_data = _generate_mockup_from_prompt(prompt)

        if "error" in mockup_data:
            if regenerate_mockup:
                regenerate_mockup.generation_status = GENERATION_STATUS_FAILED
                regenerate_mockup.generation_error = mockup_data["error"]
                regenerate_mockup.generation_completed_at = timezone.now()
                regenerate_mockup.save()
            return mockup_data

        html_content = mockup_data.get("html_content", "")
        mockup_name = mockup_data.get("name", f"Mockup for {user_story.role} - {user_story.action[:50]}")

        if regenerate_mockup:
            regenerate_mockup.html_content = html_content
            regenerate_mockup.name = mockup_name
            regenerate_mockup.version_number += 1
            regenerate_mockup.generation_status = GENERATION_STATUS_COMPLETED
            regenerate_mockup.generation_completed_at = timezone.now()
            regenerate_mockup.save()
            created_mockups.append(str(regenerate_mockup.id))
        else:
            mockup = Mockup.objects.create(
                project=project,
                user_story=user_story,
                requirement=user_story.requirement,
                name=mockup_name,
                html_content=html_content,
                status=STATUS_ACTIVE,
                generation_status=GENERATION_STATUS_COMPLETED,
                generation_completed_at=timezone.now()
            )
            created_mockups.append(str(mockup.id))

    # Process requirements
    for requirement in requirements:
        prompt = _create_mockup_prompt(
            project=project,
            user_story=None,
            requirement=requirement,
            regenerate_mockup=regenerate_mockup if regenerate_mockup and regenerate_mockup.requirement == requirement else None,
            feedback=feedback
        )

        mockup_data = _generate_mockup_from_prompt(prompt)

        if "error" in mockup_data:
            if regenerate_mockup:
                regenerate_mockup.generation_status = GENERATION_STATUS_FAILED
                regenerate_mockup.generation_error = mockup_data["error"]
                regenerate_mockup.generation_completed_at = timezone.now()
                regenerate_mockup.save()
            return mockup_data

        html_content = mockup_data.get("html_content", "")
        mockup_name = mockup_data.get("name", f"Mockup for {requirement.title}")

        if regenerate_mockup:
            regenerate_mockup.html_content = html_content
            regenerate_mockup.name = mockup_name
            regenerate_mockup.version_number += 1
            regenerate_mockup.generation_status = GENERATION_STATUS_COMPLETED
            regenerate_mockup.generation_completed_at = timezone.now()
            regenerate_mockup.save()
            created_mockups.append(str(regenerate_mockup.id))
        else:
            mockup = Mockup.objects.create(
                project=project,
                requirement=requirement,
                name=mockup_name,
                html_content=html_content,
                status=STATUS_ACTIVE,
                generation_status=GENERATION_STATUS_COMPLETED,
                generation_completed_at=timezone.now()
            )
            created_mockups.append(str(mockup.id))

    return {
        "success": True,
        "generated_mockups": created_mockups,
        "count": len(created_mockups)
    }


def _create_mockup_prompt(project, user_story, requirement, regenerate_mockup=None, feedback=None):
    """Helper to create the mockup generation prompt"""
    prompt = (
        f"Project Name: {project.name}\n"
        f"Application Type: {project.type_of_application}\n"
        f"Language: {project.language}\n"
        f"Color Scheme: {project.color_scheme if project.color_scheme else 'Default (blues and grays)'}\n\n"
    )

    if user_story:
        prompt += (
            f"User Story:\n"
            f"As a {user_story.role}, I want to {user_story.action} so that {user_story.benefit}\n\n"
        )

        if user_story.acceptance_criteria:
            prompt += "Acceptance Criteria:\n"
            for i, criterion in enumerate(user_story.acceptance_criteria, 1):
                prompt += f"{i}. {criterion}\n"
            prompt += "\n"

    if requirement:
        prompt += (
            f"Requirement:\n"
            f"Title: {requirement.title}\n"
            f"Category: {requirement.category}\n"
            f"Type: {requirement.requirement_type}\n"
            f"Description: {requirement.description}\n\n"
        )

    if regenerate_mockup:
        prompt += (
            f"Current Mockup:\n"
            f"Name: {regenerate_mockup.name}\n"
            f"User Feedback: {feedback or 'Please improve this mockup.'}\n\n"
        )

    prompt += (
        f"Task: Create an HTML mockup for {'this user story' if user_story else 'this requirement'}.\n\n"
        f"Guidelines:\n"
        f"1. Create clean, modern, and responsive HTML mockup\n"
        f"2. Use Tailwind CSS for styling\n"
        f"3. Focus on the most important UI elements\n"
        f"4. Include navigation elements where appropriate\n"
        f"5. Use placeholder content where needed but keep it realistic\n"
        f"6. Include appropriate form elements for user interactions\n"
        f"7. Keep accessibility in mind (contrast, readable text)\n"
        f"8. Use the project's color scheme if specified\n\n"
        f"Output your mockup as JSON with the following structure:\n"
        "{\n"
        "  \"name\": \"Descriptive name for the mockup\",\n"
        "  \"html_content\": \"Complete HTML for the mockup, including Tailwind CSS\"\n"
        "}"
    )

    return prompt


def _generate_mockup_from_prompt(prompt):
    """Helper to generate mockup HTML from a prompt"""
    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4o", is_json=True)

    if "error" in resp:
        return {"error": "Failed to generate mockup", "detail": resp}

    data = resp.get("data") or resp.get("answer") or resp
    try:
        parsed_data = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, AttributeError):
        return {"error": "Invalid response format from GPT", "detail": data}

    html_content = parsed_data.get("html_content")
    name = parsed_data.get("name", "Untitled Mockup")

    if not html_content:
        return {"error": "No HTML content generated", "detail": parsed_data}

    # Clean up HTML content
    html_content = html_content.replace("<script", "<!-- script").replace("</script>", "<!-- /script -->")
    html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8"/>
            <title>{name}</title>
            <script src="https://cdn.tailwindcss.com/"></script>
        </head>
        <body class="bg-gray-100 text-gray-800">
        {html_content}
        </body>
        </html>
    """

    return {
        "name": name,
        "html_content": html_content
    }