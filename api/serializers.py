from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    SrsTemplate, Project, Requirement, RequirementHistory,
    RequirementComment, DevelopmentPlan, DevelopmentPlanVersion,
    Mockup, MockupHistory, UserStory, UserStoryHistory, UserStoryComment,
    UmlDiagram
)


class SrsTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SrsTemplate
        fields = "__all__"


class UmlDiagramSerializer(serializers.ModelSerializer):
    class Meta:
        model = UmlDiagram
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "generation_status",
                            "generation_started_at", "generation_completed_at", "generation_error")


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

    class Meta:
        model = UserStory
        fields = (
            "id", "requirement", "role", "action", "benefit",
            "acceptance_criteria", "version_number", "generation_status",
            "generation_started_at", "generation_completed_at", "generation_error",
            "status", "created_at", "updated_at", "history", "comments"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at",
                            "history", "comments", "generation_status",
                            "generation_started_at", "generation_completed_at",
                            "generation_error")

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
    requirement = serializers.SerializerMethodField()
    user_story = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)
    history = MockupHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Mockup
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "created_by",
                            "generation_status", "generation_started_at",
                            "generation_completed_at", "generation_error",
                            "history")

    def get_requirement(self, obj):
        return obj.requirement.title if obj.requirement else None

    def get_user_story(self, obj):
        if obj.user_story:
            return f"As a {obj.user_story.role}, I want to {obj.user_story.action}"
        return None

    def update(self, instance, validated_data):
        user = self.context["request"].user
        MockupHistory.objects.create(
            mockup=instance,
            html_content=instance.html_content,
            version_number=instance.version_number,
            changed_by=user,
            status=instance.status
        )

        instance.name = validated_data.get("name", instance.name)
        instance.html_content = validated_data.get("html_content", instance.html_content)
        instance.requirement = validated_data.get("requirement", instance.requirement)
        instance.user_story = validated_data.get("user_story", instance.user_story)
        instance.status = validated_data.get("status", instance.status)
        instance.version_number += 1
        instance.save()
        return instance


class RequirementDetailSerializer(serializers.ModelSerializer):
    history = RequirementHistorySerializer(many=True, read_only=True)
    comments = RequirementCommentSerializer(many=True, read_only=True)
    user_stories = UserStorySerializer(many=True, read_only=True)
    mockups = MockupSerializer(many=True, read_only=True)
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Requirement
        fields = (
            "id", "project", "parent", "children", "title", "description",
            "category", "requirement_type", "version_number", "status",
            "created_at", "updated_at", "history", "comments", "user_stories", "mockups"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at",
                            "history", "comments", "user_stories", "mockups")

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
            "id", "project", "parent", "title", "description", "category",
            "requirement_type", "version_number", "status", "created_at", "updated_at"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at")


class DevelopmentPlanVersionSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    uml_diagrams = UmlDiagramSerializer(many=True, read_only=True)

    class Meta:
        model = DevelopmentPlanVersion
        fields = "__all__"
        read_only_fields = ("id", "created_at", "created_by", "uml_diagrams")


class DevelopmentPlanSerializer(serializers.ModelSerializer):
    versions = DevelopmentPlanVersionSerializer(many=True, read_only=True)

    class Meta:
        model = DevelopmentPlan
        fields = (
            "id", "project", "current_version_number", "hourly_rates",
            "status", "created_at", "updated_at", "versions"
        )
        read_only_fields = ("id", "current_version_number", "created_at", "updated_at", "versions")


class ProjectListSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description",
            "type_of_application", "operating_systems", "language", "status",
            "generation_status", "deadline_start", "deadline_end",
            "created_at", "updated_at"
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    requirements = RequirementSerializer(many=True, read_only=True)
    mockups = MockupSerializer(many=True, read_only=True)
    development_plan = DevelopmentPlanSerializer(read_only=True)
    uml_diagrams = UmlDiagramSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description", "srs_template",
            "type_of_application", "color_scheme", "language",
            "application_description", "target_users", "additional_requirements",
            "non_functional_requirements", "technology_stack", "operating_systems",
            "priority_modules", "deadline_start", "deadline_end", "preliminary_budget",
            "scope", "generation_status", "generation_started_at",
            "generation_completed_at", "generation_error", "status",
            "created_at", "updated_at", "requirements", "mockups",
            "development_plan", "uml_diagrams"
        )
        read_only_fields = (
            "id", "created_by", "created_at", "updated_at", "requirements",
            "generation_status", "generation_started_at", "generation_completed_at",
            "generation_error"
        )

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)