from django.urls import path

from . import views
app_name = 'accountlink'
urlpatterns = [
    path('delete/', views.delete_link),
    path('update/', views.update_link),
]
