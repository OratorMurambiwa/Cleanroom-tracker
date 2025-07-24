from django.contrib import admin
from django.urls import path
from tracker import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('', views.custom_login_view, name='custom_login'),
    path('dashboard/', views.role_based_redirect, name='dashboard'),

    # Dashboards
    path('lead-dashboard/', views.lead_dashboard, name='lead_dashboard'),
    path('tech-dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('technician-dashboard/', views.technician_dashboard, name='technician_dashboard'),

    # Projects
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('create_project/', views.create_project_view, name='create_project'),
    path('projects/<int:project_id>/create-task/', views.create_task_view, name='create_task'),
    path('projects/<int:project_id>/add-task/', views.add_tasks_view, name='add_tasks'),
    path('projects/<int:project_id>/assign-user/', views.assign_user_view, name='assign_user'),
    path('projects/<int:project_id>/upload-document/', views.upload_document_view, name='upload_document'),
    path('projects/<int:project_id>/add-component/', views.add_component, name='add_component'),
    path('projects/<int:project_id>/add-team-member/', views.add_team_member, name='add_team_member'),
    path('tech/projects/', views.tech_project_list, name='tech_project_list'),
    path('project-task/<int:task_id>/', views.project_task_detail_view, name='project_task_detail'),
    path('tech/projects/<int:project_id>/', views.tech_project_detail_view, name='tech_project_detail'),

    # Tasks
    path('assign_tasks/', views.assign_tasks_view, name='assign_tasks'),
    path('my-tasks/', views.tech_tasks_view, name='tech_tasks'),  # ✅ renamed from tech_task_list to tech_tasks
    path('tasks/<int:task_id>/', views.task_detail_view, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.edit_task_view, name='edit_task'),
    path('tasks/<int:task_id>/submit/', views.submit_task, name='submit_task'),
    path('submit_task/<int:task_id>/', views.submit_task, name='submit_task'),
    path('tasks/<int:task_id>/approve/', views.approve_task, name='approve_task'),
    path('components/<int:component_id>/assign-task/', views.assign_tasks_view, name='assign_task_component'),

    path('tasks/<int:task_id>/review/', views.review_task_for_approval, name='review_task_for_approval'),
    path('tasks/save-extracted/', views.save_extracted_tasks, name='save_extracted_tasks'),

    # Components
    path('components/', views.components_view, name='components'),
    path('component-list/', views.component_list_view, name='component_list'),
    path('create_component/', views.create_component_view, name='create_component'),
    path('components/<int:component_id>/', views.component_detail_view, name='component_detail'),
    path('components/task/<int:task_id>/', views.component_task_detail_view, name='component_task_detail'),
    path('component-tasks/<int:task_id>/', views.component_task_completed_view, name='component_task_completed'),
    path('components/<int:component_id>/assign-task/', views.assign_tasks_view, name='assign_component_task'),
    path('tech/components/<int:component_id>/', views.tech_component_detail_view, name='tech_component_detail'),
    path('components/<int:component_id>/edit/', views.edit_component, name='edit_component'),


    # Calendar and Reminders
    path('calendar/', views.calendar_view, name='calendar'),
    path('create_reminder/', views.create_reminder, name='create_reminder'),
]

# Serve media files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
