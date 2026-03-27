from django.urls import path
from .push_views import PushDataView

urlpatterns = [
    path('data/', PushDataView.as_view(), name='push-data'),
]
