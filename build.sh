#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
mkdir -p media
python manage.py collectstatic --no-input
python manage.py migrate
# Create superuser automatically if it doesn't exist
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='Admin123!'
    )
    print('✅ ADMIN CREATED SUCCESSFULLY!')
else:
    print('ℹ️ Admin already exists')
"