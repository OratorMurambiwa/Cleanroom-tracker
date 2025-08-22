from .views import (
    assign_tasks_view,  # component-scoped create moved to views_components but keep export
    create_task_view,
    submit_task,
    approve_task,
    edit_task_view,
    review_task_for_approval,
    delete_task_view,
    task_detail_view,
    project_task_detail_view,
    component_task_detail_view,
    component_task_completed_view,
    all_tasks_view,
    view_pending_tasks,
)

__all__ = [
    'assign_tasks_view',
    'create_task_view',
    'submit_task',
    'approve_task',
    'edit_task_view',
    'review_task_for_approval',
    'delete_task_view',
    'task_detail_view',
    'project_task_detail_view',
    'component_task_detail_view',
    'component_task_completed_view',
    'all_tasks_view',
    'view_pending_tasks',
]


