from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    SrsTemplate, Project, Requirement, RequirementHistory,
    RequirementComment, DevelopmentPlan, DevelopmentPlanVersion, Mockup
)


class SrsTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SrsTemplate
        fields = "__all__"


class RequirementHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = RequirementHistory
        fields = "__all__"

    def get_changed_by(self, obj):
        return obj.changed_by.username


class RequirementCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementComment
        fields = "__all__"
        read_only_fields = ("id", "created_at", "user")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class RequirementSerializer(serializers.ModelSerializer):
    history = RequirementHistorySerializer(many=True, read_only=True)
    comments = RequirementCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Requirement
        fields = (
            "id", "project", "title", "description", "category",
            "version_number", "status", "created_at", "updated_at",
            "history", "comments"
        )
        read_only_fields = ("id", "version_number", "created_at", "updated_at", "history", "comments")

    def update(self, instance, validated_data):
        user = self.context["request"].user
        RequirementHistory.objects.create(
            requirement=instance,
            title=instance.title,
            description=instance.description,
            category=instance.category,
            version_number=instance.version_number,
            changed_by=user,
            status=instance.status
        )
        instance.title = validated_data.get("title", instance.title)
        instance.description = validated_data.get("description", instance.description)
        instance.category = validated_data.get("category", instance.category)
        instance.status = validated_data.get("status", instance.status)
        instance.version_number += 1
        instance.save()
        return instance


class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description",
            "type_of_application", "color_scheme", "language", "status",
            "created_at", "updated_at"
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class DevelopmentPlanVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevelopmentPlanVersion
        fields = "__all__"
        read_only_fields = ("id", "created_at", "created_by")


class DevelopmentPlanSerializer(serializers.ModelSerializer):
    versions = DevelopmentPlanVersionSerializer(many=True, read_only=True)

    class Meta:
        model = DevelopmentPlan
        fields = (
            "id", "project", "current_version_number", "status",
            "created_at", "updated_at", "versions"
        )
        read_only_fields = ("id", "current_version_number", "created_at", "updated_at", "versions")


class MockupSerializer(serializers.ModelSerializer):
    requirement = serializers.SerializerMethodField()
    class Meta:
        model = Mockup
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def get_requirement(self, obj):
        return obj.requirement.title if obj.requirement else None


class ProjectSerializer(serializers.ModelSerializer):
    requirements = RequirementSerializer(many=True, read_only=True)
    mockups = MockupSerializer(many=True, read_only=True)
    development_plan = DevelopmentPlanSerializer(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "created_by", "name", "short_description", "srs_template",
            "type_of_application", "color_scheme", "language",
            "application_description", "target_users", "additional_requirements",
            "non_functional_requirements", "technology_stack", "operating_system",
            "priority_modules", "deadline", "preliminary_budget", "status",
            "created_at", "updated_at", "requirements", "mockups", "development_plan"
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at", "requirements")

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
