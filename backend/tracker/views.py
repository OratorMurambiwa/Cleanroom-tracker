from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import logout
# Optional: pandas is only used for Excel features; import lazily inside the functions that need it
try:
    import pandas as pd  # noqa: F401
except Exception:
    pd = None
"""
Avoid importing heavy/optional libs like PyMuPDF (fitz) at module import time to
ensure management commands (e.g., migrate) work even if those optional binaries
are not installed on the host. We'll import them lazily within functions.
"""
import re
import os
import uuid
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import now
from .models import Task, Project, Component, Reminder, InventoryUpload, LookupHistory, Message, MessageThread, StoredTravelerFile, TravelerDocument
os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
from .forms import (
ProjectForm, ComponentForm, ReminderForm, MessageForm, CustomUserCreationForm,
DocumentForm, TeamMemberForm, TaskForm, TechnicianTaskSubmissionForm, TravelerDocUploadForm
)

# ----------------------- Utility Helpers -----------------------

def update_project_progress(project):
    tasks = Task.objects.filter(project=project)
    if tasks.exists():
        total = tasks.count()
        completed = tasks.filter(completed=True).count()
        project.progress = (completed / total) * 100
        project.save()

def update_component_progress(component):
    tasks = Task.objects.filter(components=component)
    if tasks.exists():
        total = tasks.count()
        approved = tasks.filter(is_approved=True).count()
        component.progress = (approved / total) * 100
        component.save()

def is_lead(user):
    return user.groups.filter(name='lead').exists()

# ----------------------- Authentication & Routing -----------------------

@login_required
def role_based_redirect(request):
    user = request.user
    if user.groups.filter(name='lead').exists():
        return redirect('lead_dashboard')
    elif user.groups.filter(name='technician').exists():
        return redirect('tech_dashboard')
    return render(request, 'tracker/genericdashboard.html')

def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')
        next_url = request.GET.get('next')  # for redirect after login if applicable

        print("USERNAME:", username)
        print("PASSWORD:", password)
        print("ROLE:", role)

        user = authenticate(request, username=username, password=password)
        print("AUTHENTICATED USER:", user)

        if user is not None:
            login(request, user)

            # Optional: Assign role-based group ONLY if user isn't in the group already
            if role == 'projectlead':
                lead_group = Group.objects.get(name='lead')
                if not user.groups.filter(name='lead').exists():
                    user.groups.add(lead_group)
                return redirect(next_url or 'lead_dashboard')

            elif role == 'technician':
                tech_group = Group.objects.get(name='technician')
                if not user.groups.filter(name='technician').exists():
                    user.groups.add(tech_group)
                return redirect(next_url or 'tech_dashboard')

            else:
                print("Unknown role provided.")
                return render(request, 'tracker/index.html', {'error': 'Unknown role selected'})

        else:
            print("Login failed: Invalid credentials")
            return render(request, 'tracker/index.html', {'error': 'Invalid credentials'})

    return render(request, 'tracker/index.html')
# ----------------------- Dashboards -----------------------

@login_required
def lead_dashboard(request):
    projects = Project.objects.all()
    components = Component.objects.all()
    pending_tasks = Task.objects.filter(completed=True, is_approved=False)

    return render(request, 'tracker/leaddashboard.html', {
        'projects': projects,
        'components': components,
        'pending_tasks': pending_tasks,
    })

@login_required
def tech_dashboard(request):
    projects = Project.objects.filter(assigned_users=request.user)
    components = Component.objects.all()
    
    # Get reminders from calendar for this user
    reminders = Reminder.objects.filter(user=request.user).order_by('reminder_time')
    
    # Get upcoming tasks in the next 14 days
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    upcoming_tasks = Task.objects.filter(
        assigned_to=request.user,
        due_date__isnull=False,
        due_date__gte=now.date(),
        due_date__lte=now.date() + timedelta(days=14),
        completed=False
    ).order_by('due_date')
    
    # Get recent messages from projects the user has access to
    recent_messages = Message.objects.filter(
        thread__project__in=projects
    ).select_related('sender', 'thread__project').order_by('-timestamp')[:3]
    
    # Add reminder form
    from .forms import ReminderForm
    form = ReminderForm()
    
    # Handle reminder creation
    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder_id = request.POST.get('reminder_id')
            if reminder_id:
                # Update existing reminder
                try:
                    reminder = Reminder.objects.get(id=reminder_id, user=request.user)
                    reminder.title = form.cleaned_data['title']
                    reminder.reminder_time = form.cleaned_data['reminder_time']
                    reminder.note = form.cleaned_data['note']
                    reminder.save()
                except Reminder.DoesNotExist:
                    pass  # Silently ignore if reminder doesn't exist or doesn't belong to user
            else:
                # Create new reminder
                reminder = form.save(commit=False)
                reminder.user = request.user
                reminder.save()
            return redirect('tech_dashboard')

    return render(request, 'tracker/tech_dashboard.html', {
        'projects': projects,
        'components': components,
        'reminders': reminders,
        'upcoming_tasks': upcoming_tasks,
        'recent_messages': recent_messages,
        'form': form,
    })

@login_required
def tech_project_list(request):
    projects = Project.objects.all() 
    return render(request, 'tracker/tech_project_list.html', {'projects': projects})


@login_required
def component_detail_view(request, component_id):
    """Show a single component page.

    I load the component, recalc its progress, list tasks, projects, and
    members (people on the linked projects). You can also link the component
    to a new project and upload docs for this component.
    """
    component = get_object_or_404(Component, id=component_id)

    # Keep component progress up-to-date
    update_component_progress(component)

    active_projects = Project.objects.filter(status='ongoing')

    # Technicians who have tasks on this component
    assigned_techs = User.objects.filter(
        id__in=component.tasks.values_list('assigned_to__id', flat=True)
    ).distinct()

    # Members from all linked projects (union)
    project_members = User.objects.filter(
        id__in=component.projects.values_list('assigned_users__id', flat=True)
    ).distinct()

    # Handle actions
    if request.method == 'POST':
        # Link to a project
        if 'project_id' in request.POST:
            project_id = request.POST.get('project_id')
            if project_id:
                project = get_object_or_404(Project, id=project_id)
                component.projects.add(project)
                component.save()
                messages.success(request, f"Linked to project: {project.name}")
                return redirect('component_detail', component_id=component.id)

        # Upload a document for this component
        if 'file' in request.FILES:
            form = DocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.component = component
                doc.save()
                messages.success(request, "Document uploaded.")
                return redirect('component_detail', component_id=component.id)

    return render(request, 'tracker/component_detail.html', {
        'component': component,
        'active_projects': active_projects,
        'assigned_techs': assigned_techs,
        'project_members': project_members,
        'document_form': DocumentForm(),
    })

# ----------------------- Project Views -----------------------

@login_required
def project_list_view(request):
    projects = Project.objects.all()
    return render(request, 'tracker/project_list.html', {'projects': projects})



@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    components = project.components.all()

    user = request.user
    is_technician = user.groups.filter(name__iexact='technician').exists()
    is_lead = user.is_staff or user.groups.filter(name__in=['lead', 'project_lead']).exists()

    tasks_qs = project.tasks.select_related('assigned_to')

    if is_technician and not (user.is_superuser or is_lead):
        tasks = tasks_qs.filter(assigned_to=user)
    else:
        tasks = tasks_qs

    # --------- FILTER INPUTS ----------
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').lower()
    assigned_to_filter = request.GET.get('assigned_to', '').strip()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sort_by = request.GET.get('sort', '').lower()

    # --------- APPLY FILTERS ----------
    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

    if status_filter == 'completed':
        tasks = tasks.filter(completed=True, is_approved=False)
    elif status_filter == 'approved':
        tasks = tasks.filter(is_approved=True)
    elif status_filter == 'todo':
        tasks = tasks.filter(completed=False, is_approved=False)

    if assigned_to_filter:
        tasks = tasks.filter(assigned_to__username__icontains=assigned_to_filter)

    if start_date:
        tasks = tasks.filter(due_date__gte=start_date)
    if end_date:
        tasks = tasks.filter(due_date__lte=end_date)

    if sort_by == 'due':
        tasks = tasks.order_by('due_date')
    elif sort_by == 'priority':
        tasks = tasks.order_by('-priority')

    total_tasks = tasks.count()
    completed_tasks = tasks.filter(completed=True, is_approved=False).count()
    approved_tasks = tasks.filter(is_approved=True).count()

    context = {
        'project': project,
        'components': components,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'assigned_to_filter': assigned_to_filter,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'approved_tasks': approved_tasks,
        'is_technician': is_technician,
        'is_lead': is_lead,
    }
    return render(request, 'tracker/project_detail.html', context)


@login_required
def create_project_view(request):
    """Simple create form for a project (name + description)."""
    form = ProjectForm(request.POST or None)
    technicians = User.objects.filter(groups__name='technician').exclude(is_superuser=True).exclude(username__iexact='admin')
    if request.method == 'POST' and form.is_valid():
        project = form.save()

        # Link selected component (optional)
        link_component_id = request.POST.get('link_component_id')
        linked_component = None
        if link_component_id:
            linked_component = Component.objects.filter(id=link_component_id).first()
            if linked_component:
                linked_component.projects.add(project)

        # Assign members (optional)
        assign_ids = request.POST.getlist('assign_user_ids')
        if assign_ids:
            users_to_add = User.objects.filter(id__in=assign_ids).exclude(is_superuser=True).exclude(username__iexact='admin')
            for u in users_to_add:
                project.assigned_users.add(u)

        # Optional document upload
        if 'file' in request.FILES:
            doc_form = DocumentForm(request.POST, request.FILES)
            if doc_form.is_valid():
                doc = doc_form.save(commit=False)
                doc.project = project
                if linked_component:
                    doc.component = linked_component
                doc.save()

        messages.success(request, "Project created successfully.")
        return redirect('lead_dashboard')
    return render(request, 'tracker/create_project.html', {
        'form': form,
        'components': Component.objects.all(),
        'technicians': technicians,
        'document_form': DocumentForm(),
    })

# ----------------------- Component Views -----------------------

@login_required
def create_component_view(request):
    """Create a new component (name/description/progress)."""
    form = ComponentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lead_dashboard')
    return render(request, 'tracker/create_component.html', {'form': form})
    
@login_required
def add_component(request, project_id):
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
def edit_component(request, component_id):
    """Edit a component and attach any selected tasks (M2M linkage)."""
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
def components_view(request):
    """List all components with simple filters in the template."""
    components = Component.objects.all()
    projects = Project.objects.all()
    return render(request, 'tracker/components.html', {
        'components': components,
        'projects': projects,
    })

@login_required
def component_list_view(request):
    components = Component.objects.prefetch_related('projects').order_by('-updated_at')
    return render(request, 'tracker/component_list.html', {'components': components})

    
# ----------------------- Task Views -----------------------


@login_required
def assign_tasks_view(request, component_id=None):
    """Create a task and attach it to 0..n components.

    If a specific component is passed in the URL, we default to that
    when no explicit component is selected in the form.
    """
    projects = Project.objects.all()
    components = Component.objects.all()
    technicians = User.objects.filter(groups__name='technician')
    tasks = Task.objects.filter(completed=True, is_approved=False)

    selected_component = None
    if component_id:
        selected_component = get_object_or_404(Component, id=component_id)

    if request.method == 'POST':
        # Create the task without components
        task = Task.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            project=Project.objects.get(id=request.POST.get('project')) if request.POST.get('project') else (selected_component.projects.first() if selected_component else None),
            assigned_to=User.objects.get(id=request.POST.get('technician')),
            due_date=request.POST.get('due_date')
        )

        # Handle the components (many-to-many field)
        component_ids = request.POST.getlist('component')
        if component_ids:
            selected_components = Component.objects.filter(id__in=component_ids)
        elif selected_component:
            selected_components = [selected_component]
        else:
            selected_components = []

        task.components.set(selected_components)

        return redirect('assign_tasks')  # You could redirect elsewhere if needed

    return render(request, 'tracker/assigntasks.html', {
        'projects': projects,
        'components': components,
        'technicians': technicians,
        'pending_tasks': tasks,
        'selected_component': selected_component
    })


    


@login_required
def create_task_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    technicians = User.objects.filter(groups__name='technician')

    if request.method == 'POST':
        Task.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            project=project,
            assigned_to=User.objects.get(id=request.POST.get('technician')),
            due_date=request.POST.get('due_date')
        )
        return redirect('project_detail', project_id=project.id)

    return render(request, 'tracker/create_task.html', {
        'project': project,
        'technicians': technicians
    })


@login_required
def submit_task(request, task_id):
    """Technician submits a task with optional media for approval."""
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        task.notes = request.POST.get('completion_notes', '')  # ✅ from form
        task.description = request.POST.get('description', task.description)

        # Handle uploaded files
        if 'image_upload' in request.FILES:
            task.image = request.FILES['image_upload']
        if 'video_upload' in request.FILES:
            task.video = request.FILES['video_upload']
        if 'audio_upload' in request.FILES:
            task.audio = request.FILES['audio_upload']
        if 'doc_upload' in request.FILES:
            task.document = request.FILES['doc_upload']

        task.completed = True
        task.status = "Pending Approval"
        task.save()

        messages.success(request, "Task submitted for approval.")
        return redirect('tech_tasks')

    return render(request, 'tasks/task_detail.html', {'task': task})

@login_required
def project_task_detail_view(request, task_id):
    """Task detail view for tasks that belong to a project."""
    task = get_object_or_404(Task, id=task_id, project__isnull=False)

    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_dashboard')

    return render(request, 'tracker/project_task_detail.html', {'task': task})




@login_required
def approve_task(request, task_id):
    """Lead approves a task and updates project/component progress."""
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        task.is_approved = True
        task.status = "Approved"
        task.save()

        # Update project progress
        if task.project:
            update_project_progress(task.project)

        # Update progress for all linked components
        for component in task.components.all():
            update_component_progress(component)
            component.updated_at = timezone.now()
            component.save()

        messages.success(request, f"Task '{task.title}' approved.")

    # Redirect somewhere sensible after approval
    if task.project:
        return redirect('project_detail', project_id=task.project.id)
    first_component = task.components.first()
    if first_component:
        return redirect('component_detail', component_id=first_component.id)
    return redirect('all_tasks')  # fallback: no project, no components





@login_required
def tech_tasks_view(request):
    """Show all tasks assigned to the current technician with filtering."""
    from django.db.models import Q
    
    # Start with tasks assigned to the current user
    tasks = Task.objects.filter(assigned_to=request.user).select_related('assigned_to')
    
    # Check if clear filter is requested
    if request.GET.get('clear'):
        return redirect('tech_tasks')
    
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    deadline_filter = request.GET.get('deadline', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query)
        )
    
    if status_filter == 'completed':
        tasks = tasks.filter(completed=True, is_approved=False)
    elif status_filter == 'approved':
        tasks = tasks.filter(is_approved=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(completed=False, is_approved=False)
    
    if deadline_filter:
        if deadline_filter == 'overdue':
            from django.utils import timezone
            today = timezone.now().date()
            tasks = tasks.filter(due_date__lt=today, completed=False)
        elif deadline_filter == 'today':
            from django.utils import timezone
            today = timezone.now().date()
            tasks = tasks.filter(due_date=today)
        elif deadline_filter == 'week':
            from django.utils import timezone
            from datetime import timedelta
            today = timezone.now().date()
            week_from_now = today + timedelta(days=7)
            tasks = tasks.filter(due_date__gte=today, due_date__lte=week_from_now)
    
    # Handle date range filter
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            tasks = tasks.filter(due_date__gte=start_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore the filter
    
    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            tasks = tasks.filter(due_date__lte=end_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore the filter
    
    # Default ordering by due date
    tasks = tasks.order_by('due_date')
    
    # Get today's date for deadline highlighting
    from django.utils import timezone
    today = timezone.now().date()
    
    return render(request, 'tracker/tech_tasks.html', {
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'deadline_filter': deadline_filter,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        'projects': Project.objects.filter(assigned_users=request.user),
    })


@login_required
def task_detail_view(request, task_id):
    """Generic task detail (guards techs from viewing others' tasks)."""
    task = get_object_or_404(Task, id=task_id)

    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_tasks')

    return render(request, 'tracker/task_detail.html', {'task': task})

@user_passes_test(is_lead)
def edit_task_view(request, task_id):
    """Lead/staff can edit a task (title/desc/due/assignee)."""
    task = get_object_or_404(Task, id=task_id)
    technicians = User.objects.filter(groups__name='technician')

    if request.method == 'POST':
        task.title = request.POST.get('title')
        task.description = request.POST.get('description')
        task.notes = request.POST.get('notes')

        # Parse deadline (due_date)
        due_date_str = request.POST.get('due_date')
        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
        else:
            task.due_date = None

        # Assigned technician
        tech_id = request.POST.get('assigned_to')
        if tech_id:
            task.assigned_to = User.objects.get(id=tech_id)

        task.save()
        messages.success(request, "Task updated successfully.")
        return redirect('review_task_for_approval', task_id=task.id)

    return render(request, 'tracker/edit_task.html', {
        'task': task,
        'technicians': technicians,
        'components': Component.objects.all()
    })


@login_required
def review_task_for_approval(request, task_id):
    """Lightweight review screen to approve/reject a task."""
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            task.is_approved = True
            task.status = 'Approved'
            task.save()
        elif action == 'reject':
            task.is_completed = False
            task.status = 'todo'
            task.save()
        elif action == 'revoke':
            note = request.POST.get('rejection_note', '').strip()
            if note:
                existing = task.notes or ''
                prefix = '\n\n' if existing else ''
                task.notes = f"{existing}{prefix}Lead feedback: {note}"
            task.is_approved = False
            task.completed = False
            task.status = 'todo'
            task.save()
        if task.project:
            return redirect('project_detail', project_id=task.project.id)
        first_component = task.components.first()
        if first_component:
            return redirect('component_detail', component_id=first_component.id)
        return redirect('all_tasks')

    return render(request, 'tracker/review_task_for_approval.html', {
        'task': task,
        'projects': Project.objects.all(),
    })

@login_required
def component_task_detail_view(request, task_id):
    """Task detail for tasks that are attached to at least one component."""
    task = get_object_or_404(Task, id=task_id, components__isnull=False)

    # Optional: restrict so only the assigned technician sees it
    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_dashboard')

    return render(request, 'tracker/component_task_detail.html', {'task': task})

@login_required
def component_task_completed_view(request, task_id):
    """Technician submission flow for component tasks (uploads + notes)."""
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        task.notes = request.POST.get('notes', '')
        if 'image' in request.FILES:
            task.image = request.FILES['image']
        if 'video' in request.FILES:
            task.video = request.FILES['video']
        if 'audio' in request.FILES:
            task.audio = request.FILES['audio']
        if 'document' in request.FILES:
            task.document = request.FILES['document']
        task.completed = True
        task.status = "Pending Approval"
        task.save()
        messages.success(request, "Task submitted for approval.")
        return redirect('tech_tasks')

    return render(request, 'tracker/component_task_completed.html', {'task': task})


# ----------------------- Team & Docs -----------------------

@login_required
def assign_user_view(request, project_id):
    """Add selected users to a project's team."""
    project = get_object_or_404(Project, id=project_id)
    users = User.objects.exclude(id__in=project.assigned_users.all())
    
    if request.method == 'POST':
        selected_ids = request.POST.getlist('users')
        for uid in selected_ids:
            user = User.objects.get(id=uid)
            project.assigned_users.add(user)
        return redirect('project_detail', project_id=project.id)
    
    return render(request, 'tracker/assign_user.html', {'project': project, 'users': users})

@login_required
def upload_document_view(request, project_id):
    """Upload a document and associate it with a project."""
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.project = project
            doc.save()
            return redirect('project_detail', project_id=project.id)
    else:
        form = DocumentForm()
    return render(request, 'tracker/upload_document.html', {'form': form, 'project': project})

@login_required
def add_tasks_view(request, project_id):
    """Upload a traveler or manually add tasks to a project."""
    project = get_object_or_404(Project, id=project_id)
    users = User.objects.all()
    components = Component.objects.all()
    extracted_tasks = []
    
    if request.method == 'POST':
        if 'pdf_file' in request.FILES:
            uploaded_file = request.FILES['pdf_file']
            file_path = os.path.join(settings.BASE_DIR, 'temp_uploaded.pdf')
    
            with open(file_path, 'wb+') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
    
            extracted_tasks = extract_tasks_from_pdf(file_path)
    
            return render(request, 'add_tasks.html', {
                'form': TaskForm(),
                'project': project,
                'users': users,
                'components': components,
                'extracted_tasks': extracted_tasks
            })
    
        else:
            # Regular manual task form submission
            form = TaskForm(request.POST)
            if form.is_valid():
                task = form.save(commit=False)
                task.project = project
                task.save()
                return redirect('project_detail', project_id=project.id)
    else:
        form = TaskForm()
    
    return render(request, 'add_tasks.html', {
        'form': form,
        'project': project,
        'users': users,
        'components': components,
        'extracted_tasks': extracted_tasks
    })

# delete tasks
def delete_task_view(request, task_id):
    """Delete a task (POST only), then go back to its project page."""
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        project_id = task.project.id  # store for redirect
        task.delete()
        messages.success(request, 'Task deleted successfully.')
        return redirect('project_detail', project_id=project_id)

    return redirect('task_detail', task_id=task_id)
    

@login_required
def add_team_member(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = TeamMemberForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            project.assigned_users.add(user)
            messages.success(request, 'Team member added successfully!')
            return redirect('project_detail', project_id=project.id)
    else:
        form = TeamMemberForm()
    return render(request, 'tracker/add_team_member.html', {'form': form, 'project': project})
    
# ----------------------- Calendar & Tech Dashboard -----------------------

@login_required
def calendar_view(request):
    """Simple calendar feed for due-dated tasks + personal reminders."""
    user = request.user
    today = timezone.now().date()
    day_plus_2 = today + timedelta(days=2)
    day_plus_5 = today + timedelta(days=5)

    is_technician = user.groups.filter(name__iexact='technician').exists()
    is_lead = user.is_staff or user.groups.filter(name__in=['lead', 'project_lead']).exists()

    if is_technician and not user.is_superuser and not is_lead:
        tasks = Task.objects.filter(assigned_to=user, due_date__isnull=False)
    else:
        tasks = Task.objects.filter(due_date__isnull=False)

    # Keep it simple since the template does not touch task.project
    tasks = tasks.only('id', 'title', 'due_date')

    reminders = Reminder.objects.filter(user=user)

    return render(request, 'tracker/calendar.html', {
        'tasks': tasks,
        'reminders': reminders,
        'today': today,
        'day_plus_2': day_plus_2,
        'day_plus_5': day_plus_5,
        'is_technician': is_technician,
        'is_lead': is_lead,
    })

@login_required
def task_detail_api(request, task_id):
    """Read-only JSON for a task (guards techs to own tasks only)."""
    try:
        task = Task.objects.select_related('project', 'assigned_to').get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task not found")

    user = request.user
    is_technician = user.groups.filter(name__iexact='technician').exists()
    is_lead = user.is_staff or user.groups.filter(name__in=['lead', 'project_lead']).exists()

    # Techs can only see their own tasks in detail; leads/staff/superusers can see all
    if is_technician and not (task.assigned_to_id == user.id or user.is_superuser):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = {
        'id': task.id,
        'title': task.title,
        'description': getattr(task, 'description', '') or '',
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'project': getattr(task.project, 'name', None),
        'assignee': (task.assigned_to.get_full_name() or task.assigned_to.username) if task.assigned_to else None,
        'status': getattr(task, 'status', '') or '',
        'priority': getattr(task, 'priority', '') or '',
        'detail_url': reverse('task_detail', args=[task.id]),
    }
    return JsonResponse(data)



@login_required
def create_reminder(request):
    if request.method == 'POST':
        Reminder.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            reminder_time=request.POST.get('reminder_time'),
            note=request.POST.get('note')
        )
    return redirect('calendar')

@login_required
def delete_reminder(request, reminder_id):
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    reminder.delete()
    return redirect('calendar')

@login_required
def technician_dashboard(request):
    """Tech home: reminders + upcoming tasks (next 3 days)."""
    reminders = Reminder.objects.filter(user=request.user).order_by('due_date')
    form = ReminderForm()

    # Add upcoming tasks (due in the next 3 days)
    upcoming_tasks = Task.objects.filter(
        assigned_to=request.user,
        due_date__isnull=False,
        due_date__gte=now(),
        due_date__lte=now() + timedelta(days=3),
        completed=False
    ).order_by('due_date')

    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            reminder.save()
            return redirect('technician_dashboard')

    return render(request, 'dashboard/technician_dashboard.html', {
        'reminders': reminders,
        'upcoming_tasks': upcoming_tasks,
        'form': form,
    })

@login_required
def tech_project_detail_view(request, project_id):
    """Tech-specific project view with filtering and sorting."""
    from django.db.models import Q
    
    project = get_object_or_404(Project, id=project_id)
    # Show all tasks for the project, not just assigned to the user
    tasks = Task.objects.filter(project=project).select_related('assigned_to')
    
    # Check if clear filter is requested
    if request.GET.get('clear'):
        return redirect('tech_project_detail', project_id=project_id)
    
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    deadline_filter = request.GET.get('deadline', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(assigned_to__username__icontains=search_query)
        )
    
    if status_filter == 'completed':
        tasks = tasks.filter(completed=True, is_approved=False)
    elif status_filter == 'approved':
        tasks = tasks.filter(is_approved=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(completed=False, is_approved=False)
    
    if deadline_filter:
        if deadline_filter == 'overdue':
            from django.utils import timezone
            today = timezone.now().date()
            tasks = tasks.filter(due_date__lt=today, completed=False)
        elif deadline_filter == 'today':
            from django.utils import timezone
            today = timezone.now().date()
            tasks = tasks.filter(due_date=today)
        elif deadline_filter == 'week':
            from django.utils import timezone
            from datetime import timedelta
            today = timezone.now().date()
            week_from_now = today + timedelta(days=7)
            tasks = tasks.filter(due_date__gte=today, due_date__lte=week_from_now)
    
    # Handle date range filter
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            tasks = tasks.filter(due_date__gte=start_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore the filter
    
    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            tasks = tasks.filter(due_date__lte=end_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore the filter
    
    # Default ordering by due date
    tasks = tasks.order_by('due_date')
    
    # Get all documents related to this project
    project_documents = project.documents.all().order_by('-uploaded_at')
    traveler_documents = TravelerDocument.objects.filter(related_project=project).order_by('-uploaded_at')
    stored_files = StoredTravelerFile.objects.filter(project=project).order_by('-uploaded_at')
    
    # Get today's date for deadline highlighting
    from django.utils import timezone
    today = timezone.now().date()
    
    return render(request, 'tracker/tech_project_detail.html', {
        'project': project,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'deadline_filter': deadline_filter,
        'start_date': start_date,
        'end_date': end_date,
        'project_documents': project_documents,
        'traveler_documents': traveler_documents,
        'stored_files': stored_files,
        'today': today,
    })
    
@login_required
def tech_component_detail_view(request, component_id):
    """Tech-specific component view showing only my tasks."""
    component = get_object_or_404(Component, id=component_id)
    tasks = component.tasks.filter(assigned_to=request.user)

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', '')

    if search_query:
        tasks = tasks.filter(title__icontains=search_query)

    if status_filter == 'completed':
        tasks = tasks.filter(completed=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(completed=False)

    if sort_by == 'due':
        tasks = tasks.order_by('due_date')
    elif sort_by == 'priority':
        tasks = tasks.order_by('-priority')

    return render(request, 'tracker/tech_component_detail.html', {
        'component': component,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
    })

    
@login_required
def save_extracted_tasks(request):
    """Persist the previewed extracted tasks into real Task rows.

    I loop over dynamic form keys tasks[i][...] and make Task rows. If a
    component id is present, I link it through the M2M.
    """
    if request.method == 'POST':
        tasks_data = request.POST
    
        i = 0
        while f'tasks[{i}][title]' in tasks_data:
            title = tasks_data.get(f'tasks[{i}][title]')
            section = tasks_data.get(f'tasks[{i}][section]')
            user_id = tasks_data.get(f'tasks[{i}][user]')
            project_id = tasks_data.get(f'tasks[{i}][project]')
            component_id = tasks_data.get(f'tasks[{i}][component]')
            due_date = tasks_data.get(f'tasks[{i}][due_date]')
    
            task = Task.objects.create(
                title=title,
                section=section,
                assigned_to_id=user_id,
                project_id=project_id,
                due_date=due_date
            )
            if component_id:
                try:
                    task.components.add(int(component_id))
                except Exception:
                    pass
            i += 1
    
        messages.success(request, "All extracted tasks have been saved!")
        return redirect('project_detail', project_id=project_id)
    
    return redirect('add_tasks')



def extract_text_from_pdf(file_path):
    """Minimal PDF text extractor using PyMuPDF (fitz)."""
    import fitz  # Local import to avoid module import-time failures
    doc = fitz.open(file_path)
    return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file_path):
    """DOCX text extractor (kept for future use)."""
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())




#view for excel file extraction

# Asset Lookup View
@login_required
def asset_lookup_view(request):
    """Excel lookup tool for component/asset metadata (latest or uploaded file)."""
    asset_data = None
    search_query = ""
    error_message = ""

    if request.method == 'POST':
        uploaded_file = request.FILES.get('excel_file')
        search_query = request.POST.get('asset_name', '').strip()

        if uploaded_file and uploaded_file.name.endswith('.xlsx'):
            try:
                df = pd.read_excel(uploaded_file)
                df.columns = df.columns.str.strip()  # Clean column names

                if 'Asset Type' not in df.columns:
                    error_message = "Excel file must contain a column named 'Asset Type'."
                else:
                    if search_query:
                        filtered_df = df[df['Asset Type'].astype(str).str.lower().str.contains(search_query.lower())]
                    else:
                        filtered_df = df

                    asset_data = filtered_df.to_dict(orient='records')
            except Exception as e:
                error_message = f"Error reading Excel file: {str(e)}"
        else:
            error_message = "Please upload a valid .xlsx file."

    return render(request, 'tracker/asset_lookup.html', {
        'asset_data': asset_data,
        'search_query': search_query,
        'error_message': error_message,
    })


#tech component view
@login_required
def tech_components_view(request):
    """Tech page: components plus quick asset inventory search (Excel)."""
    components = Component.objects.all()
    asset_data = None
    search_query = ""
    search_field = "Asset Type"
    error_message = ""
    file_uploaded = False
    last_file_url = None
    last_file_name = None
    recent_lookups = []

    if request.method == 'POST':
        uploaded_file = request.FILES.get('excel_file')
        search_query = request.POST.get('asset_name', '').strip()
        search_field = request.POST.get('search_field', 'Asset Type').strip()

        if uploaded_file and uploaded_file.name.endswith('.xlsx'):
            inventory_file = InventoryUpload.objects.create(file=uploaded_file)
            file_path = inventory_file.file.path
            file_uploaded = True
            last_file_url = inventory_file.file.url
            last_file_name = uploaded_file.name
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"New file uploaded: {file_path}, exists: {os.path.exists(file_path) if file_path else False}")
        else:
            try:
                latest_file = InventoryUpload.objects.latest('uploaded_at')
                file_path = latest_file.file.path
                file_uploaded = True
                last_file_url = latest_file.file.url
                last_file_name = os.path.basename(latest_file.file.name)
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Using latest file: {file_path}, exists: {os.path.exists(file_path) if file_path else False}")
            except InventoryUpload.DoesNotExist:
                error_message = "No Excel file found. Please upload one."
                file_path = None

        if file_path and os.path.exists(file_path):
            try:
                # Additional debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Attempting to read Excel file: {file_path}")
                logger.info(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'}")
                
                                # Check if pandas is available
                if pd is None:
                    error_message = "Pandas library not available. Please contact administrator."
                    logger.error("Pandas library not available")
                else:
                    df = pd.read_excel(file_path)
                    logger.info(f"Successfully read Excel file with {len(df)} rows and columns: {list(df.columns)}")
                    
                    # Check if file has data
                    if len(df) == 0:
                        error_message = "Excel file is empty. Please upload a file with data."
                        logger.warning("Excel file is empty")
                    elif len(df.columns) == 0:
                        error_message = "Excel file has no columns. Please check the file format."
                        logger.warning("Excel file has no columns")
                    else:
                        df.columns = df.columns.str.strip()

                if pd is not None and 'df' in locals():
                    if search_query:
                        if search_field not in df.columns:
                            available_columns = ', '.join(df.columns.tolist())
                            error_message = f"Search field '{search_field}' not found in Excel file. Available columns: {available_columns}"
                            logger.warning(f"Search field '{search_field}' not found. Available columns: {available_columns}")
                        else:
                            col_data = df[search_field].astype(str).str.strip()
                            if search_field == "Assembly number (Description)":
                                # Exact match (case-insensitive)
                                filtered_df = df[col_data.str.lower() == search_query.lower()]
                            else:
                                # Partial match
                                filtered_df = df[col_data.str.lower().str.contains(search_query.lower())]
                            
                            asset_data = filtered_df.to_dict(orient='records')
                            
                            if search_query:
                                LookupHistory.objects.create(user=request.user, query=search_query)
                            recent_lookups = LookupHistory.objects.filter(user=request.user).order_by('-timestamp')[:5]
                else:
                    # No search query, show all data
                    filtered_df = df
                    asset_data = filtered_df.to_dict(orient='records')

            except Exception as e:
                error_message = f"Error reading file: {e}"
                # Log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Excel file read error: {e}, file_path: {file_path}")
                
                # Provide more helpful error messages for common issues
                if "not a zip file" in str(e).lower():
                    error_message = "Invalid Excel file format. Please ensure you're uploading a valid .xlsx file."
                elif "password protected" in str(e).lower():
                    error_message = "Excel file appears to be password protected. Please upload an unprotected file."
                elif "corrupt" in str(e).lower():
                    error_message = "Excel file appears to be corrupted. Please try uploading the file again."
                elif "permission" in str(e).lower():
                    error_message = "Permission denied reading file. Please check file permissions."
        elif file_path:
            error_message = f"File not found at path: {file_path}"
        else:
            error_message = "No Excel file available for search. Please upload a file first."

    # Get projects for sidebar navigation
    projects = Project.objects.all()[:5]  # Limit to 5 projects for sidebar
    
    return render(request, 'tracker/tech_components.html', {
        'components': components,
        'asset_data': asset_data,
        'search_query': search_query,
        'search_field': search_field,
        'file_uploaded': file_uploaded,
        'last_file_url': last_file_url,
        'last_file_name': last_file_name,
        'recent_lookups': recent_lookups,
        'error_message': error_message,
        'projects': projects,
    })


@login_required
def component_tasks_api(request, component_id):
    """API endpoint to get tasks for a specific component assigned to the current user."""
    from django.http import JsonResponse
    from django.db.models import Q, Case, When, Value, BooleanField
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        component = Component.objects.get(id=component_id)
        logger.info(f"Found component: {component.name} (ID: {component_id})")
        
        # Get tasks linked to this component and assigned to the current user
        tasks = Task.objects.filter(
            components=component,
            assigned_to=request.user
        ).select_related('assigned_to').prefetch_related('components')
        
        logger.info(f"Initial tasks query: {tasks.count()} tasks found")
        logger.info(f"User: {request.user.username}, Component: {component.name}")
        
        # Apply search filter
        search_query = request.GET.get('search', '')
        if search_query:
            tasks = tasks.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(notes__icontains=search_query)
            )
            logger.info(f"After search filter: {tasks.count()} tasks")
        
        # Apply status filter
        status_filter = request.GET.get('status', 'all')
        if status_filter == 'pending':
            tasks = tasks.filter(completed=False, is_approved=False)
        elif status_filter == 'completed':
            tasks = tasks.filter(completed=True, is_approved=False)
        elif status_filter == 'approved':
            tasks = tasks.filter(is_approved=True)
        
        logger.info(f"After status filter: {tasks.count()} tasks")
        
        # Order by due date (overdue first, then by due date)
        from datetime import date
        today = date.today()
        tasks = tasks.annotate(
            is_overdue=Case(
                When(due_date__lt=today, completed=False, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        ).order_by('-is_overdue', 'due_date')
        
        # Convert to JSON-serializable format
        tasks_data = []
        for task in tasks:
            task_data = {
                'id': task.id,
                'title': task.title,
                'description': task.description or '',
                'notes': task.notes or '',
                'priority': task.priority or '',
                'assigned_to': task.assigned_to.username,
                'due_date': task.due_date.strftime('%b %d, %Y') if task.due_date else '',
                'completed': task.completed,
                'is_approved': task.is_approved,
                'created_at': task.created_at.strftime('%b %d, %Y'),
                'updated_at': task.updated_at.strftime('%b %d, %Y') if task.updated_at != task.created_at else '',
            }
            tasks_data.append(task_data)
        
        logger.info(f"Returning {len(tasks_data)} tasks")
        
        # Debug: Let's also check all tasks for this component regardless of assignment
        all_component_tasks = Task.objects.filter(components=component)
        logger.info(f"Total tasks for component {component.name}: {all_component_tasks.count()}")
        
        # Debug: Check if there are any tasks assigned to this user
        user_tasks = Task.objects.filter(assigned_to=request.user)
        logger.info(f"Total tasks assigned to user {request.user.username}: {user_tasks.count()}")
        
        # Debug: Check all tasks in the system
        total_tasks = Task.objects.all().count()
        logger.info(f"Total tasks in system: {total_tasks}")
        
        # Debug: Check component-task relationships
        component_task_count = component.tasks.count()
        logger.info(f"Component.tasks.count(): {component_task_count}")
        
        # Debug: Check user-component relationships
        user_component_tasks = Task.objects.filter(
            components=component,
            assigned_to=request.user
        )
        logger.info(f"User-component tasks: {user_component_tasks.count()}")
        
        # Debug: Show some sample task data
        sample_tasks = Task.objects.filter(components=component)[:3]
        sample_data = []
        for task in sample_tasks:
            sample_data.append({
                'id': task.id,
                'title': task.title,
                'assigned_to': task.assigned_to.username if task.assigned_to else 'None',
                'components_count': task.components.count()
            })
        
        return JsonResponse({
            'success': True,
            'tasks': tasks_data,
            'component_name': component.name,
            'debug_info': {
                'total_component_tasks': all_component_tasks.count(),
                'total_user_tasks': user_tasks.count(),
                'user_id': request.user.id,
                'component_id': component_id,
                'total_system_tasks': total_tasks,
                'component_tasks_count': component_task_count,
                'user_component_tasks': user_component_tasks.count(),
                'sample_tasks': sample_data
            }
        })
        
    except Component.DoesNotExist:
        logger.error(f"Component not found: {component_id}")
        return JsonResponse({
            'success': False,
            'error': 'Component not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in component_tasks_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# ----------------------- Upload Traveler View -----------------------

@login_required
def upload_tasks_from_traveler_view(request):
    """Upload a traveler PDF and auto-extract tasks by sections/pages."""
    if request.method == 'POST':
        form = TravelerDocUploadForm(request.POST, request.FILES)

        if form.is_valid():
            start_from = form.cleaned_data['start_section']
            end_at = form.cleaned_data['end_section']
            uploaded_file = request.FILES.get('file')
            project = form.cleaned_data['related_project']
            start_page = form.cleaned_data.get('start_page')
            end_page = form.cleaned_data.get('end_page')

            # Save inputs in session
            request.session['start_section'] = start_from
            request.session['end_section'] = end_at
            request.session['start_page'] = start_page
            request.session['end_page'] = end_page
            request.session['related_project_id'] = project.id if project else None

            stored_file_obj = None

            if uploaded_file:
                stored_file_obj = StoredTravelerFile.objects.create(
                    file=uploaded_file,
                    filename=uploaded_file.name,
                    project=project
                )
                request.session['stored_file_id'] = stored_file_obj.id
                request.session['document_name'] = uploaded_file.name
            else:
                file_id = request.session.get('stored_file_id')
                if file_id:
                    try:
                        stored_file_obj = StoredTravelerFile.objects.get(id=file_id)
                    except StoredTravelerFile.DoesNotExist:
                        return render(request, 'tracker/upload_from_doc.html', {
                            'form': form,
                            'error': 'Previous file not found. Please upload again.'
                        })
                else:
                    return render(request, 'tracker/upload_from_doc.html', {
                        'form': form,
                        'error': 'No file uploaded.'
                    })

            temp_filename = stored_file_obj.file.path
            headers = []
            ext = os.path.splitext(temp_filename)[1].lower()

            if ext == '.pdf':
                try:
                    import fitz  # Local import to avoid module import-time failures
                except Exception as e:
                    return render(request, 'tracker/upload_from_doc.html', {
                        'form': form,
                        'stored_file': stored_file_obj,
                        'error': (
                            'PDF extraction is unavailable on this system. '
                            'Your file was saved successfully. To enable extraction, '
                            'install a compatible PyMuPDF build (e.g. "pip install --upgrade pymupdf").'
                        )
                    })

                try:
                    doc = fitz.open(temp_filename)
                except Exception as e:
                    return render(request, 'tracker/upload_from_doc.html', {
                        'form': form,
                        'stored_file': stored_file_obj,
                        'error': 'Unable to open PDF for extraction. Your file is saved.'
                    })

                if start_page is not None and end_page is not None:
                    start_page = max(0, start_page - 1)
                    end_page = max(0, end_page - 1)
                    pages_to_read = doc[start_page:end_page + 1]
                    page_range_offset = start_page
                else:
                    pages_to_read = doc
                    page_range_offset = 0

                current_section = None
                current_step = None

                for page_index, page in enumerate(pages_to_read):
                    lines = page.get_text("text").splitlines()
                    actual_page_number = page_range_offset + page_index + 1

                    for line in lines:
                        line = line.strip()

                        match_section = re.match(r'^(\d+(?:\.\d+)*)\s+(.*)', line)
                        match_step = re.match(r'^(\d+)\.\s+(.*)', line)
                        match_sub = re.match(r'^([a-zA-Z])\.\s+(.*)', line)

                        if match_section:
                            sec_num, title = match_section.groups()
                            try:
                                if int(sec_num.split('.')[0]) in range(start_from, end_at + 1):
                                    current_section = sec_num
                                    current_step = None
                                    headers.append({
                                        'title': title.strip()[:80],
                                        'description': f"{sec_num} {title}",
                                        'section': sec_num,
                                        'page': actual_page_number
                                    })
                            except:
                                continue

                        elif match_step and current_section:
                            step_num, title = match_step.groups()
                            current_step = step_num
                            full_id = f"{current_section}.{step_num}"
                            headers.append({
                                'title': title.strip()[:80],
                                'description': f"{full_id} {title}",
                                'section': full_id,
                                'page': actual_page_number
                            })

                        elif match_sub and current_section and current_step:
                            sub_letter, text = match_sub.groups()
                            full_id = f"{current_section}.{current_step}.{sub_letter}"
                            headers.append({
                                'title': text.strip()[:80],
                                'description': f"{full_id} {text}",
                                'section': full_id,
                                'page': actual_page_number
                            })

                try:
                    doc.close()
                except Exception:
                    pass
            else:
                return render(request, 'tracker/upload_from_doc.html', {
                    'form': form,
                    'error': 'Only PDF files are supported for now.'
                })

            seen = set()
            cleaned_headers = []
            for task in headers:
                key = (task['title'], task['section'])
                if key not in seen:
                    seen.add(key)
                    cleaned_headers.append(task)

            request.session['extracted_tasks'] = cleaned_headers
            return redirect('preview_extracted_tasks')

    else:
        initial_data = {
            'start_section': request.session.get('start_section'),
            'end_section': request.session.get('end_section'),
            'start_page': request.session.get('start_page'),
            'end_page': request.session.get('end_page'),
            'related_project': request.session.get('related_project_id'),
        }
        form = TravelerDocUploadForm(initial=initial_data)

    stored_file = None
    if request.session.get('stored_file_id'):
        stored_file = StoredTravelerFile.objects.filter(id=request.session['stored_file_id']).first()

    return render(request, 'tracker/upload_from_doc.html', {
        'form': form,
        'stored_file': stored_file,
    })



@login_required
def preview_extracted_tasks(request):
    tasks = request.session.get('extracted_tasks', [])
    project_id = request.session.get('related_project_id')
    project = Project.objects.get(id=project_id) if project_id else None

    seen_titles = set()
    cleaned_tasks = []
    for task in tasks:
        title = task.get('title', '').strip().rstrip('.')
        description = task.get('description', '').strip()
        if not title or title in seen_titles or title.endswith('...'):
            continue
        seen_titles.add(title)
        task['title'] = title
        task['description'] = description
        cleaned_tasks.append(task)

    request.session['extracted_tasks'] = cleaned_tasks

    users = User.objects.filter(groups__name="technician")
    components = Component.objects.filter(status='ongoing')

    return render(request, 'tracker/preview_tasks.html', {
        'tasks': cleaned_tasks,
        'related_project_id': project.id if project else '',
        'users': users,
        'components': components,
    })


@login_required
def edit_preview_task(request, index):
    tasks = request.session.get('extracted_tasks', [])

    if index >= len(tasks):
        messages.error(request, "Invalid task index.")
        return redirect('preview_extracted_tasks')

    if request.method == 'POST':
        tasks[index]['title'] = request.POST.get('title', tasks[index]['title'])
        tasks[index]['description'] = request.POST.get('description', tasks[index]['description'])
        tasks[index]['section'] = request.POST.get('section', tasks[index].get('section'))

        request.session['extracted_tasks'] = tasks
        messages.success(request, "Task updated successfully.")
        return redirect('preview_extracted_tasks')

    task = tasks[index]

    users = User.objects.filter(groups__name="technician")
    components = Component.objects.filter(status='ongoing')
    projects = Project.objects.all()

    return render(request, 'tracker/edit_preview_task.html', {
        'task': task,
        'index': index,
        'users': users,
        'components': components,
        'projects': projects,
    })


@csrf_exempt
def assign_single_task(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        title = data.get('title')
        description = data.get('description')
        due_date = data.get('due_date')
        section = data.get('section')
        user_id = data.get('user')
        component_id = data.get('component')
        project_id = data.get('project')

        try:
            user = User.objects.get(id=user_id)
            project = Project.objects.get(id=project_id)
            component = Component.objects.get(id=component_id) if component_id else None

            task = Task.objects.create(
                title=title,
                description=description or "",
                due_date=due_date,
                assigned_to=user,
                project=project,
                section=section,
            )
            if component:
                task.components.add(component)

            return JsonResponse({'success': True, 'task_id': task.id})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


#-----------------------------Messages Views-----------------------------------------


@login_required
def project_messages_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    thread, created = MessageThread.objects.get_or_create(project=project)
    messages = thread.messages.order_by('timestamp')

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.thread = thread
            message.sender = request.user
            message.save()
            return redirect('project_messages', project_id=project.id)
    else:
        form = MessageForm()

    return render(request, 'tracker/project_messages.html', {
        'project': project,
        'messages': messages,
        'form': form,
        'all_projects': Project.objects.all(),  
    })

def landing_page(request):
    return render(request, 'tracker/landing_page.html')



def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            group = form.cleaned_data.get('group')
            group.user_set.add(user)  # Assign user to selected group
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('custom_login')  # redirect to your login page
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'tracker/register.html', {'form': form})


@login_required
def tech_project_list_view(request):
    projects = Project.objects.all()
    return render(request, 'tracker/tech_project_list.html', {'projects': projects})

def LogoutView(request):
    logout(request)
    return redirect('landing')

@login_required
def settings_view(request):
    return render(request, 'tracker/settings.html')


@login_required
def all_tasks_view(request):
    tasks = Task.objects.all()

    query = request.GET.get('q', '')
    status = request.GET.get('status')
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    if query:
        tasks = tasks.filter(
            Q(title__icontains=query) |
            Q(assigned_to__first_name__icontains=query) |
            Q(assigned_to__last_name__icontains=query) |
            Q(assigned_to__username__icontains=query)
        )

    if status:
        if status == 'approved':
            tasks = tasks.filter(is_approved=True)
        elif status == 'completed':
            tasks = tasks.filter(completed=True, is_approved=False)
        elif status == 'todo':
            tasks = tasks.filter(completed=False, is_approved=False)

    if start_date:
        tasks = tasks.filter(due_date__gte=start_date)

    if end_date:
        tasks = tasks.filter(due_date__lte=end_date)

    return render(request, 'tracker/alltasks.html', {
        'tasks': tasks,
        'projects': Project.objects.all(),
    })



@login_required
def view_pending_tasks(request):
    pending_tasks = Task.objects.filter(completed=True, is_approved=False)
    return render(request, 'tracker/view_pending_tasks.html', {
        'pending_tasks': pending_tasks
    })



@login_required
def create_project(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        section = request.POST.get('section', '').strip()
        contributor_ids = request.POST.getlist('contributors')

        if name:
            project = Project.objects.create(name=name, description=description)
            
            contributors = User.objects.filter(id__in=contributor_ids)
            project.assigned_users.set(contributors)

            messages.success(request, "✅ Project created successfully!")
            return redirect('lead_dashboard')
        else:
            messages.error(request, "❌ Project name is required.")
            return redirect('lead_dashboard')

    return redirect('lead_dashboard')

def alerts_view(request):
    alerts = [
        {
            "title": "Pending Task Approval",
            "message": "Your submitted task for Project X needs review.",
            "timestamp": timezone.now(),
            "link": reversed('tech_tasks'),
        },
        {
            "title": "Component Delivery Delay",
            "message": "Shipment for component ABC123 is delayed.",
            "timestamp": timezone.now() - timedelta(hours=4),
            "link": "",  # or a component detail page
        },
    ]
    return render(request, 'tracker/alerts.html', {'alerts': alerts, 'projects': Project.objects.all()})



@login_required
def settings_view(request):
   
    if request.method == 'POST':
        # Example: handle settings save logic
        dark_mode = request.POST.get('dark_mode') == 'on'
        notify_tasks = request.POST.get('notify_tasks') == 'on'
        notify_components = request.POST.get('notify_components') == 'on'

        # You can print or save this to the DB later
        print("Dark Mode:", dark_mode)
        print("Notify Tasks:", notify_tasks)
        print("Notify Components:", notify_components)


    return render(request, 'tracker/settings.html', {
        'projects': Project.objects.all(),  
    })


