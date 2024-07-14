from django.urls import path
from users.views import CustomRegisterView

urlpatterns = [
    path('registration/', CustomRegisterView.as_view(), name='custom_registration'),
]
