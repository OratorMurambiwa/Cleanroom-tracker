from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db.models import Q
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import logout
import pandas as pd
import fitz 
import re
import os
import uuid
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import now
from .models import Task, Project, Component, Reminder, InventoryUpload, LookupHistory, Message, MessageThread, StoredTravelerFile
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
    return render(request, 'tracker/components.html', {'components': components})

@login_required
def component_list_view(request):
    components = Component.objects.select_related('project').order_by('-updated_at')
    return render(request, 'tracker/component_list.html', {'components': components})

    
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
        # Create the task without components
        task = Task.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            project=Project.objects.get(id=request.POST.get('project')) if request.POST.get('project') else (selected_component.project if selected_component else None),
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

        # Update progress for all linked components
        for component in task.components.all():
            update_component_progress(component)
            component.updated_at = timezone.now()
            component.save()

        messages.success(request, f"Task '{task.title}' approved.")

    # Redirect to the first component's detail view (or somewhere else)
    first_component = task.components.first()
    if first_component:
        return redirect('component_detail', component_id=first_component.id)
    else:
        return redirect('all_tasks')  # fallback if no components are linked





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

#delete tasks
def delete_task_view(request, task_id):
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
    tasks = Task.objects.filter(due_date__isnull=False)
    reminders = Reminder.objects.filter(user=request.user)
    today = timezone.now().date()

    return render(request, 'tracker/calendar.html', {
        'tasks': tasks,
        'reminders': reminders,
        'today': today,
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
def delete_reminder(request, reminder_id):
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    reminder.delete()
    return redirect('calendar')

@login_required
def technician_dashboard(request):
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

    return render(request, 'tracker/tech_component_detail.htm¹l', {
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



def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())




#view for excel file extraction

# Asset Lookup View
@login_required
def asset_lookup_view(request):
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
        else:
            try:
                latest_file = InventoryUpload.objects.latest('uploaded_at')
                file_path = latest_file.file.path
                file_uploaded = True
                last_file_url = latest_file.file.url
                last_file_name = os.path.basename(latest_file.file.name)
            except InventoryUpload.DoesNotExist:
                error_message = "No Excel file found. Please upload one."
                file_path = None

        if file_path:
            try:
                df = pd.read_excel(file_path)
                df.columns = df.columns.str.strip()

                if search_query and search_field in df.columns:
                    col_data = df[search_field].astype(str).str.strip()
                    if search_field == "Assembly number (Description)":
                        # Exact match (case-insensitive)
                        filtered_df = df[col_data.str.lower() == search_query.lower()]
                    else:
                        # Partial match
                        filtered_df = df[col_data.str.lower().str.contains(search_query.lower())]
                else:
                    filtered_df = df

                asset_data = filtered_df.to_dict(orient='records')

                if search_query:
                    LookupHistory.objects.create(user=request.user, query=search_query)
                recent_lookups = LookupHistory.objects.filter(user=request.user).order_by('-timestamp')[:5]

            except Exception as e:
                error_message = f"Error reading file: {e}"

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
    })

# ----------------------- Upload Traveler View -----------------------

@login_required
def upload_tasks_from_traveler_view(request):
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
                doc = fitz.open(temp_filename)

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

                doc.close()
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
                component=component,
                project=project,
                section=section,
            )

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
        'all_projects': Project.objects.all(),  # 👈 add this line for dropdown
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


def all_tasks_view(request):
    tasks = Task.objects.all()
    query = request.GET.get('q', '')
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    if query:
        tasks = tasks.filter(
            Q(title__icontains=query) |
            Q(assigned_to__first_name__icontains=query) |
            Q(assigned_to__last_name__icontains=query)
        )

    if start_date:
        tasks = tasks.filter(due_date__gte=start_date)

    if end_date:
        tasks = tasks.filter(due_date__lte=end_date)

    return render(request, 'tracker/alltasks.html', {
        'tasks': tasks,
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
