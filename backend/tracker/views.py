from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import Group
from .models import Task, Project


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