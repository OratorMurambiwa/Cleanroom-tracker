# views/__init__.py

from .dashboard_views import (
    home_dashboard,
    tech_dashboard,
    lead_dashboard,
)

from .task_views import (
    create_task,
    review_task_for_approval,
    all_tasks,
    edit_task,
    delete_task,
    assign_task,
)

from .project_views import (
    project_detail,
    create_project,
    edit_project,
    add_team_member,
)

from .message_views import (
    project_messages,
    send_message,
)

from .component_views import (
    add_component,
    edit_component,
    tech_components,
)

from .utils import (
    calculate_progress,
    filter_tasks,
)
