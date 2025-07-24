from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db.models import Q
from datetime import datetime
from django.utils import timezone
from .models import Task, Project, Component, Reminder
from .forms import (
ProjectForm, ComponentForm, ReminderForm,
DocumentForm, TeamMemberForm, TaskForm, TechnicianTaskSubmissionForm
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
    tasks = Task.objects.filter(component=component)
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
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if role == 'projectlead':
                user.groups.set([Group.objects.get(name='lead')])
                return redirect('lead_dashboard')
            elif role == 'technician':
                user.groups.set([Group.objects.get(name='technician')])
                return redirect('tech_dashboard')
        return render(request, 'tracker/index.html', {'error': 'Invalid credentials'})
    return render(request, 'tracker/index.html')

# ----------------------- Dashboards -----------------------

@login_required
def lead_dashboard(request):
    projects = Project.objects.all()
    pending_tasks = Task.objects.filter(completed=True, is_approved=False)
    components = Component.objects.all()
    
    return render(request, 'tracker/leaddashboard.html', {
        'projects': projects,
        'pending_tasks': pending_tasks,
        'components': components,
    })

@login_required
def tech_dashboard(request):
    projects = Project.objects.filter(assigned_users=request.user)
    components = Component.objects.all()
    reminders = Reminder.objects.filter(user=request.user)

    return render(request, 'tracker/tech_dashboard.html', {
        'projects': projects,
        'components': components,
        'reminders': reminders,
        
    })

@login_required
def tech_project_list(request):
    projects = Project.objects.all() 
    return render(request, 'tracker/tech_project_list.html', {'projects': projects})


@login_required
def component_detail_view(request, component_id):
    component = get_object_or_404(Component, id=component_id)
    
    # ✅ Update progress before rendering
    update_component_progress(component)

    active_projects = Project.objects.filter(status='ongoing')
    technicians = User.objects.filter(groups__name='technician')

    # Deduplicate techs from task_set
    assigned_techs = User.objects.filter(
        id__in=component.task_set.values_list('assigned_to__id', flat=True)
    ).distinct()

    if request.method == 'POST':
        if 'project_id' in request.POST:
            project_id = request.POST.get('project_id')
            if project_id:
                project = get_object_or_404(Project, id=project_id)
                component.project = project
                component.save()
                messages.success(request, f"Linked to project: {project.name}")
                return redirect('component_detail', component_id=component.id)

        elif 'technician_id' in request.POST:
            tech_id = request.POST.get('technician_id')
            if tech_id:
                tech = get_object_or_404(User, id=tech_id)
                Task.objects.create(
                    title=f"Tech Assigned: {tech.get_full_name()}",
                    description="Auto-assigned via component page",
                    component=component,
                    assigned_to=tech,
                    status='todo'
                )
                messages.success(request, f"{tech.get_full_name()} assigned.")
                return redirect('component_detail', component_id=component.id)

    return render(request, 'tracker/component_detail.html', {
        'component': component,
        'active_projects': active_projects,
        'technicians': technicians,
        'assigned_techs': assigned_techs,
    })

# ----------------------- Project Views -----------------------

@login_required
def project_list_view(request):
    projects = Project.objects.all()
    return render(request, 'tracker/project_list.html', {'projects': projects})

@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    tasks = project.tasks.all()
    components = project.components.all()
    
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', '')

    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if status_filter == 'completed':
        tasks = tasks.filter(is_completed=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(is_completed=False)
    if sort_by == 'due':
        tasks = tasks.order_by('due_date')
    elif sort_by == 'priority':
        tasks = tasks.order_by('priority')

    users = project.assigned_users.all() if hasattr(project, 'assigned_users') else []
    documents = project.documents.all() if hasattr(project, 'documents') else []
    progress = project.progress if hasattr(project, 'progress') else 0

    return render(request, 'tracker/project_detail.html', {
        'project': project,
        'tasks': tasks,
        'components': components,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'users': users,
        'documents': documents,
        'progress': progress,
    })

@login_required
def create_project_view(request):
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lead_dashboard')
    return render(request, 'tracker/create_project.html', {'form': form})

# ----------------------- Component Views -----------------------

@login_required
def create_component_view(request):
    form = ComponentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lead_dashboard')
    return render(request, 'tracker/create_component.html', {'form': form})
    
@login_required
def add_component(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = ComponentForm(request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            component.project = project
            component.save()
            messages.success(request, "Component added!")
            return redirect('project_detail', project_id=project.id)
    else:
        form = ComponentForm()
    return render(request, 'tracker/add_component.html', {'form': form, 'project': project})

@login_required
def edit_component(request, component_id):
    component = get_object_or_404(Component, id=component_id)
    unlinked_tasks = Task.objects.filter(component__isnull=True) | Task.objects.filter(component=component)
    
    if request.method == 'POST':
        form = ComponentForm(request.POST, instance=component)
        if form.is_valid():
            form.save()
            task_ids = request.POST.getlist('tasks')
            Task.objects.filter(id__in=task_ids).update(component=component)
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
    components = Component.objects.all()
    return render(request, 'components.html', {'components': components})
    
def component_list_view(request):
    components = Component.objects.select_related('project').order_by('-updated_at')
    return render(request, 'components.html', {'components': components})
    
# ----------------------- Task Views -----------------------
@login_required
def assign_tasks_view(request, component_id=None):
    projects = Project.objects.all()
    components = Component.objects.all()
    technicians = User.objects.filter(groups__name='technician')
    tasks = Task.objects.filter(completed=True, is_approved=False)

    selected_component = None
    if component_id:
        selected_component = get_object_or_404(Component, id=component_id)

    if request.method == 'POST':
        Task.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            project=Project.objects.get(id=request.POST.get('project')) if request.POST.get('project') else (selected_component.project if selected_component else None),
            component=Component.objects.get(id=request.POST.get('component')) if request.POST.get('component') else selected_component,
            assigned_to=User.objects.get(id=request.POST.get('technician')),
            due_date=request.POST.get('due_date')
        )
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
    task = get_object_or_404(Task, id=task_id, project__isnull=False)

    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_dashboard')

    return render(request, 'tracker/project_task_detail.html', {'task': task})


@login_required
def approve_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        task.is_approved = True
        task.status = "Approved"
        task.save()

        # Update project progress
        if task.project:
            update_project_progress(task.project)

        # Update component progress and timestamp
        if task.component:
            update_component_progress(task.component)
            task.component.updated_at = timezone.now()  # ✅ Force timestamp update
            task.component.save()

        messages.success(request, f"Task '{task.title}' approved.")
    
    return redirect('component_detail', component_id=task.component.id)




@login_required
def tech_tasks_view(request):
    tasks = Task.objects.filter(assigned_to=request.user)
    return render(request, 'tracker/tech_tasks.html', {'tasks': tasks})


@login_required
def task_detail_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_tasks')

    return render(request, 'tracker/task_detail.html', {'task': task})

@user_passes_test(is_lead)
def edit_task_view(request, task_id):
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
        'technicians': technicians
    })

@login_required
def review_task_for_approval(request, task_id):
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
        return redirect('project_detail', project_id=task.project.id if task.project else task.component.project.id)

    return render(request, 'tracker/review_task_for_approval.html', {'task': task})

@login_required
def component_task_detail_view(request, task_id):
    task = get_object_or_404(Task, id=task_id, component__isnull=False)

    # Optional: restrict so only the assigned technician sees it
    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_dashboard')

    return render(request, 'tracker/component_task_detail.html', {'task': task})

@login_required
def component_task_completed_view(request, task_id):
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
    tasks = Task.objects.all()
    reminders = Reminder.objects.filter(user=request.user)
    today = timezone.now().date()
    return render(request, 'calendar.html', {
        'tasks': tasks,
        'reminders': reminders,
        'today': today
    })

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
def technician_dashboard(request):
    reminders = Reminder.objects.filter(user=request.user).order_by('due_date')
    form = ReminderForm()
    
    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            reminder.save()
            return redirect('technician_dashboard')
    
    return render(request, 'dashboard/technician_dashboard.html', {
        'reminders': reminders,
        'form': form,
    })

@login_required
def tech_project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    tasks = Task.objects.filter(project=project, assigned_to=request.user)
    
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', '')
    
    if search_query:
        tasks = tasks.filter(title__icontains=search_query)
    if status_filter == 'completed':
        tasks = tasks.filter(is_completed=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(is_completed=False)
    if sort_by == 'due':
        tasks = tasks.order_by('due_date')
    elif sort_by == 'priority':
        tasks = tasks.order_by('-priority')
    
    return render(request, 'tracker/tech_project_detail.html', {
        'project': project,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
    })
    
@login_required
def tech_component_detail_view(request, component_id):
    component = get_object_or_404(Component, id=component_id)
    tasks = component.task_set.filter(assigned_to=request.user)

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
    
            Task.objects.create(
                title=title,
                section=section, 
                assigned_to_id=user_id,
                project_id=project_id,
                component_id=component_id,
                due_date=due_date
            )
            i += 1
    
        messages.success(request, "All extracted tasks have been saved!")
        return redirect('project_detail', pk=project_id)
    
    return redirect('add_tasks')
    
