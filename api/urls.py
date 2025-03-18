from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SrsTemplateViewSet, ProjectViewSet, RequirementViewSet,
    RequirementCommentViewSet, DevelopmentPlanViewSet,
    DevelopmentPlanVersionViewSet, MockupViewSet
)

router = DefaultRouter()
router.register("srs-templates", SrsTemplateViewSet, basename="srs-template")
router.register("projects", ProjectViewSet, basename="project")
router.register("requirements", RequirementViewSet, basename="requirement")
router.register("requirement-comments", RequirementCommentViewSet, basename="requirement-comment")
router.register("development-plans", DevelopmentPlanViewSet, basename="development-plan")
router.register("development-plan-versions", DevelopmentPlanVersionViewSet, basename="development-plan-version")
router.register("mockups", MockupViewSet, basename="mockup")

urlpatterns = [
    path("", include(router.urls)),
]
