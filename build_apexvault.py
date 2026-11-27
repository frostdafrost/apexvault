import os
import subprocess
import sys

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {path}")

def run_cmd(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

print("--- Step 1: Setting up Environment ---")
python_exe = sys.executable
run_cmd(f'"{python_exe}" -m venv venv')

if os.name == 'nt': # Windows
    pip_exe = r"venv\Scripts\pip.exe"
    django_exe = r"venv\Scripts\django-admin.exe"
    python_venv = r"venv\Scripts\python.exe"
else: # Mac/Linux
    pip_exe = "venv/bin/pip"
    django_exe = "venv/bin/django-admin"
    python_venv = "venv/bin/python"

run_cmd(f'"{pip_exe}" install django')
run_cmd(f'"{django_exe}" startproject apex_vault .')
run_cmd(f'"{python_venv}" manage.py startapp banking')

print("--- Step 2: Writing Core Files ---")

# 1. Settings
write_file('apex_vault/settings.py', """
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-apex-vault-secret-key-123'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'banking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'apex_vault.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'apex_vault.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
""")

# 2. Project URLs
write_file('apex_vault/urls.py', """
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('banking.urls')),
]
""")

# 3. Models
write_file('banking/models.py', """
from django.db import models
from django.contrib.auth.models import User
import random

def generate_account_number():
    return str(random.randint(1000000000, 9999999999))

class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    account_number = models.CharField(max_length=12, unique=True, default=generate_account_number)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=190000.00)
    is_frozen = models.BooleanField(default=False)
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    beneficiary_name = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Completed')

    class Meta:
        ordering = ['-timestamp']

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (('Pending', 'Pending'), ('Requires Code', 'Requires Code'), ('Processing', 'Processing'), ('Completed', 'Completed'), ('Rejected', 'Rejected'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    admin_note = models.TextField(blank=True, null=True)
    required_code = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Beneficiary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beneficiaries')
    name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    swift_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)

class AuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='actions_taken')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actions_received')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
""")

# 4. Views
write_file('banking/views.py', """
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Account, Transaction, Beneficiary, WithdrawalRequest

def home(request):
    if request.user.is_authenticated: return redirect('dashboard')
    return render(request, 'home.html')

@login_required
def dashboard(request):
    account, created = Account.objects.get_or_create(user=request.user)
    latest_withdrawal = WithdrawalRequest.objects.filter(user=request.user, status__in=['Requires Code', 'Processing']).last()
    expenses = Transaction.objects.filter(account=account, amount__lt=0).values('transaction_type').annotate(total=Sum('amount'))
    expense_labels = [item['transaction_type'] for item in expenses]
    expense_data = [abs(float(item['total'])) for item in expenses]
    if not expense_labels:
        expense_labels = ["Transfers", "Withdrawals", "Bills"]
        expense_data = [1500, 800, 400]
    context = {'account': account, 'latest_withdrawal': latest_withdrawal, 'expense_labels': json.dumps(expense_labels), 'expense_data': json.dumps(expense_data)}
    return render(request, 'dashboard.html', context)

@login_required
def transfer(request):
    account = Account.objects.get(user=request.user)
    beneficiaries = Beneficiary.objects.filter(user=request.user)
    return render(request, 'transfer.html', {'account': account, 'beneficiaries': beneficiaries})

@login_required
def add_beneficiary(request):
    if request.method == 'POST':
        Beneficiary.objects.create(user=request.user, name=request.POST.get('name'), account_number=request.POST.get('account_number'), bank_name=request.POST.get('bank_name'), swift_code=request.POST.get('swift_code'), country=request.POST.get('country'))
    return redirect('transfer')

@login_required
def submit_withdrawal(request):
    if request.method == 'POST':
        WithdrawalRequest.objects.create(user=request.user, amount=request.POST.get('amount'), bank_name=request.POST.get('bank_name'), account_name=request.POST.get('account_name'), account_number=request.POST.get('account_number'))
    return redirect('dashboard')

@login_required
def verify_imt_code(request, request_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=request_id, user=request.user)
    if request.method == 'POST':
        if request.POST.get('imt_code') == withdrawal.required_code:
            withdrawal.status = 'Processing'
            withdrawal.save()
    return redirect('dashboard')
""")

# 5. Admin Views
write_file('banking/admin_views.py', """
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from .models import WithdrawalRequest, AuditLog
from decimal import Decimal

def is_admin(user): return user.is_staff or user.is_superuser

@user_passes_test(is_admin)
def admin_dashboard(request):
    users = User.objects.all().select_related('account')
    withdrawals = WithdrawalRequest.objects.all().order_by('-created_at')
    audit_logs = AuditLog.objects.all().order_by('-timestamp')[:10]
    context = {'users': users, 'withdrawals': withdrawals, 'audit_logs': audit_logs}
    return render(request, 'admin_dashboard.html', context)

@user_passes_test(is_admin)
def edit_user_balance(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        account = user.account
        old_balance = account.balance
        account.balance = Decimal(request.POST.get('balance'))
        account.save()
        AuditLog.objects.create(admin=request.user, target_user=user, action=f"Changed balance from ${old_balance} to ${account.balance}")
        return redirect('admin_dashboard')

@user_passes_test(is_admin)
def toggle_freeze_account(request, user_id):
    user = get_object_or_404(User, id=user_id)
    account = user.account
    account.is_frozen = not account.is_frozen
    account.save()
    AuditLog.objects.create(admin=request.user, target_user=user, action=f"Account {'Frozen' if account.is_frozen else 'Unfrozen'}")
    return redirect('admin_dashboard')

@user_passes_test(is_admin)
def manage_withdrawal(request, request_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=request_id)
    if request.method == 'POST':
        withdrawal.amount = request.POST.get('amount')
        withdrawal.status = request.POST.get('status')
        withdrawal.admin_note = request.POST.get('admin_note')
        withdrawal.required_code = request.POST.get('required_code')
        withdrawal.save()
        return redirect('admin_dashboard')
    return render(request, 'admin_manage_withdrawal.html', {'withdrawal': withdrawal})
""")

# 6. Banking URLs
write_file('banking/urls.py', """
from django.urls import path
from . import views, admin_views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transfer/', views.transfer, name='transfer'),
    path('add-beneficiary/', views.add_beneficiary, name='add_beneficiary'),
    path('withdraw/', views.submit_withdrawal, name='submit_withdrawal'),
    path('verify-code/<int:request_id>/', views.verify_imt_code, name='verify_imt_code'),
    path('control-panel/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('control-panel/withdrawal/<int:request_id>/', admin_views.manage_withdrawal, name='manage_withdrawal'),
    path('control-panel/user/<int:user_id>/balance/', admin_views.edit_user_balance, name='edit_user_balance'),
    path('control-panel/user/<int:user_id>/freeze/', admin_views.toggle_freeze_account, name='toggle_freeze_account'),
]
""")

print("--- Step 3: Writing Templates ---")

# 7. Home Template
write_file('banking/templates/home.html', """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><title>ApexVault | Next-Gen Banking</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg-base: #050810; --primary: #6D28D9; --accent: #06B6D4; --text-muted: #94a3b8; --border: rgba(255,255,255,0.1); }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: var(--bg-base); color: white; overflow-x: hidden; }
        .glow-bg { position: absolute; width: 100%; height: 100%; z-index: -1; overflow: hidden; }
        .glow-circle { position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.4; }
        .glow-1 { width: 600px; height: 600px; background: var(--primary); top: -200px; left: -100px; }
        .glow-2 { width: 500px; height: 500px; background: var(--accent); top: 20%; right: -200px; opacity: 0.2; }
        .navbar { display: flex; justify-content: space-between; padding: 20px 8%; position: fixed; width: 100%; top: 0; z-index: 100; background: rgba(5,8,16,0.7); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); }
        .brand { font-size: 24px; font-weight: 800; letter-spacing: 1px; }
        .nav-links { display: flex; gap: 30px; align-items: center; }
        .nav-links a { text-decoration: none; color: var(--text-muted); font-weight: 500; }
        .btn-register { background: white; color: var(--bg-base) !important; padding: 12px 28px; border-radius: 30px; font-weight: 700; }
        .hero { min-height: 100vh; display: flex; align-items: center; padding: 120px 8% 60px; }
        .hero-content { flex: 1.2; padding-right: 50px; }
        .hero-badge { display: inline-flex; background: rgba(6,182,212,0.1); color: var(--accent); padding: 8px 16px; border-radius: 30px; font-size: 13px; font-weight: 600; margin-bottom: 25px; border: 1px solid rgba(6,182,212,0.2); }
        .hero h1 { font-size: 64px; font-weight: 800; line-height: 1.1; margin-bottom: 20px; }
        .hero h1 span { background: linear-gradient(90deg, var(--accent), var(--primary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero p { font-size: 18px; color: var(--text-muted); margin-bottom: 40px; max-width: 500px; }
        .btn-primary-lg { background: var(--primary); color: white; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: 700; box-shadow: 0 0 30px rgba(109,40,217,0.5); }
        .hero-graphic { flex: 1; display: flex; justify-content: center; perspective: 1000px; }
        .hologram-card { width: 100%; max-width: 450px; background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 24px; padding: 30px; transform: rotateY(-15deg); animation: float 6s ease-in-out infinite; }
        @keyframes float { 50% { transform: rotateY(-15deg) translateY(-20px); } }
        .trust-stats { display: flex; justify-content: space-between; padding: 40px 8%; border-top: 1px solid var(--border); background: rgba(255,255,255,0.01); }
        .reviews { padding: 100px 8%; text-align: center; border-top: 1px solid var(--border); }
        .review-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; text-align: left; margin-top: 40px;}
        .review-card { background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 30px; border-radius: 20px; }
        .stars { color: #fbbf24; margin-bottom: 15px; }
        .footer { background: #020408; padding: 60px 8%; border-top: 1px solid var(--border); text-align: center; color: var(--text-muted); }
    </style>
</head>
<body>
    <div class="glow-bg"><div class="glow-circle glow-1"></div><div class="glow-circle glow-2"></div></div>
    <nav class="navbar">
        <div class="brand">🛡️ APEXVAULT</div>
        <div class="nav-links"><a href="/login/">Log In</a><a href="/login/" class="btn-register">Open Account</a></div>
    </nav>
    <header class="hero">
        <div class="hero-content">
            <div class="hero-badge">⚡ V2.0 Platform Live</div>
            <h1>Banking built for the <span>digital</span> age.</h1>
            <p>Experience zero-friction global transfers, AI-driven analytics, and military-grade security.</p>
            <a href="/login/" class="btn-primary-lg">Get Started Now</a>
        </div>
        <div class="hero-graphic">
            <div class="hologram-card">
                <p style="color:var(--text-muted); margin-bottom:10px;">Total Net Worth</p>
                <h1 style="font-size:42px; margin-bottom:20px;">$190,000.00</h1>
                <div style="height:100px; border-bottom:2px solid var(--accent); background:linear-gradient(to top, rgba(6,182,212,0.2), transparent);"></div>
            </div>
        </div>
    </header>
    <section class="trust-stats">
        <div><h3 style="font-size:32px;">$5B+</h3><p style="color:var(--text-muted);">Processed</p></div>
        <div><h3 style="font-size:32px;">99.99%</h3><p style="color:var(--text-muted);">Uptime</p></div>
        <div><h3 style="font-size:32px;">150+</h3><p style="color:var(--text-muted);">Countries</p></div>
    </section>
    <section class="reviews">
        <h2>Trusted by industry leaders.</h2>
        <div class="review-grid">
            <div class="review-card"><div class="stars">★★★★★</div><p>"ApexVault replaced my traditional bank. Wire transfers are instant."</p><br><strong>- Martin Davis</strong></div>
            <div class="review-card"><div class="stars">★★★★★</div><p>"The analytics dashboard is unreal. Legacy banking apps are put to shame."</p><br><strong>- Sarah Jenkins</strong></div>
            <div class="review-card"><div class="stars">★★★★★</div><p>"The IMT code verification process is seamless and makes me feel secure."</p><br><strong>- David O.</strong></div>
        </div>
    </section>
    <footer class="footer"><h3>🛡️ APEXVAULT</h3><p>&copy; 2024 ApexVault Financial Technologies.</p></footer>
</body>
</html>
""")

# 8. Login Template
write_file('banking/templates/login.html', """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><title>Login | ApexVault</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { background: #4318ff; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: 'Plus Jakarta Sans', sans-serif; margin: 0; }
        .login-box { background: white; padding: 40px; border-radius: 20px; width: 350px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); text-align: center; }
        h2 { color: #2b3674; margin-bottom: 20px; }
        input { width: 100%; padding: 15px; margin-bottom: 15px; border: 1px solid #e0e5f2; border-radius: 10px; box-sizing: border-box; outline: none; }
        button { width: 100%; padding: 15px; background: #4318ff; color: white; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🛡️ ApexVault</h2>
        <form method="POST">
            {% csrf_token %}
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>
""")

# 9. Base Template
write_file('banking/templates/base.html', """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><title>ApexVault</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg-main: #f4f7fe; --bg-sidebar: #ffffff; --bg-card: #ffffff; --primary: #4318ff; --text-dark: #2b3674; --text-muted: #a3aed0; --border: #e0e5f2; --success: #05cd99; --danger: #ee5d50; }
        [data-theme="dark"] { --bg-main: #0b1437; --bg-sidebar: #111c44; --bg-card: #111c44; --text-dark: #ffffff; --border: #1b254b; }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; transition: 0.3s; }
        body { background: var(--bg-main); color: var(--text-dark); display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 260px; background: var(--bg-sidebar); padding: 30px 20px; border-right: 1px solid var(--border); }
        .brand { font-size: 22px; font-weight: 700; color: var(--primary); margin-bottom: 30px; }
        .nav-item { display: flex; align-items: center; gap: 15px; padding: 12px; color: var(--text-muted); text-decoration: none; font-weight: 600; border-radius: 10px; margin-bottom: 5px; }
        .nav-item:hover, .nav-item.active { background: var(--bg-main); color: var(--primary); }
        .main-wrapper { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
        .topbar { display: flex; justify-content: space-between; padding: 20px 40px; align-items: center; }
        .content-area { padding: 0 40px 40px 40px; }
        .card { background: var(--bg-card); border-radius: 20px; padding: 25px; box-shadow: 0 10px 20px rgba(0,0,0,0.02); border: 1px solid var(--border); }
        .btn { padding: 12px 20px; border-radius: 10px; border: none; font-weight: 600; cursor: pointer; background: var(--primary); color: white; }
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: none; justify-content: center; align-items: center; z-index: 1000; }
        .modal-box { background: var(--bg-card); padding: 30px; border-radius: 20px; width: 400px; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-size: 13px; margin-bottom: 5px; font-weight: 600; }
        .input-group input, .input-group select { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-main); color: var(--text-dark); outline: none; }
    </style>
</head>
<body>
    <aside class="sidebar">
        <div class="brand">🛡️ APEXVAULT</div>
        <a href="/dashboard/" class="nav-item active">📊 Dashboard</a>
        <a href="/transfer/" class="nav-item">💸 Transfer Funds</a>
        {% if user.is_staff %}
        <a href="/control-panel/" class="nav-item" style="color: var(--danger); margin-top: 20px;">⚡ Admin Panel</a>
        {% endif %}
        <a href="/logout/" class="nav-item" style="color: var(--danger); margin-top: 50px;">🚪 Logout</a>
    </aside>
    <main class="main-wrapper">
        <header class="topbar">
            <div><p style="color: var(--text-muted); font-size: 14px;">Hi {{ user.username|title }}</p><h2 style="font-size: 20px;">Welcome Back</h2></div>
            <div style="display: flex; gap: 20px; align-items: center;">
                <button onclick="toggleDarkMode()" style="background:none; border:none; font-size:20px; cursor:pointer;">🌓</button>
                <div style="width: 40px; height: 40px; background: var(--primary); color: white; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold;">{{ user.username|first|upper }}</div>
            </div>
        </header>
        <div class="content-area">
            {% if account.is_frozen %}
            <div style="background: var(--danger); color: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-weight: bold; text-align: center;">⚠️ Your account is currently suspended.</div>
            {% endif %}
            {% block content %}{% endblock %}
        </div>
    </main>
    <script>
        function toggleDarkMode() {
            const isDark = document.body.getAttribute('data-theme') === 'dark';
            document.body.setAttribute('data-theme', isDark ? 'light' : 'dark');
        }
    </script>
    {% block scripts %}{% endblock %}
</body>
</html>
""")

# 10. Dashboard Template
write_file('banking/templates/dashboard.html', """
{% extends 'base.html' %}
{% block content %}
<style>
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 25px; margin-top: 20px; }
    .balance-card { background: linear-gradient(135deg, var(--primary), #7551ff); color: white; padding: 30px; border-radius: 20px; }
    .card-container { perspective: 1000px; height: 200px; }
    .credit-card { width: 100%; height: 100%; position: relative; transition: 0.8s; transform-style: preserve-3d; cursor: pointer; }
    .card-container:hover .credit-card { transform: rotateY(180deg); }
    .card-front, .card-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 20px; padding: 25px; color: white; background: linear-gradient(135deg, #4318ff, #7551ff); }
    .card-back { background: linear-gradient(135deg, #2b3674, #111c44); transform: rotateY(180deg); display: flex; flex-direction: column; justify-content: center; align-items: center; }
</style>
<div class="grid">
    <div>
        <div class="balance-card">
            <p style="opacity: 0.8;">Account Balance</p>
            <h1 style="font-size: 40px; margin: 10px 0;">$ {{ account.balance }}</h1>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px;">
                <p style="letter-spacing: 1px;">{{ account.account_number }}</p>
                <button class="btn" style="background: #2200aa;" onclick="document.getElementById('withdrawModal').style.display='flex'">Withdraw</button>
            </div>
        </div>
        <div class="card" style="margin-top: 25px;">
            <h3>Expense Analytics</h3>
            <canvas id="expenseChart" height="120"></canvas>
        </div>
    </div>
    <div>
        <div class="card-container" style="margin-bottom: 20px;">
            <div class="credit-card">
                <div class="card-front">
                    <div style="display: flex; justify-content: space-between; font-size: 20px;"><span>VISA</span><span>💳</span></div>
                    <div style="margin-top: 40px; font-size: 22px; letter-spacing: 2px;">**** **** **** 4921</div>
                    <div style="display: flex; justify-content: space-between; margin-top: 20px; font-size: 12px;">
                        <div><span style="opacity:0.7;">CARD HOLDER</span><br><strong>{{ user.username|upper }}</strong></div>
                        <div><span style="opacity:0.7;">EXPIRES</span><br><strong>12/28</strong></div>
                    </div>
                </div>
                <div class="card-back"><p style="opacity: 0.7;">CVV</p><h2 style="background: white; color: black; padding: 5px 20px; border-radius: 5px;">889</h2></div>
            </div>
        </div>
        <div class="card" style="margin-bottom: 20px;"><p style="color: var(--text-muted);">Total Income</p><h3 style="color: var(--success);">+${{ account.total_income }}</h3></div>
        <div class="card"><p style="color: var(--text-muted);">Total Expense</p><h3 style="color: var(--danger);">-${{ account.total_expense }}</h3></div>
    </div>
</div>
<div class="modal-overlay" id="withdrawModal">
    <div class="modal-box">
        <h3 style="margin-bottom: 20px;">Withdraw Funds</h3>
        <form method="POST" action="/withdraw/">
            {% csrf_token %}
            <div class="input-group"><label>Amount ($)</label><input type="number" name="amount" required></div>
            <div class="input-group"><label>Bank Name</label><input type="text" name="bank_name" required></div>
            <div class="input-group"><label>Account Name</label><input type="text" name="account_name" required></div>
            <div class="input-group"><label>Account Number</label><input type="text" name="account_number" required></div>
            <button type="submit" class="btn" style="width: 100%;">Submit Request</button>
        </form>
    </div>
</div>
{% if latest_withdrawal and latest_withdrawal.status == 'Requires Code' %}
<div class="modal-overlay" style="display: flex;">
    <div class="modal-box">
        <h3>⚠️ Security Action Required</h3>
        <p style="margin: 15px 0; color: var(--text-muted);"><strong>Admin Note:</strong> {{ latest_withdrawal.admin_note }}</p>
        <form method="POST" action="/verify-code/{{ latest_withdrawal.id }}/">
            {% csrf_token %}
            <div class="input-group"><label>Enter IMT CODE</label><input type="text" name="imt_code" required></div>
            <button type="submit" class="btn" style="width: 100%;">Confirm Code</button>
        </form>
    </div>
</div>
{% endif %}
{% endblock %}
{% block scripts %}
<script>
    new Chart(document.getElementById('expenseChart'), {
        type: 'doughnut',
        data: { labels: {{ expense_labels|safe }}, datasets: [{ data: {{ expense_data|safe }}, backgroundColor: ['#4318ff', '#05cd99', '#ee5d50'], borderWidth: 0 }] },
        options: { cutout: '70%' }
    });
</script>
{% endblock %}
""")

# 11. Transfer Template
write_file('banking/templates/transfer.html', """
{% extends 'base.html' %}
{% block content %}
<div class="card" style="max-width: 600px; margin: 20px auto;">
    <h2>Wire Transfer</h2>
    <form method="POST" action="#">
        {% csrf_token %}
        <div class="input-group">
            <label>Select Beneficiary</label>
            <select id="bene-select" onchange="fillBene()">
                <option value="">-- New --</option>
                {% for b in beneficiaries %}
                <option data-name="{{ b.name }}" data-acc="{{ b.account_number }}" data-bank="{{ b.bank_name }}">{{ b.name }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="input-group"><label>Amount ($)</label><input type="number" name="amount" required></div>
        <div class="input-group"><label>Beneficiary Name</label><input type="text" id="b-name" name="name" required></div>
        <div class="input-group"><label>Account Number</label><input type="text" id="b-acc" name="account_number" required></div>
        <div class="input-group"><label>Bank Name</label><input type="text" id="b-bank" name="bank_name" required></div>
        <button type="submit" class="btn" style="width: 100%;">Send Funds</button>
    </form>
</div>
{% endblock %}
{% block scripts %}
<script>
    function fillBene() {
        const opt = document.getElementById('bene-select').selectedOptions[0];
        if(opt.value) {
            document.getElementById('b-name').value = opt.dataset.name;
            document.getElementById('b-acc').value = opt.dataset.acc;
            document.getElementById('b-bank').value = opt.dataset.bank;
        }
    }
</script>
{% endblock %}
""")

# 12. Admin Dashboard Template
write_file('banking/templates/admin_dashboard.html', """
{% extends 'base.html' %}
{% block content %}
<h2 style="margin-top: 20px;">Admin Control Center</h2>
<div class="card" style="margin-top: 20px; overflow-x: auto;">
    <h3>Manage Users</h3>
    <table style="width: 100%; text-align: left; margin-top: 15px; border-collapse: collapse;">
        <tr style="border-bottom: 1px solid var(--border);">
            <th style="padding: 10px;">User</th><th style="padding: 10px;">Balance</th><th style="padding: 10px;">Status</th><th style="padding: 10px;">Actions</th>
        </tr>
        {% for u in users %}
        <tr style="border-bottom: 1px solid var(--border);">
            <td style="padding: 10px;">{{ u.username }}</td>
            <td style="padding: 10px;">${{ u.account.balance }}</td>
            <td style="padding: 10px;">{% if u.account.is_frozen %}<span style="color:var(--danger);">Frozen</span>{% else %}<span style="color:var(--success);">Active</span>{% endif %}</td>
            <td style="padding: 10px;">
                <form method="POST" action="/control-panel/user/{{ u.id }}/balance/" style="display: flex; gap: 5px;">
                    {% csrf_token %}
                    <input type="number" name="balance" value="{{ u.account.balance }}" style="width: 100px; padding: 5px; border-radius: 5px; border: 1px solid var(--border);">
                    <input type="text" name="reason" placeholder="Reason" style="width: 120px; padding: 5px; border-radius: 5px; border: 1px solid var(--border);">
                    <button type="submit" class="btn" style="padding: 5px 10px;">Update</button>
                </form>
                <a href="/control-panel/user/{{ u.id }}/freeze/" style="font-size: 12px; display:inline-block; margin-top:5px; color:var(--primary);">Toggle Freeze</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
<div class="card" style="margin-top: 20px;">
    <h3>Pending Withdrawals</h3>
    <ul>
    {% for w in withdrawals %}
        <li style="padding: 10px 0; border-bottom: 1px solid var(--border);">
            {{ w.user.username }} requested ${{ w.amount }} (Status: {{ w.status }}) 
            <a href="/control-panel/withdrawal/{{ w.id }}/" style="color: var(--primary); margin-left: 10px;">Manage</a>
        </li>
    {% empty %}
        <li>No pending withdrawals.</li>
    {% endfor %}
    </ul>
</div>
{% endblock %}
""")

# 13. Admin Manage Withdrawal Template
write_file('banking/templates/admin_manage_withdrawal.html', """
{% extends 'base.html' %}
{% block content %}
<div class="card" style="max-width: 600px; margin: 20px auto;">
    <h2>Manage Withdrawal</h2>
    <p>User: <strong>{{ withdrawal.user.username }}</strong></p>
    <form method="POST">
        {% csrf_token %}
        <div class="input-group"><label>Amount ($)</label><input type="number" name="amount" value="{{ withdrawal.amount }}" step="0.01" required></div>
        <div class="input-group">
            <label>Status</label>
            <select name="status">
                <option value="Pending" {% if withdrawal.status == 'Pending' %}selected{% endif %}>Pending</option>
                <option value="Requires Code" {% if withdrawal.status == 'Requires Code' %}selected{% endif %}>Requires Code</option>
                <option value="Processing" {% if withdrawal.status == 'Processing' %}selected{% endif %}>Processing</option>
                <option value="Completed" {% if withdrawal.status == 'Completed' %}selected{% endif %}>Completed</option>
                <option value="Rejected" {% if withdrawal.status == 'Rejected' %}selected{% endif %}>Rejected</option>
            </select>
        </div>
        <div class="input-group"><label>Admin Note / Message to User</label><input type="text" name="admin_note" value="{{ withdrawal.admin_note|default:'' }}"></div>
        <div class="input-group"><label>Required IMT Code</label><input type="text" name="required_code" value="{{ withdrawal.required_code|default:'' }}"></div>
        <button type="submit" class="btn">Update Request</button>
        <a href="/control-panel/" style="display:block; text-align:center; margin-top:10px; color:var(--text-muted); text-decoration:none;">Cancel</a>
    </form>
</div>
{% endblock %}
""")

print("--- Step 4: Migrations and Setup ---")
run_cmd(f'"{python_venv}" manage.py makemigrations banking')
run_cmd(f'"{python_venv}" manage.py migrate')

print("\n=======================================================")
print("APEXVAULT PRO SUCCESSFULLY CREATED!")
print("=======================================================")
print("\nTo run your server, type these two commands in your terminal:")
print("\n1. Activate the environment:")
if os.name == 'nt':
    print("   .\\venv\\Scripts\\activate")
else:
    print("   source venv/bin/activate")
print("\n2. Create your admin account:")
print("   python manage.py createsuperuser")
print("\n3. Start the server:")
print("   python manage.py runserver")
print("\nThen go to http://127.0.0.1:8000 in your browser.")