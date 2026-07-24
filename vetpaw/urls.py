from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .health import health_check

handler404 = 'vetpaw.errors.api_not_found'
handler500 = 'vetpaw.errors.api_server_error'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='api-health'),
    path('api/users/', include('users.urls')),
    path('api/', include('pets.urls')),
    path('api/', include('clinics.urls')),
    path('api/', include('appointments.urls')),
    path('api/', include('messaging.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include('lost_pets.urls')),
    path('api/', include('contact.urls')),
    path('api/', include('ads.urls')),
    path('api/', include('blog.urls')),
    path('api/', include('community.urls')),
    path('api/', include('partners.urls')),
    path('api/', include('adoptions.urls')),
    path('api/', include('commerce.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)