# views/dashboard_views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from projects.models import Project, Task
from django.utils.timezone import now
from .utils import calculate_progress

@login_required
def home_dashboard(request):
    user = request.user
    projects = Project.objects.filter(contributors=user)
    tasks = Task.objects.filter(assigned_to=user)
    progress = calculate_progress(tasks)

    return render(request, 'dashboard/home_dashboard.html', {
        'projects': projects,
        'tasks': tasks,
        'progress': progress,
    })

@login_required
def lead_dashboard(request):
    projects = Project.objects.all()
    return render(request, 'dashboard/lead_dashboard.html', {
        'projects': projects,
    })

@login_required
def tech_dashboard(request):
    tasks = Task.objects.filter(assigned_to=request.user)
    return render(request, 'dashboard/tech_dashboard.html', {
        'tasks': tasks,
    })
