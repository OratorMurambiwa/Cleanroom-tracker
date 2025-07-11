from django import forms
from .models import Project, Component

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
          'name': forms.TextInput(attrs={'placeholder': 'Project Title', 'class': 'w-full border boarder-[#e7c2c4] rounded-md px-3 py-3 text-sm   focus:outline-none focus:ring-[#a51c30]'
          }),
        }

class ComponentForm(forms.ModelForm):
  """
  Form for creating and updating Component models.
  """
  class Meta:
    model = Component
    fields = ['name', 'description']
    widgets = {
      'name': forms.TextInput(attrs={'placeholder': 'Component Title', 'class': 'w-full border boarder-[#e7c2c4] rounded-md px-3 py-3 text-sm   focus:outline-none focus:ring-[#a51c30]'}),
      'description': forms.Textarea(attrs={'placeholder': 'Component Description', 'class': 'w-full border boarder-[#e7c2c4] rounded-md px-3 py-3 text-sm   focus:outline-none focus:ring-[#a51c30]'})
    }

class TaskForm(forms.ModelForm):
  class Meta:
    model = Task
    fields = ['title', 'description', 'project', 'component', 'assigned_to', 'due_date']