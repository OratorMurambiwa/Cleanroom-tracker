
import os
import sys

# Add the backend directory to Python path
sys.path.append('backend')

# Change to backend directory
os.chdir('backend')

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Run Django development server
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    django.setup()
    execute_from_command_line(['manage.py', 'runserver', '0.0.0.0:5000'])
