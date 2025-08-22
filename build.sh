#!/usr/bin/env bash
# Build script for Render deployment

# Exit on any error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Install additional production dependencies
pip install dj-database-url psycopg2-binary whitenoise

# Collect static files
python manage.py collectstatic --noinput

# Run database migrations
python manage.py migrate

# Create superuser if it doesn't exist (optional)
# echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'admin123') if not User.objects.filter(username='admin').exists() else None" | python manage.py shell

echo "Build completed successfully!"
