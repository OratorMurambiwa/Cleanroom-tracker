from django.shortcuts import render

def tasks_view(request):
    return render(request, 'tracker/tasks.html')
