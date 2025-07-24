from django.db import models
from django.contrib.auth.models import User

# ----------------------- Project -----------------------
class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('ongoing', 'Ongoing'), ('completed', 'Completed'), ('paused', 'Paused')],
        default='ongoing'
    )
    progress = models.FloatField(default=0)
    assigned_users = models.ManyToManyField(User, related_name='assigned_projects', blank=True)

    def __str__(self):
        return self.name

    @property
    def progress(self):
        total = self.tasks.count()
        if total == 0:
            return 0
        approved = self.tasks.filter(is_approved=True).count()
        return int((approved / total) * 100)


# ----------------------- Component -----------------------
class Component(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='components', null=True, blank=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    progress = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[('ongoing', 'Ongoing'), ('completed', 'Completed'), ('paused', 'Paused')],
        default='ongoing'
    )

    def __str__(self):
        return self.name


# ----------------------- Task -----------------------
class Task(models.Model):
    section = models.CharField(max_length=20, blank=True, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    component = models.ForeignKey(Component, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    completed = models.BooleanField(default=False)
    submitted_for_approval = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    notes = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='tasks/images/', blank=True, null=True)
    video = models.FileField(upload_to='tasks/videos/', blank=True, null=True)
    audio = models.FileField(upload_to='tasks/audio/', blank=True, null=True)
    document = models.FileField(upload_to='tasks/docs/', blank=True, null=True)

    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('approved', 'Approved')],
        default='todo'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        link = 'No Project or Component'
        if self.project:
            link = self.project.name
        elif self.component:
            link = self.component.name
        return f'{self.title} -> ({link})'


# ----------------------- Reminder -----------------------
class Reminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.due_date}"


# ----------------------- Document -----------------------
class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"Document for {self.project.name} uploaded on {self.uploaded_at}"
