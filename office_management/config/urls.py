"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/',include('app.accounts.urls')),
    path('clients/',include('app.clients.urls')),
    path('projects/',include('app.projects.urls')),
    path('employees/',include('app.employees.urls')),
    path('location_master/',include('app.location_master.urls')),
    path('payments/',include('app.payments.urls')),
    path('vendors/',include('app.vendors.urls')),
    path('expenses/',include('app.expenses.urls')),
    path('social_media/',include('app.social_media.urls')),
    path('attendance/', include("app.attendance.urls")),
    path('calendar/', include("app.calendar_app.urls")),
]
