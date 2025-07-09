from django.contrib import admin
from .models import Project, Component, Task

admin.site.register(Project)
admin.site.register(Component)
admin.site.register(Task)
