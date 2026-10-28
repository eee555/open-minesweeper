from django.urls import path

from . import views
app_name = 'accountlink'
urlpatterns = [
    path('delete/', views.delete_link),
    path('update/', views.update_link),
    path('saolei/videolist/get/', views.view_saolei_get_import_list),
    path('saolei/videoimport/stat/', views.view_saolei_get_import_summary),
]
