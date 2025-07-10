"""
URL configuration for backend project.

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
from django.urls import path
from tracker import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.custom_login_view, name='custom_login'),
    path('tasks/', views.tasks_view, name='tasks'),
    path('dashboard/', views.role_based_redirect, name='dashboard'),
    path('lead-dashboard/', views.lead_dashboard, name='lead_dashboard'),
    path('tech-dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('submit_task/<int:task_id>/', views.submit_task, name='submit_task'),
    path('approve_task/<int:task_id>/', views.approve_task, name='approve_task')
]
