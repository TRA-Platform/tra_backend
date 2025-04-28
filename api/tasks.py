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
    GENERATION_STATUS_FAILED, UML_DIAGRAM_TYPE_CLASS, UML_DIAGRAM_TYPE_SEQUENCE, UML_DIAGRAM_TYPE_ACTIVITY,
    UML_DIAGRAM_TYPE_COMPONENT, PROJECT_TYPE_API, PROJECT_TYPE_MOBILE, PROJECT_TYPE_WEBSITE, PROJECT_TYPE_DESKTOP,
    PROJECT_TYPE_OTHER, RequirementComment, REQUIREMENT_TYPE_PERFORMANCE, REQUIREMENT_TYPE_SECURITY
)
from gpt.adapter import GptClient

app = current_app._get_current_object()
logger = logging.getLogger(__name__)


@app.task
def generate_requirements_task(project_id, user_id=None):
    logger.info(f"Generating requirements for project {project_id}")
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

    try:
        project.generation_status = GENERATION_STATUS_IN_PROGRESS
        project.generation_started_at = timezone.now()
        project.save()

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
            f"10. Categorize requirements by type (feature, constraint, quality, etc.)"
            f"11. Language should be: {project.language}\n\n"
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
        resp, code = client.send_request(prompt=prompt, engine="gpt-4.1", is_json=True)

        if code != 201:
            project.generation_status = GENERATION_STATUS_FAILED
            project.generation_error = f"Failed to generate requirements: {resp}"
            project.save()
            return {"error": f"Failed to generate requirements: {resp}"}

        requirements = resp.get("requirements", [])
        if not requirements:
            project.generation_status = GENERATION_STATUS_FAILED
            project.generation_error = "No requirements generated"
            project.save()
            return {"error": "No requirements generated"}

        current_requirements = Requirement.objects.filter(project=project)
        if current_requirements.exists():
            current_requirements.update(status=STATUS_ARCHIVED)

        category_counters = {
            REQUIREMENT_CATEGORY_FUNCTIONAL: 1,
            REQUIREMENT_CATEGORY_NONFUNCTIONAL: 1,
            REQUIREMENT_CATEGORY_UIUX: 1,
            REQUIREMENT_CATEGORY_OTHER: 1
        }

        new_requirements = []
        for i, item in enumerate(requirements):
            title = item.get("title", "Untitled")
            description = item.get("description", "")
            category = item.get("category", REQUIREMENT_CATEGORY_FUNCTIONAL)
            requirement_type = item.get("requirement_type", "feature")

            if category not in [REQUIREMENT_CATEGORY_FUNCTIONAL, REQUIREMENT_CATEGORY_NONFUNCTIONAL,
                                REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_OTHER]:
                category = REQUIREMENT_CATEGORY_FUNCTIONAL

            category_prefix = {
                REQUIREMENT_CATEGORY_FUNCTIONAL: "FUN",
                REQUIREMENT_CATEGORY_NONFUNCTIONAL: "NF",
                REQUIREMENT_CATEGORY_UIUX: "UI",
                REQUIREMENT_CATEGORY_OTHER: "OTH"
            }.get(category, "FUN")

            handle = f"REQ-{category_prefix}-{category_counters[category]}"
            category_counters[category] += 1

            new_req = Requirement.objects.create(
                project=project,
                title=title,
                handle=handle,
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

        for i, item in enumerate(requirements):
            parent_idx = item.get("parent_id")
            if parent_idx is not None and isinstance(parent_idx, int) and 0 <= parent_idx < len(new_requirements):
                if parent_idx != i:
                    new_requirements[i].parent = new_requirements[parent_idx]
                    new_requirements[i].save()

        project.generation_status = GENERATION_STATUS_COMPLETED
        project.generation_completed_at = timezone.now()
        project.save()

        # Chain user stories generation
        generate_user_stories_task.delay(str(project.id), user_id=str(user.id) if user else None)
        
        return {"success": True, "requirements_count": len(new_requirements)}
    except Exception as e:
        logger.error(f"Error generating requirements: {str(e)}")
        project.generation_status = GENERATION_STATUS_FAILED
        project.generation_error = f"Error generating requirements: {str(e)}"
        project.save()
        return {"error": f"Error generating requirements: {str(e)}"}


@app.task
def generate_user_stories_task(project_id, requirement_id=None, user_story_id=None, feedback=None, user_id=None):
    logger.info(f"Generating user stories for project {project_id}")
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

    try:
        if user_story_id:
            try:
                user_story = UserStory.objects.get(id=user_story_id)
                requirement = user_story.requirement

                user_story.generation_status = GENERATION_STATUS_IN_PROGRESS
                user_story.generation_started_at = timezone.now()
                user_story.save()
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
            try:
                requirement = Requirement.objects.get(id=requirement_id, project_id=project_id)
                requirements_to_process = [requirement]
                regenerate_story = None
            except ObjectDoesNotExist:
                return {"error": "Requirement not found"}
        else:
            requirements_to_process = Requirement.objects.filter(
                project_id=project_id,
                status__in=[STATUS_DRAFT, STATUS_ACTIVE],
                category=REQUIREMENT_CATEGORY_FUNCTIONAL,
            )
            current_user_stories = UserStory.objects.filter(
                requirement__in=requirements_to_process,
                status__in=[STATUS_DRAFT, STATUS_ACTIVE]
            ).update(
                status=STATUS_ARCHIVED,
            )
            regenerate_story = None

        created_stories = []

        for requirement in requirements_to_process:
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
                f"Language should be: {project.language}\n\n"
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
            resp, code = client.send_request(prompt=prompt, engine="gpt-4.1", is_json=True)

            if code != 201:
                if regenerate_story:
                    regenerate_story.generation_status = GENERATION_STATUS_FAILED
                    regenerate_story.generation_error = f"Failed to generate user story: {resp}"
                    regenerate_story.save()
                return {"error": f"Failed to generate user stories: {resp}"}

            stories = resp.get("user_stories", [])
            if not stories:
                if regenerate_story:
                    regenerate_story.generation_status = GENERATION_STATUS_FAILED
                    regenerate_story.generation_error = "No user stories generated"
                    regenerate_story.save()
                return {"error": "No user stories generated"}

            for story_data in stories:
                role = story_data.get("role", "")
                action = story_data.get("action", "")
                benefit = story_data.get("benefit", "")
                acceptance_criteria = story_data.get("acceptance_criteria", [])

                if regenerate_story:
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

        # If this was a full project generation (not just for one requirement or story),
        # chain the development plan generation
        if not requirement_id and not user_story_id:
            generate_development_plan_task.delay(str(project.id), user_id=str(user.id) if user else None)
        generate_mockups_task.delay(str(project.id), requirement_id=requirement_id)
        return {"success": True, "created_user_stories": created_stories, "count": len(created_stories)}
    except Exception as e:
        logger.error(f"Error generating user stories: {str(e)}")
        if regenerate_story:
            regenerate_story.generation_status = GENERATION_STATUS_FAILED
            regenerate_story.generation_error = f"Error generating user story: {str(e)}"
            regenerate_story.save()
        return {"error": f"Error generating user stories: {str(e)}"}


@app.task
def export_srs_task(project_id, created_by=None, fmt="pdf"):
    logger.info(f"Exporting SRS for project {project_id} in {fmt} format (enhanced version)")
    try:
        project = Project.objects.get(id=project_id)
        creator = User.objects.get(id=created_by) if created_by else None
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    export = SrsExport.objects.create(
        project=project,
        template=project.srs_template,
        fmt=fmt,
        created_by=creator,
        status=STATUS_ACTIVE,
    )
    requirements = project.requirements.filter(status__in=[STATUS_ACTIVE, STATUS_DRAFT])
    content = generate_srs_document(project, requirements, creator)
    export.content = content
    export.save()

    return {"success": True, "export_id": str(export.id), "format": fmt}


def generate_srs_document(project, requirements, creator=None):
    current_date = timezone.now().strftime("%Y-%m-%d")
    organization = creator.get_full_name() if creator else "Organization"
    header = [
        f"# Software Requirements Specification\n",
        f"## For {project.name}\n\n",
        f"Version 1.0  \n",
        f"Prepared by {creator.get_full_name() if creator else 'System'}  \n",
        f"{organization}  \n",
        f"{current_date}  \n\n",
    ]

    toc = [
        "# Table of Contents\n",
        "* [Revision History](#revision-history)\n",
        "* 1 [Introduction](#1-introduction)\n",
        "  * 1.1 [Document Purpose](#11-document-purpose)\n",
        "  * 1.2 [Product Scope](#12-product-scope)\n",
        "  * 1.3 [Definitions, Acronyms and Abbreviations](#13-definitions-acronyms-and-abbreviations)\n",
        "  * 1.4 [References](#14-references)\n",
        "  * 1.5 [Document Overview](#15-document-overview)\n",
        "* 2 [Product Overview](#2-product-overview)\n",
        "  * 2.1 [Product Perspective](#21-product-perspective)\n",
        "  * 2.2 [Product Functions](#22-product-functions)\n",
        "  * 2.3 [Product Constraints](#23-product-constraints)\n",
        "  * 2.4 [User Characteristics](#24-user-characteristics)\n",
        "  * 2.5 [Assumptions and Dependencies](#25-assumptions-and-dependencies)\n",
        "  * 2.6 [Apportioning of Requirements](#26-apportioning-of-requirements)\n",
        "* 3 [Requirements](#3-requirements)\n",
        "  * 3.1 [External Interfaces](#31-external-interfaces)\n",
        "    * 3.1.1 [User Interfaces](#311-user-interfaces)\n",
        "    * 3.1.2 [Hardware Interfaces](#312-hardware-interfaces)\n",
        "    * 3.1.3 [Software Interfaces](#313-software-interfaces)\n",
        "  * 3.2 [Functional Requirements](#32-functional-requirements)\n",
        "  * 3.3 [Quality of Service](#33-quality-of-service)\n",
        "    * 3.3.1 [Performance](#331-performance)\n",
        "    * 3.3.2 [Security](#332-security)\n",
        "    * 3.3.3 [Reliability](#333-reliability)\n",
        "    * 3.3.4 [Availability](#334-availability)\n",
        "  * 3.4 [Compliance](#34-compliance)\n",
        "  * 3.5 [Design and Implementation](#35-design-and-implementation)\n",
        "* 4 [Verification](#4-verification)\n",
        "* 5 [Appendixes](#5-appendixes)\n\n",
    ]
    revision_history = [
        "## Revision History\n",
        "| Name | Date | Reason For Changes | Version |\n",
        "| ---- | ---- | ------------------ | ------- |\n",
        f"| {creator.get_full_name() if creator else 'System'} | {current_date} | Initial document creation | 1.0 |\n\n",
    ]
    introduction = generate_introduction_section(project)
    product_overview = generate_product_overview_section(project)
    requirements_section = generate_requirements_section(project, requirements)
    verification = [
        "## 4. Verification\n\n",
        "This section outlines the verification approaches and methods planned to qualify the software. ",
        "The purpose of the verification process is to provide objective evidence that the system ",
        "fulfills its specified requirements and characteristics.\n\n",
        "### 4.1 Verification Approach\n\n",
        "The following methods will be used to verify that the requirements have been met:\n\n",
        "- **Inspection**: Review of documents, code, and other artifacts\n",
        "- **Analysis**: Mathematical or logical verification\n",
        "- **Demonstration**: Show that the system performs as expected\n",
        "- **Test**: Execute the system with specific inputs and compare to expected outputs\n\n",
        "### 4.2 Verification Matrix\n\n",
        "A traceability matrix will be maintained to ensure that each requirement is properly verified.\n\n",
        "| Requirement ID | Verification Method | Success Criteria | Status |\n",
        "| -------------- | ------------------- | ---------------- | ------ |\n"
    ]
    for req in requirements:
        verification.append(
            f"| {req.handle or 'REQ-' + str(req.id)[:8]} | Test | All acceptance criteria met | Pending |\n")
    verification.append("\n")
    appendixes = [
        "## 5. Appendixes\n\n",
        "### 5.1 Glossary\n\n",
        "| Term | Definition |\n",
        "| ---- | ---------- |\n",
        "| SRS | Software Requirements Specification |\n",
        f"| {project.type_of_application.upper()} | {get_application_type_description(project.type_of_application)} |\n\n",
        "### 5.2 Referenced Documents\n\n",
        "1. IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications\n",
        "2. Project Charter\n",
        "3. Business Requirements Document\n\n",
        "### 5.3 UML Diagrams\n\n",
        "UML diagrams are available in the project repository.\n\n",
        "### 5.4 Mockups\n\n",
        "UI mockups are available in the project repository.\n\n"
    ]
    document = (
            header +
            toc +
            revision_history +
            introduction +
            product_overview +
            requirements_section +
            verification +
            appendixes
    )

    return "".join(document)


def generate_introduction_section(project):
    return [
        "## 1. Introduction\n\n",
        "This section provides an overview of the entire document. It includes the purpose, scope, definitions, ",
        "references, and overview of this Software Requirements Specification (SRS) document.\n\n",

        "### 1.1 Document Purpose\n\n",
        "The purpose of this document is to specify the software requirements for the " +
        f"{project.name} project. It describes what the system will do, not how it will be implemented. ",
        "This document is intended for both technical and non-technical stakeholders, including developers, ",
        "testers, project managers, product owners, and business stakeholders.\n\n",

        "### 1.2 Product Scope\n\n",
        f"This SRS applies to the {project.name} {project.type_of_application}. " +
        f"The software is designed to {project.short_description}\n\n" if project.short_description else "The software is designed to meet the needs specified in this document.\n\n",

        f"The scope of this project includes: {project.scope}\n\n" if project.scope else "",

        "### 1.3 Definitions, Acronyms and Abbreviations\n\n",
        "| Term | Definition |\n",
        "| ---- | ---------- |\n",
        "| SRS | Software Requirements Specification |\n",
        "| UI | User Interface |\n",
        "| API | Application Programming Interface |\n",
        "| UX | User Experience |\n\n",

        "### 1.4 References\n\n",
        "1. IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications\n",
        "2. Project Charter\n",
        "3. Business Requirements Document\n\n",

        "### 1.5 Document Overview\n\n",
        "This document is organized into the following sections:\n\n",
        "- **Section 1: Introduction** - Provides an overview of the document\n",
        "- **Section 2: Product Overview** - Describes the context and origin of the product\n",
        "- **Section 3: Requirements** - Detailed software requirements specifications\n",
        "- **Section 4: Verification** - Approaches to verify the requirements\n",
        "- **Section 5: Appendixes** - Additional information\n\n"
    ]


def generate_product_overview_section(project):
    return [
        "## 2. Product Overview\n\n",
        "This section describes the general factors that affect the product and its requirements. ",
        "It provides context for the detailed requirements that follow.\n\n",

        "### 2.1 Product Perspective\n\n",
        f"The {project.name} is a {project.type_of_application} application " +
        "designed to operate in the context of " +
        f"{get_application_context(project.type_of_application)}. " +
        f"{project.application_description if project.application_description else ''}\n\n",

        generate_system_context_diagram(project),

        "### 2.2 Product Functions\n\n",
        "The major functions of the system include:\n\n",
        generate_product_functions(project),

        "### 2.3 Product Constraints\n\n",
        "The system is subject to the following constraints:\n\n",

        "#### 2.3.1 Technical Constraints\n\n",
        f"- **Technology Stack**: {project.technology_stack if project.technology_stack else 'To be determined'}\n",
        f"- **Operating Systems**: {', '.join(project.operating_systems) if project.operating_systems else 'To be determined'}\n",
        "- **Development Constraints**: The system must be delivered within the specified timeframe and budget\n\n",

        f"#### 2.3.2 Non-Functional Constraints\n\n{project.non_functional_requirements if project.non_functional_requirements else 'To be determined'}\n\n",

        "### 2.4 User Characteristics\n\n",
        f"{project.target_users if project.target_users else 'The system will serve the following types of users:'}\n\n",

        "### 2.5 Assumptions and Dependencies\n\n",
        "The following assumptions have been made regarding the project:\n\n",
        "- All necessary hardware will be available for development and testing\n",
        "- Required third-party services will remain operational\n",
        "- Stakeholders will be available to provide timely feedback\n\n",

        "### 2.6 Apportioning of Requirements\n\n",
        "Requirements have been prioritized as follows:\n\n",
        "- **High Priority**: Requirements that must be implemented in the initial release\n",
        "- **Medium Priority**: Requirements that should be implemented if time permits\n",
        "- **Low Priority**: Requirements that can be deferred to future releases\n\n",
        f"{project.priority_modules if project.priority_modules else ''}\n\n"
    ]


def generate_requirements_section(project, requirements):
    functional_reqs = [r for r in requirements if r.category == REQUIREMENT_CATEGORY_FUNCTIONAL]
    ui_reqs = [r for r in requirements if r.category == REQUIREMENT_CATEGORY_UIUX]
    nonfunctional_reqs = [r for r in requirements if r.category == REQUIREMENT_CATEGORY_NONFUNCTIONAL]
    other_reqs = [r for r in requirements if r.category == REQUIREMENT_CATEGORY_OTHER]

    section = [
        "## 3. Requirements\n\n",
        "This section specifies the software product's requirements to a level of detail sufficient ",
        "to enable designers to design a system that satisfies those requirements, and testers to ",
        "test that the system satisfies those requirements.\n\n"
    ]
    section.extend([
        "### 3.1 External Interfaces\n\n",
        "This section defines all inputs into and outputs from the software system.\n\n",

        "#### 3.1.1 User Interfaces\n\n",
        "The system will provide the following user interfaces:\n\n"
    ])
    if ui_reqs:
        for i, req in enumerate(ui_reqs, 1):
            section.append(f"##### {req.handle or f'UI-{i}'}: {req.title}\n\n")
            section.append(f"{req.description}\n\n")
    else:
        section.append("User interface requirements will be defined during the design phase.\n\n")
    section.extend([
        "#### 3.1.2 Hardware Interfaces\n\n",
        f"The system will run on {', '.join(project.operating_systems) if project.operating_systems else 'standard hardware platforms'}.\n\n",
        "#### 3.1.3 Software Interfaces\n\n",
        f"The system will interface with the following software systems:\n\n"
    ])

    if project.technology_stack:
        tech_items = [tech.strip() for tech in project.technology_stack.split(',')]
        for tech in tech_items:
            section.append(f"- {tech}\n")
    else:
        section.append("Software interfaces will be defined during the design phase.\n\n")
    section.append("\n### 3.2 Functional Requirements\n\n")
    root_reqs = [r for r in functional_reqs if r.parent is None]
    for i, req in enumerate(root_reqs, 1):
        section.extend(format_requirement_hierarchy(req, functional_reqs, i, "3.2"))

    section.extend([
        "\n### 3.3 Quality of Service\n\n",
        "This section describes the quality-related property requirements.\n\n"
    ])
    performance_reqs = [r for r in nonfunctional_reqs if r.requirement_type == REQUIREMENT_TYPE_PERFORMANCE]
    security_reqs = [r for r in nonfunctional_reqs if r.requirement_type == REQUIREMENT_TYPE_SECURITY]
    reliability_reqs = [r for r in nonfunctional_reqs if
                        not (r.requirement_type in [REQUIREMENT_TYPE_PERFORMANCE, REQUIREMENT_TYPE_SECURITY])]
    section.append("#### 3.3.1 Performance\n\n")
    if performance_reqs:
        for i, req in enumerate(performance_reqs, 1):
            section.append(f"##### {req.handle or f'PERF-{i}'}: {req.title}\n\n")
            section.append(f"{req.description}\n\n")
    else:
        section.append("Performance requirements will be defined during the design phase.\n\n")
    section.append("#### 3.3.2 Security\n\n")
    if security_reqs:
        for i, req in enumerate(security_reqs, 1):
            section.append(f"##### {req.handle or f'SEC-{i}'}: {req.title}\n\n")
            section.append(f"{req.description}\n\n")
    else:
        section.append("Security requirements will be defined during the design phase.\n\n")
    section.extend([
        "#### 3.3.3 Reliability\n\n",
        "The system shall operate reliably under normal operating conditions.\n\n",
        "#### 3.3.4 Availability\n\n",
        "The system shall be available during specified operating hours with minimal downtime.\n\n"
    ])
    section.extend([
        "### 3.4 Compliance\n\n",
        "The system shall comply with all relevant legal, regulatory, and industry standards.\n\n",

        "### 3.5 Design and Implementation\n\n",
        "#### 3.5.1 Installation\n\n",
        f"The {project.type_of_application} will be installed according to industry standard practices.\n\n",

        "#### 3.5.2 Distribution\n\n",
        f"The {project.type_of_application} will be distributed via appropriate channels for the target platforms.\n\n",

        "#### 3.5.3 Maintainability\n\n",
        "The code shall be written and documented to facilitate maintenance.\n\n",

        "#### 3.5.4 Reusability\n\n",
        "Components shall be designed with reusability in mind where appropriate.\n\n",

        "#### 3.5.5 Portability\n\n",
        f"The system shall be portable across {', '.join(project.operating_systems) if project.operating_systems else 'specified platforms'}.\n\n",

        "#### 3.5.6 Cost\n\n",
        f"The estimated cost for development is {project.preliminary_budget if project.preliminary_budget else 'to be determined'}.\n\n",

        "#### 3.5.7 Deadline\n\n"
    ])

    if project.deadline_start and project.deadline_end:
        section.append(
            f"Development will commence on {project.deadline_start.strftime('%Y-%m-%d')} and is scheduled to be completed by {project.deadline_end.strftime('%Y-%m-%d')}.\n\n")
    elif project.deadline_end:
        section.append(f"The project is scheduled to be completed by {project.deadline_end.strftime('%Y-%m-%d')}.\n\n")
    else:
        section.append("The project deadline will be determined in the project planning phase.\n\n")

    section.append("#### 3.5.8 Proof of Concept\n\n")
    section.append(
        "A prototype or proof of concept may be developed to validate key technical aspects of the system.\n\n")

    return section


def format_requirement_hierarchy(requirement, all_reqs, index, prefix):
    result = []
    req_id = f"{prefix}.{index}"
    result.append(f"#### {req_id} {requirement.handle or ''}: {requirement.title}\n\n")
    result.append(f"**Description**: {requirement.description}\n\n")
    result.append(f"**Type**: {requirement.requirement_type}\n")
    result.append(f"**Status**: {requirement.status}\n")
    result.append(f"**Version**: {requirement.version_number}\n\n")
    user_stories = UserStory.objects.filter(requirement=requirement, status__in=[STATUS_ACTIVE, STATUS_DRAFT])
    if user_stories.exists():
        result.append("**User Stories**:\n\n")
        for story in user_stories:
            result.append(f"- As a {story.role}, I want to {story.action} so that {story.benefit}\n")
            if story.acceptance_criteria:
                result.append("  **Acceptance Criteria**:\n")
                for criterion in story.acceptance_criteria:
                    result.append(f"  - {criterion}\n")
        result.append("\n")

    mockups = Mockup.objects.filter(requirement=requirement, status=STATUS_ACTIVE)
    if mockups.exists():
        result.append("**Mockups**: Available in the project repository\n\n")
    comments = RequirementComment.objects.filter(requirement=requirement, status=STATUS_ACTIVE)
    if comments.exists():
        result.append("**Notes**:\n\n")
        for comment in comments:
            result.append(f"- {comment.text} (by {comment.user.username}, {comment.created_at.strftime('%Y-%m-%d')})\n")
        result.append("\n")
    children = [r for r in all_reqs if r.parent and r.parent.id == requirement.id]
    for i, child in enumerate(children, 1):
        child_prefix = f"{req_id}"
        child_result = format_requirement_hierarchy(child, all_reqs, i, child_prefix)
        result.extend(child_result)

    result.append("---\n\n")
    return result


def get_application_type_description(app_type):
    descriptions = {
        PROJECT_TYPE_WEBSITE: "Web-based application accessible through standard browsers",
        PROJECT_TYPE_MOBILE: "Mobile application for smartphones and tablets",
        PROJECT_TYPE_DESKTOP: "Software application that runs on desktop computers",
        PROJECT_TYPE_API: "Application Programming Interface for system integration",
        PROJECT_TYPE_OTHER: "Custom software application"
    }
    return descriptions.get(app_type, "Software application")


def get_application_context(app_type):
    contexts = {
        PROJECT_TYPE_WEBSITE: "web browsers and internet services",
        PROJECT_TYPE_MOBILE: "mobile operating systems and app stores",
        PROJECT_TYPE_DESKTOP: "desktop operating systems",
        PROJECT_TYPE_API: "networked systems and services",
        PROJECT_TYPE_OTHER: "its target environment"
    }
    return contexts.get(app_type, "its operating environment")


def generate_system_context_diagram(project):
    return (
        "**System Context Diagram**:\n\n"
        "The following diagram illustrates the system context:\n\n"
        "```\n"
        f"    ┌────────────────┐      ┌────────────────┐\n"
        f"    │                │      │                │\n"
        f"    │     Users      │◄────►│  {project.name.ljust(12)}  │\n"
        f"    │                │      │                │\n"
        f"    └────────────────┘      └───────┬────────┘\n"
        f"                                     │\n"
        f"                                     ▼\n"
        f"                            ┌────────────────┐\n"
        f"                            │   External     │\n"
        f"                            │   Systems      │\n"
        f"                            │                │\n"
        f"                            └────────────────┘\n"
        "```\n\n"
    )


def generate_product_functions(project):
    functions = []
    requirements = Requirement.objects.filter(
        project_id=project.id,
        status__in=[STATUS_ACTIVE, STATUS_DRAFT],
        category=REQUIREMENT_CATEGORY_FUNCTIONAL
    )

    if requirements.exists():
        for req in requirements[:5]:
            functions.append(f"- {req.title}\n")
        if requirements.count() > 5:
            functions.append(f"- And {requirements.count() - 5} additional functions\n")
    elif project.priority_modules:
        modules = project.priority_modules.split('\n')
        for module in modules:
            if module.strip():
                functions.append(f"- {module.strip()}\n")
    else:
        if project.type_of_application == PROJECT_TYPE_WEBSITE:
            functions = [
                "- User registration and authentication\n",
                "- Content management\n",
                "- Search functionality\n",
                "- Responsive design for various devices\n"
            ]
        elif project.type_of_application == PROJECT_TYPE_MOBILE:
            functions = [
                "- User authentication\n",
                "- Push notifications\n",
                "- Offline functionality\n",
                "- Mobile-specific features (location, camera, etc.)\n"
            ]
        elif project.type_of_application == PROJECT_TYPE_API:
            functions = [
                "- Authentication and authorization\n",
                "- Data retrieval endpoints\n",
                "- Data manipulation endpoints\n",
                "- API documentation\n"
            ]
        else:
            functions = [
                "- Core functionality\n",
                "- User interaction\n",
                "- Data management\n",
                "- Reporting and analytics\n"
            ]

    return "".join(functions) + "\n"

@app.task
def generate_development_plan_task(project_id, user_id=None):
    logger.info(f"Generating development plan for project {project_id}")
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

    try:
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
            f"9. Also make sure to not pass preliminary budget.\n"
            f"11. Language should be: {project.language}\n\n"
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
            "  \"notes\": \"Additional notes or considerations\"\n"
            "}"
        )

        client = GptClient()
        resp, code = client.send_request(prompt=prompt, engine="gpt-4.1", is_json=True)

        if code != 201:
            return {"error": f"Failed to generate development plan: {resp}"}

        roles_hours = resp.get("roles_hours", [])
        notes = resp.get("notes", "")

        if not roles_hours:
            return {"error": "No roles and hours generated"}

        plan, created = DevelopmentPlan.objects.get_or_create(project=project)
        if not created:
            next_version = plan.current_version_number + 1
        else:
            next_version = 1

        formatted_roles_hours = []
        total_cost = 0

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

        # Chain UML diagrams generation for all diagram types
        for diagram_type in [UML_DIAGRAM_TYPE_CLASS, UML_DIAGRAM_TYPE_SEQUENCE, UML_DIAGRAM_TYPE_ACTIVITY, UML_DIAGRAM_TYPE_COMPONENT]:
            generate_uml_diagrams_task.delay(str(project.id), diagram_type=diagram_type, plan_version_id=str(dv.id))

        return {
            "success": True,
            "plan_id": str(plan.id),
            "version_id": str(dv.id),
            "version_number": next_version,
            "total_cost": total_cost,
            "roles_count": len(formatted_roles_hours)
        }
    except Exception as e:
        logger.error(f"Error generating development plan: {str(e)}")
        return {"error": f"Error generating development plan: {str(e)}"}


@app.task
def generate_uml_diagrams_task(project_id, diagram_type="class", diagram_id=None, plan_version_id=None):
    logger.error(f"Generating {diagram_type} UML diagram for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}

    try:
        plan_version = None
        if plan_version_id:
            try:
                plan_version = DevelopmentPlanVersion.objects.get(id=plan_version_id)
            except ObjectDoesNotExist:
                logger.warning(f"Plan version {plan_version_id} not found")
        if diagram_id:
            try:
                diagram = UmlDiagram.objects.get(id=diagram_id)
                diagram.generation_status = GENERATION_STATUS_IN_PROGRESS
                diagram.generation_started_at = timezone.now()
                diagram.save()
            except ObjectDoesNotExist:
                return {"error": "Diagram not found"}
        else:
            diagram = UmlDiagram.objects.create(
                project=project,
                plan_version=plan_version,
                name=f"{diagram_type.capitalize()} Diagram for {project.name}",
                diagram_type=diagram_type,
                generation_status=GENERATION_STATUS_IN_PROGRESS,
                generation_started_at=timezone.now(),
                status=STATUS_DRAFT
            )
        reqs = project.requirements.filter(status__in=[STATUS_ACTIVE, STATUS_DRAFT])
        req_data = []
        for req in reqs:
            req_data.append({
                "id": str(req.id),
                "title": req.title,
                "description": req.description,
                "category": req.category,
                "requirement_type": req.requirement_type
            })
        prompt = (
            f"Project Name: {project.name}\n"
            f"Application Type: {project.type_of_application}\n"
            f"Technology Stack: {project.technology_stack}\n\n"
            f"Requirements:\n{json.dumps(req_data, indent=2, ensure_ascii=False)}\n\n"
            f"Task: Create a {diagram_type} UML diagram for this project based on the requirements.\n\n"
        )

        if diagram_type.lower() == UML_DIAGRAM_TYPE_CLASS:
            prompt += (
                "Guidelines for Class Diagram:\n"
                "1. Identify the main classes in the system\n"
                "2. Define attributes and methods for each class\n"
                "3. Establish relationships between classes (association, inheritance, composition, etc.)\n"
                "4. Use proper UML notation\n"
                "5. Focus on the most important classes and relationships\n"
                "6. Consider design patterns where appropriate\n\n"
            )
        elif diagram_type.lower() == UML_DIAGRAM_TYPE_SEQUENCE:
            prompt += (
                "Guidelines for Sequence Diagram:\n"
                "1. Identify the main actors and objects\n"
                "2. Show the sequence of interactions for a key use case\n"
                "3. Include method calls, returns, and messages\n"
                "4. Show the timeline of events from top to bottom\n"
                "5. Focus on the most important interactions\n\n"
            )
        elif diagram_type.lower() == UML_DIAGRAM_TYPE_ACTIVITY:
            prompt += (
                "Guidelines for Activity Diagram:\n"
                "1. Show the flow of activities from start to finish\n"
                "2. Include decision points, forks, and joins\n"
                "3. Represent the business process or workflow\n"
                "4. Use swim lanes for different actors if appropriate\n"
                "5. Focus on the most important activities\n\n"
                "Specific PlantUML syntax for Activity Diagrams:\n"
                "- Use 'start' and 'stop' to mark the beginning and end of the activity flow\n"
                "- Use ':activity label;' for activities\n"
                "- Use 'if (condition) then (yes)' and 'else (no)' for decision points\n"
                "- End if statements with 'endif'\n"
                "- Use 'fork' and 'fork again' for parallel activities, ending with 'end fork'\n"
                "- For swim lanes, use 'partition Name {' and close with '}'\n\n"
                "Example of valid activity diagram syntax:\n"
                "@startuml\n"
                "start\n"
                ":Initialize Process;\n"
                "if (Data Valid?) then (yes)\n"
                "  :Process Data;\n"
                "else (no)\n"
                "  :Report Error;\n"
                "endif\n"
                ":Complete Process;\n"
                "stop\n"
                "@enduml\n\n"
            )
        elif diagram_type.lower() == UML_DIAGRAM_TYPE_COMPONENT:
            prompt += (
                "Guidelines for Component Diagram:\n"
                "1. Identify the main components/modules of the system\n"
                "2. Define interfaces between components\n"
                "3. Show dependencies between components\n"
                "4. Group related components\n"
                "5. Focus on the architecture level view\n\n"
                "Specific PlantUML syntax for Component Diagrams:\n"
                "- Define components using [ComponentName] or component syntax\n"
                "- Define interfaces using () or interface syntax\n"
                "- Connect components using --> notation\n"
                "- Use package to group related components\n\n"
                "Example of valid component diagram syntax:\n"
                "@startuml\n"
                "package \"Frontend\" {\n"
                "  [Web UI]\n"
                "  [Mobile App]\n"
                "}\n"
                "package \"Backend\" {\n"
                "  [API Server]\n"
                "  [Database]\n"
                "}\n"
                "[Web UI] --> [API Server]\n"
                "[Mobile App] --> [API Server]\n"
                "[API Server] --> [Database]\n"
                "@enduml\n\n"
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
            "ALSO MAKE SURE THE UML CODE IS VALID\n"
            "Start with @startuml and end with @enduml.\n"
        )

        client = GptClient()
        resp, code = client.send_request(prompt=prompt, engine="gpt-4.1", is_json=False)
        data = resp
        if not data or not isinstance(data, str):
            diagram.generation_status = GENERATION_STATUS_FAILED
            diagram.generation_error = "Invalid or empty response"
            diagram.generation_completed_at = timezone.now()
            diagram.save()
            return {"error": "Invalid UML diagram content", "detail": data}
        plantuml_code = data
        if plantuml_code.startswith("```plantuml"):
            plantuml_code = plantuml_code[11:]
        if plantuml_code.startswith("```"):
            plantuml_code = plantuml_code[3:]
        if "@startuml" not in plantuml_code:
            plantuml_code = "@startuml\n" + plantuml_code
        if "@enduml" not in plantuml_code:
            plantuml_code += "\n@enduml"
        if plantuml_code.endswith("```"):
            plantuml_code = plantuml_code[:-3]
        diagram.content = plantuml_code
        diagram.generation_status = GENERATION_STATUS_COMPLETED
        diagram.generation_completed_at = timezone.now()
        diagram.save()

        return {
            "success": True,
            "diagram_id": str(diagram.id),
            "diagram_type": diagram_type
        }
    except Exception as e:
        logger.error(f"Error generating UML diagram: {str(e)}")
        if diagram:
            diagram.generation_status = GENERATION_STATUS_FAILED
            diagram.generation_error = f"Error generating UML diagram: {str(e)}"
            diagram.generation_completed_at = timezone.now()
            diagram.save()
        return {"error": f"Error generating UML diagram: {str(e)}"}


@app.task
def generate_mockups_task(project_id, user_story_id=None, requirement_id=None, mockup_id=None, feedback=None):
    logger.error(f"Generating mockups for project {project_id}")
    try:
        project = Project.objects.get(id=project_id)
    except ObjectDoesNotExist:
        return {"error": "Project not found"}
    if mockup_id:
        try:
            mockup = Mockup.objects.get(id=mockup_id)
            mockup.generation_status = GENERATION_STATUS_IN_PROGRESS
            mockup.generation_started_at = timezone.now()
            mockup.save()
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
            user_stories = UserStory.objects.filter(
                requirement__project_id=project_id,
                status__in=[STATUS_ACTIVE, STATUS_DRAFT]
            )
            if not user_stories.exists():
                requirements = project.requirements.filter(
                    status__in=[STATUS_ACTIVE, STATUS_DRAFT],
                    category__in=[REQUIREMENT_CATEGORY_UIUX, REQUIREMENT_CATEGORY_FUNCTIONAL]
                )
            else:
                requirements = []

    created_mockups = []
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
            previous_mockups = Mockup.objects.filter(
                project=project,
                requirement=requirement,
                status=STATUS_ACTIVE,
            ).update(
                status=STATUS_ARCHIVED,
            )
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
        user_stories = UserStory.objects.filter(requirement=requirement)
        user_stories_prompt = '\n'.join([
            f"{i+1}. As a {user_story.role}, I want to {user_story.action} so that {user_story.benefit}\n\n" for i, user_story in enumerate(user_stories)
        ])
        prompt += (
            f"Requirement:\n"
            f"Title: {requirement.title}\n"
            f"Category: {requirement.category}\n"
            f"Type: {requirement.requirement_type}\n"
            f"Description: {requirement.description}\n"
            f"User Stories: {user_stories_prompt}\n"
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
    client = GptClient()
    resp, code = client.send_request(prompt=prompt, engine="gpt-4.1", is_json=True)

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
    html_content = html_content.replace("<script", "<!-- script").replace("</script>", "<!-- /script -->")
    html_content = f"""
        {html_content}
    """

    return {
        "name": name,
        "html_content": html_content
    }
