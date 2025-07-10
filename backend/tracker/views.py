from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import Group


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
                user.groups.set(group)
                return redirect('lead_dashboard')

            elif role == 'technician':
                group = Group.objects.get(name='technician')
                user.groups.set(group)
                return redirect('tech_dashboard')

            else:
                return redirect('generic_dashboard')
        else:
            return render(request, 'tracker/index.html', {'error': 'Invalid credentials'})
    return render(request, 'tracker/index.html')