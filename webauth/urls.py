from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from webauth.views import (
    get_me,
    RegisterView,
    RegisterAdminView,
    MyObtainTokenPairView,
    ChangePasswordView,
    ProjectRoleView,
    ProjectRoleDetailView
)

urlpatterns = [
    path('login/', MyObtainTokenPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('register/admin/', RegisterAdminView.as_view(), name='register_admin'),
    path('me/', get_me, name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('projects/<uuid:project_id>/roles/', ProjectRoleView.as_view(), name='project_roles'),
    path('projects/<uuid:project_id>/roles/<uuid:pk>/', ProjectRoleDetailView.as_view(), name='project_role_detail'),
]
