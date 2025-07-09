from django.db import models

#project model
class Project(models.Model):
  name = models.CharField(max_length=100)
  description = models.TextField(blank = True)
  start_date = models.DateField(null=True, blank=True)
  end_date = models.DateField(null=True, blank=True)
  status = models.CharField(
    max_length=20,
    choices=[('ongoing', 'Ongoing'), ('completed', 'Completed'),
             ('paused', 'Paused')],
    default='ongoing'
  )
  def __str__(self):
    return self.name

#component model
class Component(models.Model):
  name = models.CharField(max_length=100)
  description = models.TextField(blank=True)
  start_date = models.DateField(null=True, blank=True)
  end_date = models.DateField(null=True, blank=True)
  status = models.CharField(
    max_length=20,
    choices=[('ongoing', 'Ongoing'), ('completed', 'Completed'),
             ('paused', 'Paused')],
    default='ongoing'
  )

  def __str__(self):
    return self.name

#task model
class Task(models.Model):
  title = models.CharField(max_length=100)
  description = models.TextField(blank=True)
  project = models.ForeignKey(
    Project,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
  )
  component = models.ForeignKey(
    Component,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
  )
  assigned_to = models.CharField(max_length=100)
  due_date = models.DateField(null=True, blank=True)
  status = models.CharField(
    max_length=20,
    choices=[('todo', 'To Do'), ('in_progress', 'In Progress'),
             ('completed', 'Completed'), ('approved', 'Approved')],
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

