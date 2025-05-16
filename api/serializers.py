from openai import project
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    SrsTemplate, Project, Requirement, RequirementHistory,
    RequirementComment, DevelopmentPlan, DevelopmentPlanVersion,
    Mockup, MockupHistory, UserStory, UserStoryHistory, UserStoryComment,
    UmlDiagram, STATUS_ARCHIVED, UML_DIAGRAM_TYPE_CLASS, UML_DIAGRAM_TYPE_ACTIVITY, UML_DIAGRAM_TYPE_SEQUENCE,
    UML_DIAGRAM_TYPE_COMPONENT, SrsExport
)
from .tasks import generate_development_plan_task
from webauth.serializers import ProjectRoleSerializer


class SrsTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SrsTemplate
        fields = "__all__"


class UmlDiagramSerializer(serializers.ModelSerializer):
    generation_details = serializers.SerializerMethodField()

    class Meta:
        model = UmlDiagram
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "generation_status",
                            "generation_started_at", "generation_completed_at", "generation_error",
                            "generation_details")

    def get_generation_details(self, obj):
        return {
            "status": obj.generation_status,
            "started_at": obj.generation_started_at,
            "completed_at": obj.generation_completed_at,
            "error": obj.generation_error,
            "duration": (obj.generation_completed_at - obj.generation_started_at).total_seconds()
            if obj.generation_completed_at and obj.generation_started_at else None,
            "is_valid": bool(obj.content and "@startuml" in obj.content and "@enduml" in obj.content),
            "content_length": len(obj.content) if obj.content else 0
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")


class UserStoryHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = UserStoryHistory
        fields = "__all__"


class UserStoryCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserStoryComment
        fields = "__all__"
        read_only_fields = ("id", "created_at", "user")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class UserStorySerializer(serializers.ModelSerializer):
    history = UserStoryHistorySerializer(many=True, read_only=True)
    comments = UserStoryCommentSerializer(many=True, read_only=True)
    requirement = serializers.SerializerMethodField()
    mockups = serializers.SerializerMethodField()

    class Meta:
        model = UserStory
        fields = (
            "id", "requirement", "role", "action", "benefit",
            "acceptance_criteria", "version_number", "generation_status",
            "generation_started_at", "generation_completed_at", "generation_error",
            "status", "created_at", "updated_at", "history", "comments", "mockups"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at",
                            "history", "comments", "generation_status",
                            "generation_started_at", "generation_completed_at",
                            "generation_error", "mockups")

    def update(self, instance, validated_data):
        user = self.context["request"].user
        UserStoryHistory.objects.create(
            user_story=instance,
            role=instance.role,
            action=instance.action,
            benefit=instance.benefit,
            acceptance_criteria=instance.acceptance_criteria,
            version_number=instance.version_number,
            changed_by=user,
            status=instance.status
        )
        instance.role = validated_data.get("role", instance.role)
        instance.action = validated_data.get("action", instance.action)
        instance.benefit = validated_data.get("benefit", instance.benefit)
        instance.acceptance_criteria = validated_data.get("acceptance_criteria", instance.acceptance_criteria)
        instance.status = validated_data.get("status", instance.status)
        instance.version_number += 1
        instance.save()
        return instance

    def get_requirement(self, obj):
        return obj.requirement.title

    def get_mockups(self, obj):
        mockups = Mockup.objects.filter(
            user_story=obj,
        ).exclude(status=STATUS_ARCHIVED)
        return MockupSerializerShort(mockups, many=True).data


class MockupHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = MockupHistory
        fields = "__all__"


class RequirementHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = RequirementHistory
        fields = "__all__"


class RequirementCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    responsible_user = UserSerializer(read_only=True)

    class Meta:
        model = RequirementComment
        fields = "__all__"
        read_only_fields = ("id", "created_at", "user")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class MockupSerializer(serializers.ModelSerializer):
    requirement_name = serializers.SerializerMethodField()
    user_story_name = serializers.SerializerMethodField()

    class Meta:
        model = Mockup
        fields = [
            'id', 'project', 'requirement', 'user_story', 'name',
            'html_content', 'image', 'created_by', 'version_number',
            'generation_status', 'generation_started_at',
            'generation_completed_at', 'generation_error',
            'needs_regeneration', 'last_associated_change',
            'status', 'created_at', 'updated_at',
            'requirement_name', 'user_story_name',
        ]
        read_only_fields = [
            'id', 'created_by', 'version_number',
            'generation_status', 'generation_started_at',
            'generation_completed_at', 'generation_error', 'last_associated_change',
            'created_at', 'updated_at',
            'requirement_name', 'user_story_name',
            'image',
        ]

    def get_requirement_name(self, obj):
        if obj.requirement:
            return obj.requirement.title
        return None

    def get_user_story_name(self, obj):
        if obj.user_story:
            return str(obj.user_story)
        return None

class MockupSerializerShort(serializers.ModelSerializer):
    requirement_name = serializers.SerializerMethodField()
    user_story_name = serializers.SerializerMethodField()

    class Meta:
        model = Mockup
        fields = [
            'id', 'project', 'requirement', 'user_story', 'name', 'image', 'created_by', 'version_number',
            'generation_status', 'generation_started_at',
            'generation_completed_at', 'generation_error',
            'needs_regeneration', 'last_associated_change',
            'status', 'created_at', 'updated_at',
            'requirement_name', 'user_story_name',
        ]
        read_only_fields = [
            'id', 'created_by', 'version_number',
            'generation_status', 'generation_started_at',
            'generation_completed_at', 'generation_error',
            'needs_regeneration', 'last_associated_change',
            'created_at', 'updated_at',
            'requirement_name', 'user_story_name',
            'image',
        ]

    def get_requirement_name(self, obj):
        if obj.requirement:
            return obj.requirement.title
        return None

    def get_user_story_name(self, obj):
        if obj.user_story:
            return str(obj.user_story)
        return None


class SrsExportSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    template = SrsTemplateSerializer(read_only=True)

    class Meta:
        model = SrsExport
        fields = (
            "id", "status", "template",
            "url", "fmt", "created_by", "created_at"
        )
        read_only_fields = (
            "id", "created_by", "created_at", "url"
        )

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class RequirementDetailSerializer(serializers.ModelSerializer):
    history = RequirementHistorySerializer(many=True, read_only=True)
    comments = RequirementCommentSerializer(many=True, read_only=True)
    user_stories = serializers.SerializerMethodField()
    mockups = MockupSerializerShort(many=True, read_only=True)
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Requirement
        fields = (
            "id", "project", "parent", "children", "title", "handle", "description",
            "category", "requirement_type", "version_number", "status",
            "created_at", "updated_at", "history", "comments", "user_stories", "mockups"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at",
                            "history", "comments", "user_stories", "mockups", "handle")

    def get_user_stories(self, obj):
        user_stories = [story for story in obj.user_stories.all() if story.status != STATUS_ARCHIVED]
        return UserStorySerializer(user_stories, many=True).data

    def get_parent(self, obj):
        if obj.parent:
            return {
                'id': obj.parent.id,
                'title': obj.parent.title
            }
        return None

    def get_children(self, obj):
        children = obj.children.all()
        if children:
            return [{'id': child.id, 'title': child.title} for child in children]
        return []

    def update(self, instance, validated_data):
        user = self.context["request"].user
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
        instance.title = validated_data.get("title", instance.title)
        instance.description = validated_data.get("description", instance.description)
        instance.category = validated_data.get("category", instance.category)
        instance.requirement_type = validated_data.get("requirement_type", instance.requirement_type)
        instance.parent = validated_data.get("parent", instance.parent)
        instance.status = validated_data.get("status", instance.status)
        instance.version_number += 1
        instance.save()
        return instance


class RequirementSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Requirement.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Requirement
        fields = (
            "id", "project", "parent", "title", "handle", "description", "category",
            "requirement_type", "version_number", "status", "created_at", "updated_at"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at", "handle")


class DevelopmentPlanVersionSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    uml_diagrams = UmlDiagramSerializer(many=True, read_only=True)
    generation_progress = serializers.SerializerMethodField()

    class Meta:
        model = DevelopmentPlanVersion
        fields = "__all__"
        read_only_fields = ("id", "created_at", "created_by", "uml_diagrams", "generation_progress")

    def get_generation_progress(self, obj):
        diagrams = UmlDiagram.objects.filter(plan_version=obj)
        total_diagrams = diagrams.count()
        completed_diagrams = diagrams.filter(generation_status=STATUS_ARCHIVED).count()

        return {
            "total_diagrams": total_diagrams,
            "completed_diagrams": completed_diagrams,
            "progress_percentage": (completed_diagrams / total_diagrams * 100) if total_diagrams > 0 else 0,
            "diagram_types": {
                diagram_type: diagrams.filter(diagram_type=diagram_type).count()
                for diagram_type in [UML_DIAGRAM_TYPE_CLASS, UML_DIAGRAM_TYPE_SEQUENCE,
                                     UML_DIAGRAM_TYPE_ACTIVITY, UML_DIAGRAM_TYPE_COMPONENT]
            }
        }


class DevelopmentPlanSerializer(serializers.ModelSerializer):
    versions = DevelopmentPlanVersionSerializer(many=True, read_only=True)

    class Meta:
        model = DevelopmentPlan
        fields = (
            "id", "project", "current_version_number", "hourly_rates",
            "status", "created_at", "updated_at", "versions"
        )
        read_only_fields = ("id", "created_at", "updated_at", "versions")
    
    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        generate_development_plan_task.delay(str(validated_data["project"].id), user_id=str(self.context["request"].user.id))
        return super().create(validated_data)


class ProjectListSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description",
            "type_of_application", "operating_systems", "language", "status",
            "generation_status", "deadline_start", "deadline_end",
            "created_at", "updated_at",
            "requirements_total", "requirements_completed",
            "user_stories_total", "user_stories_completed",
            "mockups_total", "mockups_completed",
            "uml_diagrams_total", "uml_diagrams_completed",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    requirements = RequirementDetailSerializer(many=True, read_only=True)
    mockups = serializers.SerializerMethodField()
    uml_diagrams = UmlDiagramSerializer(many=True, read_only=True)
    development_plan = DevelopmentPlanSerializer(read_only=True)
    user_stories = serializers.SerializerMethodField()
    generation_progress = serializers.SerializerMethodField()
    srs_exports = serializers.SerializerMethodField()
    roles = ProjectRoleSerializer(many=True, read_only=True)
    requirements_total = serializers.IntegerField(read_only=True)
    requirements_completed = serializers.IntegerField(read_only=True)
    user_stories_total = serializers.IntegerField(read_only=True)
    user_stories_completed = serializers.IntegerField(read_only=True)
    mockups_total = serializers.IntegerField(read_only=True)
    mockups_completed = serializers.IntegerField(read_only=True)
    uml_diagrams_total = serializers.IntegerField(read_only=True)
    uml_diagrams_completed = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description",
            "type_of_application", "color_scheme", "language",
            "application_description", "target_users", "additional_requirements",
            "non_functional_requirements", "technology_stack", "operating_systems",
            "priority_modules", "deadline_start", "deadline_end", "preliminary_budget",
            "scope", "generation_status", "generation_started_at",
            "generation_completed_at", "generation_error", "status",
            "created_at", "updated_at", "requirements", "mockups",
            "development_plan", "uml_diagrams", "user_stories", "generation_progress",
            "srs_exports",
            "requirements_total", "requirements_completed",
            "user_stories_total", "user_stories_completed",
            "mockups_total", "mockups_completed",
            "uml_diagrams_total", "uml_diagrams_completed",
            "roles",
        )
        read_only_fields = (
            "id", "created_by", "created_at", "updated_at", "requirements",
            "generation_status", "generation_started_at", "generation_completed_at",
            "generation_error", "generation_progress", "srs_exports"
        )

    def create(self, validated_data):
        print(validated_data)
        validated_data["created_by"] = self.context["request"].user
        project = super().create(validated_data)
        from .tasks import generate_requirements_task
        generate_requirements_task.delay(str(project.id), user_id=str(self.context["request"].user.id))
        return project

    def get_srs_exports(self, obj):
        return SrsExportSerializer(obj.exports.all(), many=True).data

    def get_user_stories(self, obj):
        all_stories = []
        for req in obj.requirements.all():
            for story in req.user_stories.all():
                if story.status != STATUS_ARCHIVED:
                    all_stories.append(story)
        return UserStorySerializer(all_stories, many=True).data

    def get_generation_progress(self, obj):
        return {
            "requirements": {
                "total": obj.requirements_total,
                "completed": obj.requirements_completed,
                "status": obj.generation_status,
                "started_at": obj.generation_started_at,
                "completed_at": obj.generation_completed_at,
                "error": obj.generation_error
            },
            "user_stories": {
                "total": obj.user_stories_total,
                "completed": obj.user_stories_completed
            },
            "mockups": {
                "total": obj.mockups_total,
                "completed": obj.mockups_completed
            },
            "uml_diagrams": {
                "total": obj.uml_diagrams_total,
                "completed": obj.uml_diagrams_completed
            }
        }

    def get_mockups(self, obj):
        mockups = [m for m in obj.mockups.all() if m.status != STATUS_ARCHIVED]
        return MockupSerializerShort(mockups, many=True).data
