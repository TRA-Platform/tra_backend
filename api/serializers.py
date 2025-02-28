from rest_framework import serializers
from .models import *


class ProjectListSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()
    status = serializers.CharField(source='get_status_display')

    class Meta:
        model = Project
        fields = ['id', 'name', 'owner', 'status', 'created_at']


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['name', 'description', 'template']


class ProjectDetailSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()
    template = serializers.StringRelatedField()
    requirements = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = '__all__'

    def get_requirements(self, obj):
        return RequirementListSerializer(obj.requirement_set.all(), many=True).data


class RequirementListSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    priority = serializers.CharField(source='get_priority_display')

    class Meta:
        model = Requirement
        fields = ['id', 'title', 'category', 'priority', 'created_at']


class RequirementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requirement
        fields = ['project', 'category', 'title', 'description', 'priority']


class RequirementDetailSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField()
    category = serializers.StringRelatedField()
    comments = serializers.SerializerMethodField()
    changelog = serializers.SerializerMethodField()

    class Meta:
        model = Requirement
        fields = '__all__'

    def get_comments(self, obj):
        return CommentSerializer(obj.comment_set.all(), many=True).data

    def get_changelog(self, obj):
        return ChangeLogSerializer(obj.requirementchangelog_set.all(), many=True).data


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField()

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ['author', 'created_at']


class ChangeLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = RequirementChangeLog
        fields = '__all__'
        read_only_fields = ['user', 'changed_at']


class WorkerTaskListSerializer(serializers.ModelSerializer):
    task_type = serializers.CharField(source='get_task_type_display')
    status = serializers.CharField(source='get_status_display')

    class Meta:
        model = WorkerTask
        fields = ['id', 'task_type', 'status', 'created_at', 'completed_at']


class WorkerTaskDetailSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField()
    requirement = serializers.StringRelatedField()

    class Meta:
        model = WorkerTask
        fields = '__all__'