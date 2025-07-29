from django import forms
from .models import Project, Component, Task, Reminder, Document, TravelerDocument
from django.contrib.auth.models import User
from .models import Message

# --- Project Form ---
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Project Title',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Project Description',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
        }

class ComponentForm(forms.ModelForm):
    class Meta:
        model = Component
        fields = ['name', 'description', 'progress']  
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Component Title',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Component Description',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'progress': forms.NumberInput(attrs={
                'min': 0, 'max': 100,
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
        }


# --- Task Form ---
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'project', 'component', 'assigned_to', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Task Title',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Task Description',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
        }

# --- Reminder Form ---
class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ['title', 'note', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'note': forms.Textarea(attrs={'class': 'form-textarea'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

# --- Document Form ---
class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={
                'placeholder': 'Document description...',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-3 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-gray-700'
            }),
        }

# --- Team Member Form ---
class TeamMemberForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all(), label="Select User")

class TechnicianTaskSubmissionForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['notes', 'image', 'video', 'audio']
        widgets = {
            'notes': forms.Textarea(attrs={
                'placeholder': 'Describe what you did...',
                'class': 'w-full border border-[#e7c2c4] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-[#a51c30]'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm'
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm'
            }),
            'audio': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm'
            }),
        }




class TravelerDocUploadForm(forms.Form):
    file = forms.FileField(label="Traveler Document")
    start_section = forms.IntegerField(label="Start Section")
    end_section = forms.IntegerField(label="End Section")
    related_project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        label="Related Project"
    )
    start_page = forms.IntegerField(
        required=False,
        min_value=1,
        label="Start Page (Optional)",
        help_text="Start extracting from this page (1-based index)"
    )
    end_page = forms.IntegerField(
        required=False,
        min_value=1,
        label="End Page (Optional)",
        help_text="End extracting at this page (1-based index)"
    )



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body', 'file']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Type your message...', 'class': 'w-full border rounded p-2'}),
        }
