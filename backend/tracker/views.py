from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import Group
from .models import Task, Project, Component
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test


def update_project_progress(project):
    tasks = Task.objects.filter(project=project)
    if tasks.exists():
        total_tasks = tasks.count()
        if total_tasks > 0:  # Prevent division by zero
            completed_tasks = tasks.filter(completed=True).count()
            project.progress = (completed_tasks / total_tasks) * 100
        else:
            project.progress = 0
        project.save()


@login_required
def role_based_redirect(request):
    user = request.user
    if user.groups.filter(name='lead').exists():
        return redirect('lead_dashboard')
    elif user.groups.filter(name='technician').exists():
        return redirect('tech_dashboard')
    return render(request, 'tracker/genericdashboard.html')


def tasks_view(request):
    return render(request, 'tracker/tasks.html')


@login_required
def lead_dashboard(request):
    return render(request, 'tracker/leaddashboard.html')


@login_required
def tech_dashboard(request):
    return render(request, 'tracker/techdashboard.html')


def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if role == 'projectlead':
                group = Group.objects.get(name='lead')
                user.groups.set([group])
                return redirect('lead_dashboard')

            elif role == 'technician':
                group = Group.objects.get(name='technician')
                user.groups.set([group])
                return redirect('tech_dashboard')

            else:
                return redirect('generic_dashboard')
        else:
            return render(request, 'tracker/index.html',
                          {'error': 'Invalid credentials'})
    return render(request, 'tracker/index.html')

@login_required
def submit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        task.is_completed = True
        task.notes = request.POST.get('notes')
        if 'image' in request.FILES['image']:
            task.image = request.FILES['image']
        task.save()
    return redirect('tech_dashboard')

@login_required
def approve_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.is_approved = True
    task.save()
    update_project_progress(task.project)
    return redirect('lead_dashboard')

@login_required
def project_list_view(request):
    projects = Project.objects.all()
    return render(request, 'tracker/project_list.html', {'projects': projects})

@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    tasks = Task.objects.filter(project=project)
    return render(request, 'tracker/ProjectDetails.html', {
        'project': project,
        'tasks': tasks
    })

@login_required
def assign_tasks_view(request):
    projects = Project.objects.all()
    components = Component.objects.all()
    technicians = User.objects.filter(groups__name='technician')
    tasks = Task.objects.filter(completed=True, is_approved=False)


    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        project_id = request.POST.get('project')
        component_id = request.POST.get('component')
        technician_id = request.POST.get('technician')
        due_date = request.POST.get('due_date')

        project = Project.objects.get(id=project_id)
        component = Component.objects.get(id=component_id) if component_id else None
        technician = User.objects.get(id=technician_id)

        Task.objects.create(
            title=title,
            description=description,
            project=project,
            component=component,
            assigned_to=technician,
            due_date=due_date
        )
        return redirect('assign_tasks')

    return render(request, 'tracker/assigntasks.html', {
        'projects': projects,
        'components': components,
        'technicians': technicians,
        'pending_tasks': tasks
    })

@login_required
def tech_task_list(request):
    tasks = Task.objects.filter(assigned_to=request.user)

    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        notes = request.POST.get('notes')
        image = request.FILES.get('image')

        task = Task.objects.get(id=task_id, assigned_to=request.user)
        task.is_completed = True
        task.notes = notes
        if image:
            task.image = image
        task.submitted_for_approval = True
        task.save()

        return redirect('tech_tasks')

    return render(request, 'tracker/tasks.html', {'tasks': tasks})

@login_required
def task_detail_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # Optionally: restrict techs to only their tasks
    if request.user.groups.filter(name='technician').exists() and task.assigned_to != request.user:
        return redirect('tech_tasks')

    return render(request, 'tracker/task_detail.html', {'task': task})

def is_lead(user):
    return user.groups.filter(name='lead').exists()

@user_passes_test(is_lead)
def edit_task_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    technicians = User.objects.filter(groups__name='technician')

    if request.method == 'POST':
        task.title = request.POST.get('title')
        task.description = request.POST.get('description')
        task.notes = request.POST.get('notes')
        tech_id = request.POST.get('assigned_to')
        if tech_id:
            task.assigned_to = User.objects.get(id=tech_id)
        task.save()
        return redirect('task_detail', task_id=task.id)

    return render(request, 'tracker/edit_task.html', {
        'task': task,
        'technicians': technicians
    })
