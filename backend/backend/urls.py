from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from tracker import views
from tracker.views import asset_lookup_view, tech_components_view, register_view

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Landing & Auth
    path('', views.landing_page, name='landing'),
    path('login/', views.custom_login_view, name='custom_login'),
    path('register/', register_view, name='register'),
    path('logout/', views.LogoutView, name='logout'),
    path('dashboard/', views.role_based_redirect, name='dashboard'),

    # Settings
    path('settings/', views.settings_view, name='settings'),

    # Calendar & Reminders
    path('calendar/', views.calendar_view, name='calendar'),
    path('create_reminder/', views.create_reminder, name='create_reminder'),
    path('delete_reminder/<int:reminder_id>/', views.delete_reminder, name='delete_reminder'),

    # Dashboards
    path('lead-dashboard/', views.lead_dashboard, name='lead_dashboard'),
    path('tech-dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('technician-dashboard/', views.technician_dashboard, name='technician_dashboard'),

    # Tasks
    path('assign_tasks/', views.assign_tasks_view, name='assign_tasks'),
    path('my-tasks/', views.tech_tasks_view, name='tech_tasks'),
    path('all-tasks/', views.all_tasks_view, name='all_tasks'),
    path('view-pending-tasks/', views.view_pending_tasks, name='view_pending_tasks'),
    path('tasks/<int:task_id>/', views.task_detail_view, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.edit_task_view, name='edit_task'),
    path('tasks/<int:task_id>/submit/', views.submit_task, name='submit_task'),
    path('tasks/<int:task_id>/approve/', views.approve_task, name='approve_task'),
    path('tasks/<int:task_id>/review/', views.review_task_for_approval, name='review_task_for_approval'),
    path('tasks/<int:task_id>/delete/', views.delete_task_view, name='delete_task'),
    path('upload-doc-tasks/', views.upload_tasks_from_traveler_view, name='upload_doc_tasks'),
    path('upload-traveler/', views.upload_tasks_from_traveler_view, name='upload_tasks_from_traveler'),
    path('preview-extracted-tasks/', views.preview_extracted_tasks, name='preview_extracted_tasks'),
    path('save-extracted-tasks/', views.save_extracted_tasks, name='save_extracted_tasks'),
    path('tasks/save-extracted/', views.save_extracted_tasks, name='save_extracted_tasks'),
    path('assign-task/', views.assign_single_task, name='assign_single_task'),
    path('preview-edit-task/<int:index>/', views.edit_preview_task, name='edit_preview_task'),

    # Projects
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('projects/<int:project_id>/create-task/', views.create_task_view, name='create_task'),
    path('projects/<int:project_id>/add-task/', views.add_tasks_view, name='add_tasks'),
    path('projects/<int:project_id>/assign-user/', views.assign_user_view, name='assign_user'),
    path('projects/<int:project_id>/upload-document/', views.upload_document_view, name='upload_document'),
    path('projects/<int:project_id>/add-component/', views.add_component, name='add_component'),
    path('projects/<int:project_id>/add-team-member/', views.add_team_member, name='add_team_member'),
    path('projects/<int:project_id>/messages/', views.project_messages_view, name='project_messages'),
    path('project-task/<int:task_id>/', views.project_task_detail_view, name='project_task_detail'),

    # Components
    path('components/', views.components_view, name='components'),
    path('component-list/', views.component_list_view, name='component_list'),
    path('create_component/', views.create_component_view, name='create_component'),
    path('components/<int:component_id>/', views.component_detail_view, name='component_detail'),
    path('components/<int:component_id>/edit/', views.edit_component, name='edit_component'),
    path('components/<int:component_id>/assign-task/', views.assign_tasks_view, name='assign_component_task'),
    path('components/task/<int:task_id>/', views.component_task_detail_view, name='component_task_detail'),
    path('component-tasks/<int:task_id>/', views.component_task_completed_view, name='component_task_completed'),

    # Tech-specific Views
    path('tech/projects/', views.tech_project_list_view, name='tech_project_list'),
    path('tech/projects/<int:project_id>/', views.tech_project_detail_view, name='tech_project_detail'),
    path('tech/components/', views.tech_components_view, name='tech_components'),
    path('tech/components/<int:component_id>/', views.tech_component_detail_view, name='tech_component_detail'),
    path('create-project/', views.create_project, name='create_project'),
    path('alerts/', views.alerts_view, name='alerts'),
    path('settings/', views.settings_view, name='settings'),
    path('api/tasks/<int:task_id>/', views.task_detail_api, name='task_detail_api'),


    # Lookup
    path('asset-lookup/', asset_lookup_view, name='asset_lookup'),
]

# Serve media files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
