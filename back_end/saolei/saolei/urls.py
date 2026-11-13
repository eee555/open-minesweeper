"""
URL configuration for saolei project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path
from django.views.generic import TemplateView

from . import api


def serve_robots_txt(request):
    return FileResponse(
        open(os.path.join(settings.BASE_DIR, 'dist', 'robots.txt'), 'rb'),
        content_type='text/plain',
    )


urlpatterns = [
    path('api/', api.api.urls),
    path('video/', include('videomanager.urls')),
    path('userprofile/', include('userprofile.urls', namespace='userprofile')),
    path('admin/', admin.site.urls),
    # path('gsc/', include('gsc.urls')),
    path('article/', include('article.urls')),
    path('identifier/', include('identifier.urls')),
    path('robots.txt', serve_robots_txt),
    path(r'', TemplateView.as_view(template_name='index.html')),
]


if settings.DEBUG:
    # python manage.py runserver --nostatic
    urlpatterns += static(settings.STATIC_URL, document_root=settings.MEDIA_ROOT)

if settings.E2E_TEST:
    from dangerzone.api import api as dangerzone_api
    urlpatterns.append(path('dangerzone/', dangerzone_api.urls))
