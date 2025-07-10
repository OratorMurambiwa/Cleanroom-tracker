
from django.contrib import admin
from django.urls import path
from tracker import views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.custom_login_view, name='custom_login'),
    path('tasks/', views.tasks_view, name='tasks'),
    path('dashboard/', views.role_based_redirect, name='dashboard'),
    path('lead-dashboard/', views.lead_dashboard, name='lead_dashboard'),
    path('tech-dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('submit_task/<int:task_id>/', views.submit_task, name='submit_task'),
    path('approve_task/<int:task_id>/', views.approve_task, name='approve_task'),
    path('project/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('assign_tasks/', views.assign_tasks_view, name='assign_tasks'),
    path('my-tasks/', views.tech_task_list, name='tech_tasks'),
    path('tasks/<int:task_id>/', views.task_detail_view, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.edit_task_view, name='edit_task'),
    path('projects/', views.project_list_view, name='project_list')
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)