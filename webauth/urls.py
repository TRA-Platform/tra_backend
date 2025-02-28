from django.urls import path, include
from webauth.views import MyObtainTokenPairView, ChangePasswordView, RegisterAdminView, get_me
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', MyObtainTokenPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register-admin/', RegisterAdminView.as_view(), name='auth_register_admin'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    # path('2fa-setup/', TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('me/', get_me, name='get_me'),
]
