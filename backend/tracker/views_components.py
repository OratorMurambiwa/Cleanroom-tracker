from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Component, Project, Task
from .forms import ComponentForm, DocumentForm


# ---------- Helpers (scoped here to avoid global imports) ----------

def _update_component_progress(component: Component) -> None:
    """Recalculate and save component progress based on approved tasks."""
    tasks_qs = Task.objects.filter(components=component)
    if not tasks_qs.exists():
        component.progress = 0
        component.save(update_fields=["progress"]) 
        return
    total = tasks_qs.count()
    approved = tasks_qs.filter(is_approved=True).count()
    component.progress = (approved / total) * 100
    component.save(update_fields=["progress"]) 


# ---------- Component Pages ----------

@login_required
def components_view(request):
    """List all components with filter controls rendered in the template."""
    components = Component.objects.all()
    projects = Project.objects.all()
    return render(request, 'tracker/components.html', {
        'components': components,
        'projects': projects,
    })


@login_required
def component_list_view(request):
    """Compact list variant (kept for legacy links)."""
    components = Component.objects.prefetch_related('projects').order_by('-updated_at')
    return render(request, 'tracker/component_list.html', {'components': components})


@login_required
def create_component_view(request):
    """Create a new component (name, description, progress) and optionally:
    - link it to a project
    - assign users to that linked project
    - upload a document and associate to the component and project (if selected)
    """
    form = ComponentForm(request.POST or None)
    technicians = User.objects.filter(groups__name='technician').exclude(is_superuser=True).exclude(username__iexact='admin')
    active_projects = Project.objects.filter(status='ongoing')

    if request.method == 'POST' and form.is_valid():
        component = form.save()

        # Link to a project if selected
        link_project_id = request.POST.get('link_project_id')
        linked_project = None
        if link_project_id:
            linked_project = active_projects.filter(id=link_project_id).first()
            if linked_project:
                component.projects.add(linked_project)

        # Assign users to the linked project (if any)
        assign_ids = request.POST.getlist('assign_user_ids')
        if linked_project and assign_ids:
            users_to_add = User.objects.filter(id__in=assign_ids).exclude(is_superuser=True).exclude(username__iexact='admin')
            for u in users_to_add:
                linked_project.assigned_users.add(u)

        # Optional document upload
        if 'file' in request.FILES:
            doc_form = DocumentForm(request.POST, request.FILES)
            if doc_form.is_valid():
                doc = doc_form.save(commit=False)
                doc.component = component
                if linked_project:
                    doc.project = linked_project
                doc.save()

        messages.success(request, "Component created successfully.")
        return redirect('lead_dashboard')

    context = {
        'form': form,
        'projects': active_projects,
        'technicians': technicians,
        'document_form': DocumentForm(),
    }
    return render(request, 'tracker/create_component.html', context)


@login_required
def add_component(request, project_id: int):
    """Create a component and link it to a given project (M2M)."""
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = ComponentForm(request.POST)
        if form.is_valid():
            component = form.save()
            component.projects.add(project)
            messages.success(request, "Component added!")
            return redirect('project_detail', project_id=project.id)
    else:
        form = ComponentForm()
    return render(request, 'tracker/add_component.html', {'form': form, 'project': project})


@login_required
def edit_component(request, component_id: int):
    """Edit a component and attach selected tasks through M2M."""
    component = get_object_or_404(Component, id=component_id)
    unlinked_tasks = Task.objects.filter(Q(components__isnull=True) | Q(components=component)).distinct()

    if request.method == 'POST':
        form = ComponentForm(request.POST, instance=component)
        if form.is_valid():
            form.save()
            task_ids = request.POST.getlist('tasks')
            if task_ids:
                for task in Task.objects.filter(id__in=task_ids):
                    task.components.add(component)
            return redirect('components')
    else:
        form = ComponentForm(instance=component)

    return render(request, 'components/edit_component.html', {
        'form': form,
        'component': component,
        'unlinked_tasks': unlinked_tasks
    })


@login_required
def component_detail_view(request, component_id: int):
    """Details page for a component: overview, tasks, projects, members, upload."""
    component = get_object_or_404(Component, id=component_id)
    _update_component_progress(component)

    active_projects = Project.objects.filter(status='ongoing')

    # Technicians who have tasks on this component (techs only)
    assigned_techs = User.objects.filter(
        id__in=component.tasks.values_list('assigned_to__id', flat=True),
        groups__name='technician'
    ).exclude(is_superuser=True).exclude(username__iexact='admin').distinct()

    # Members from all linked projects (union of assigned users)
    project_members = User.objects.filter(
        id__in=component.projects.values_list('assigned_users__id', flat=True)
    ).exclude(is_superuser=True).exclude(username__iexact='admin').distinct()

    # Techs from linked projects (to populate filter dropdown without leads)
    project_techs = User.objects.filter(
        id__in=component.projects.values_list('assigned_users__id', flat=True),
        groups__name='technician'
    ).exclude(is_superuser=True).exclude(username__iexact='admin').distinct()

    # Union of task techs and project techs
    filter_techs = (project_techs | assigned_techs).exclude(is_superuser=True).exclude(username__iexact='admin').distinct()

    # Users who are not yet members via any linked project (for add-member form)
    available_users = User.objects.exclude(id__in=project_members.values_list('id', flat=True)).exclude(is_superuser=True).exclude(username__iexact='admin')

    # --- Tasks filtering (GET) ---
    tasks = component.tasks.select_related('assigned_to').all()
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    assigned_to_filter = request.GET.get('assigned_to', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if assigned_to_filter:
        try:
            tasks = tasks.filter(assigned_to_id=int(assigned_to_filter))
        except ValueError:
            pass
    if start_date:
        tasks = tasks.filter(due_date__gte=start_date)
    if end_date:
        tasks = tasks.filter(due_date__lte=end_date)

    if request.method == 'POST':
        # Upload a document for this component (process uploads first)
        if 'file' in request.FILES:
            form = DocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.component = component
                # tie to a related project ONLY if provided; allow no project
                target_project_id = request.POST.get('project_id')
                if target_project_id:
                    try:
                        doc.project = component.projects.get(id=target_project_id)
                    except Project.DoesNotExist:
                        doc.project = None
                doc.save()
                messages.success(request, "Document uploaded.")
                return redirect('component_detail', component_id=component.id)

        # Link to a project
        if 'project_id' in request.POST:
            project_id = request.POST.get('project_id')
            if project_id:
                project = get_object_or_404(Project, id=project_id)
                component.projects.add(project)
                component.save()
                messages.success(request, f"Linked to project: {project.name}")
            return redirect('component_detail', component_id=component.id)

        # Add member to a linked project
        if 'add_member_user_id' in request.POST:
            user_id = request.POST.get('add_member_user_id')
            proj_id = request.POST.get('add_member_project_id')
            user = get_object_or_404(User, id=user_id)
            target_project = None
            if proj_id:
                target_project = component.projects.filter(id=proj_id).first()
            if not target_project:
                target_project = component.projects.first()
            if target_project:
                target_project.assigned_users.add(user)
                messages.success(request, f"Added {user.get_full_name() or user.username} to {target_project.name}.")
            else:
                messages.error(request, "No linked project found to add the member.")
            return redirect('component_detail', component_id=component.id)

    return render(request, 'tracker/component_detail.html', {
        'component': component,
        'active_projects': active_projects,
        'assigned_techs': assigned_techs,
        'project_members': project_members,
        'document_form': DocumentForm(),
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'assigned_to_filter': assigned_to_filter,
        'start_date': start_date,
        'end_date': end_date,
        'filter_techs': filter_techs,
        'available_users': available_users,
    })


@login_required
def assign_tasks_view(request, component_id: int | None = None):
    """Create a task and link it to selected components.

    If a component id is provided in the URL, we use it when none are
    explicitly selected in the form.
    """
    projects = Project.objects.all()
    components = Component.objects.all()
    technicians = User.objects.filter(groups__name='technician')
    pending = Task.objects.filter(completed=True, is_approved=False)

    selected_component = None
    if component_id:
        selected_component = get_object_or_404(Component, id=component_id)

    if request.method == 'POST':
        task = Task.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            project=Project.objects.get(id=request.POST.get('project')) if request.POST.get('project') else (selected_component.projects.first() if selected_component else None),
            assigned_to=User.objects.get(id=request.POST.get('technician')),
            due_date=request.POST.get('due_date')
        )

        component_ids = request.POST.getlist('component')
        if component_ids:
            selected_components = Component.objects.filter(id__in=component_ids)
        elif selected_component:
            selected_components = [selected_component]
        else:
            selected_components = []

        task.components.set(selected_components)
        return redirect('assign_tasks')

    return render(request, 'tracker/assigntasks.html', {
        'projects': projects,
        'components': components,
        'technicians': technicians,
        'pending_tasks': pending,
        'selected_component': selected_component
    })


