from django.urls import path
from .views import RetentionPolicyView

urlpatterns = [
    path('', RetentionPolicyView.as_view(), name='retention-policy'),
]
