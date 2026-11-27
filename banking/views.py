import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.models import User
from django.db.models import Sum
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from .models import Account, Transaction, Beneficiary, WithdrawalRequest, AdminPaymentSettings, AdminInstruction, UserProfile, SupportMessage

def home(request):
    if request.user.is_authenticated: 
        return redirect('dashboard')
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        middle_name = request.POST.get('middle_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = email 
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        country = request.POST.get('country')
        state = request.POST.get('state')
        address = request.POST.get('address')
        dob = request.POST.get('dob')
        currency = request.POST.get('currency')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Email is already registered.")
            return redirect('register')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        UserProfile.objects.create(
            user=user, 
            phone_number=phone, 
            middle_name=middle_name, 
            last_name=last_name, 
            country=country, 
            state_origin=state, 
            address=address, 
            dob=dob
        )
        
        Account.objects.create(user=user, currency=currency)
        
        messages.success(request, "Account created successfully! Please log in.")
        return redirect('login')
    return render(request, 'register.html')

@login_required(login_url='/')
@never_cache
def dashboard(request):
    if 'has_unread_notifications' not in request.session:
        request.session['has_unread_notifications'] = True
        
    account, created = Account.objects.get_or_create(user=request.user)
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    admin_instruction = AdminInstruction.objects.filter(user=request.user).first()
    pending_withdrawal = WithdrawalRequest.objects.filter(user=request.user, status='Requires Code').last()
    recent_transactions = Transaction.objects.filter(account=account)[:4]
    
    context = {
        'account': account, 
        'profile': profile, 
        'admin_instruction': admin_instruction, 
        'pending_withdrawal': pending_withdrawal,
        'recent_transactions': recent_transactions
    }
    return render(request, 'dashboard.html', context)

@login_required
def verify_withdrawal(request, request_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=request_id, user=request.user)
    if request.method == 'POST':
        code = request.POST.get('imt_code')
        if code == withdrawal.required_code:
            withdrawal.status = 'Processing'
            withdrawal.save()
            messages.success(request, "Code verified. Awaiting final approval.")
            AdminInstruction.objects.filter(user=request.user).delete() 
        else:
            messages.error(request, "Invalid IMT Code. Please check with support.")
    return redirect('dashboard')

@login_required
def withdraw_page(request):
    account = Account.objects.get(user=request.user)
    admin_instruction = AdminInstruction.objects.filter(user=request.user).first()
    
    if request.method == 'POST':
        if admin_instruction and request.POST.get('imt_code') != admin_instruction.required_code:
            return render(request, 'withdraw.html', {
                'account': account, 
                'admin_instruction': admin_instruction, 
                'error': 'Invalid IMT Code.', 
                'form_data': request.POST
            })
            
        try:
            amount_str = request.POST.get('amount', '0').replace(',', '')
            amount = Decimal(amount_str)
        except:
            return render(request, 'withdraw.html', {
                'account': account, 
                'admin_instruction': admin_instruction, 
                'error': 'Invalid amount format.', 
                'form_data': request.POST
            })
            
        WithdrawalRequest.objects.create(
            user=request.user, 
            amount=amount, 
            bank_name=request.POST.get('bank_name'), 
            account_name=request.POST.get('account_name'), 
            account_number=request.POST.get('account_number'), 
            country=request.POST.get('country'), 
            status='Pending'
        )
        
        Transaction.objects.create(
            account=account, 
            transaction_type="Withdrawal", 
            amount=-amount, 
            beneficiary_name=request.POST.get('account_name'), 
            status="Pending"
        )
        
        messages.success(request, "Withdrawal request submitted successfully.")
        return redirect('dashboard')
        
    return render(request, 'withdraw.html', {'account': account, 'admin_instruction': admin_instruction})

@login_required
def transfer(request):
    account = Account.objects.get(user=request.user)
    admin_instruction = AdminInstruction.objects.filter(user=request.user).first()
    
    if request.method == 'POST':
        if admin_instruction and request.POST.get('imt_code') != admin_instruction.required_code:
            return render(request, 'transfer.html', {
                'account': account, 
                'admin_instruction': admin_instruction, 
                'error': 'Invalid IMT Code.', 
                'form_data': request.POST
            })
            
        try:
            amount = Decimal(request.POST.get('amount'))
            if amount > 0 and account.balance >= amount:
                account.balance -= amount
                account.total_expense += amount
                account.save()
                Transaction.objects.create(
                    account=account, 
                    transaction_type="Wire Transfer", 
                    amount=-amount, 
                    beneficiary_name=request.POST.get('name'), 
                    status="Pending"
                )
                request.session['has_unread_notifications'] = True
        except Exception as e: 
            print(e)
            
        return redirect('dashboard')
        
    return render(request, 'transfer.html', {'account': account, 'admin_instruction': admin_instruction})

@login_required
def deposit(request):
    payment_settings = AdminPaymentSettings.objects.first()
    if request.method == 'POST':
        account = Account.objects.get(user=request.user)
        amount = Decimal(request.POST.get('amount'))
        if amount > 0:
            account.balance += amount
            account.total_income += amount
            account.save()
            Transaction.objects.create(account=account, transaction_type="Deposit", amount=amount, status="Completed")
            request.session['has_unread_notifications'] = True
        return redirect('dashboard')
    return render(request, 'deposit.html', {'payment_settings': payment_settings})

@login_required
def history(request):
    return render(request, 'history.html', {'transactions': Transaction.objects.filter(account__user=request.user)})

@login_required
def universal_feature(request, feature_name):
    return render(request, 'feature.html', {'feature_name': feature_name, 'account': Account.objects.get(user=request.user)})

@login_required
def notifications(request):
    request.session['has_unread_notifications'] = False
    return render(request, 'notifications.html', {'transactions': Transaction.objects.filter(account__user=request.user)[:5]})

@login_required
def update_profile(request):
    if request.method == 'POST':
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        if 'profile_picture' in request.FILES: 
            profile.profile_picture = request.FILES['profile_picture']
        profile.phone_number = request.POST.get('phone_number')
        profile.save()
    return redirect('dashboard')

@login_required
def manage_account(request):
    return render(request, 'manage_account.html', {'account': Account.objects.get(user=request.user), 'profile': UserProfile.objects.get_or_create(user=request.user)[0]})

@login_required
def security_settings(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated!')
            return redirect('security_settings')
    else: 
        form = PasswordChangeForm(request.user)
    return render(request, 'security_settings.html', {'form': form})

def custom_logout(request):
    logout(request)
    return redirect('login') 

def public_page(request, page_name):
    content = {
        'About Us': """
            <p>ApexVault was founded on a singular vision: to dismantle the barriers of legacy banking and provide a frictionless, borderless financial infrastructure for the digital age.</p>
            <p>We are not just a digital bank; we are a technology company obsessed with financial security. By combining military-grade encryption with intuitive design, we empower individuals and corporations to move wealth globally with absolute confidence.</p>
            <p>Our platform is built on three pillars: <strong>Speed</strong>, <strong>Security</strong>, and <strong>Scalability</strong>. Whether you are sending a local transfer or managing institutional liquidity, ApexVault ensures your capital is always protected, transparent, and accessible.</p>
        """,
        'Careers': """
            <p>ApexVault is built by a collective of visionary engineers, security experts, and financial architects who believe the future of money has no borders.</p>
            <p>We are a remote-first, highly collaborative team dedicated to solving complex problems. We look for individuals who are relentlessly curious, deeply ethical, and passionate about building the next generation of financial infrastructure.</p>
            <p><strong>Current Openings:</strong><br>We are always looking for top-tier talent in Backend Engineering, Cybersecurity, and Compliance. Send your resume to <strong>careers@apexvault.com</strong>.</p>
        """,
        'Press': """
            <p>Welcome to the ApexVault Media Center. Here, you can find our latest announcements, brand guidelines, and executive leadership profiles.</p>
            <p>We are redefining how the world views digital wealth. Our recent milestones include processing over $5B in secure transactions and expanding our infrastructure to support over 150 countries.</p>
            <p><strong>Media Inquiries:</strong><br>For interviews, press releases, or brand assets, please contact our communications team at <strong>press@apexvault.com</strong>.</p>
        """,
        'Contact': """
            <p>Our global support team is available 24/7 to assist you with your financial needs. Whether you have a question about a transfer, need help with identity verification, or require technical support, we are here for you.</p>
            <p><strong>Customer Support:</strong> support@apexvault.com<br>
            <strong>Institutional & Corporate:</strong> institutional@apexvault.com<br>
            <strong>Compliance & Legal:</strong> compliance@apexvault.com</p>
            <p><em>ApexVault operates as a simulated online banking platform for educational and demonstration purposes.</em></p>
        """,
        'Privacy Policy': """
            <p>At ApexVault, your privacy is our paramount concern. This policy outlines how we collect, protect, and utilize your data.</p>
            <p><strong>Data Collection:</strong> We only collect information strictly necessary to provide you with a secure banking experience, including identity verification (KYC) data and transaction history.</p>
            <p><strong>Data Protection:</strong> All data is encrypted using 256-bit AES encryption in transit and at rest. We operate a zero-knowledge architecture where your credentials are never exposed to our servers.</p>
            <p><strong>Third-Party Sharing:</strong> We do not sell your data. We only share information with regulatory bodies as required by global financial law or with trusted partners essential to processing your transactions securely.</p>
        """,
        'Terms of Service': """
            <p>By accessing and using ApexVault, you agree to comply with our Terms of Service.</p>
            <p><strong>Account Responsibility:</strong> You are responsible for maintaining the confidentiality of your login credentials and for all activities that occur under your account.</p>
            <p><strong>Prohibited Activities:</strong> ApexVault strictly prohibits the use of our platform for money laundering, terrorist financing, fraud, or any other illegal activity. We reserve the right to freeze any account suspected of violating these terms.</p>
            <p><strong>Simulated Environment:</strong> This platform is currently operating as a simulated educational environment. ApexVault is not a real-world bank, and funds deposited here are not FDIC insured and hold no real-world value.</p>
        """,
        'Security': """
            <p>Security is not a feature at ApexVault; it is the foundation of our architecture.</p>
            <p>We utilize <strong>Dynamic IMT Verification Codes</strong> for high-value transfers, ensuring that only you can authorize outbound funds. Our systems are monitored 24/7 by advanced AI threat detection algorithms.</p>
            <p>Your assets are safeguarded in segregated accounts with top-tier banking institutions. We employ continuous biometric monitoring and TLS 1.3 protocols to guarantee that your wealth remains impenetrable to external threats.</p>
        """,
        'Compliance': """
            <p>ApexVault is fully committed to maintaining the highest standards of financial compliance and regulatory adherence.</p>
            <p>We operate in strict compliance with international banking standards, including <strong>KYC (Know Your Customer)</strong> and <strong>AML (Anti-Money Laundering)</strong> directives. Every account is subject to rigorous identity verification prior to activation.</p>
            <p>Our compliance team works continuously to ensure that ApexVault remains a secure, transparent, and legally compliant infrastructure for our global user base.</p>
        """
    }
    text = content.get(page_name, '<p>Updating soon.</p>')
    return render(request, 'public_page.html', {'title': page_name, 'text': text})

@login_required
def api_send_chat(request):
    if request.method == 'POST':
        msg = request.POST.get('message')
        image = request.FILES.get('image')
        if msg or image: 
            SupportMessage.objects.create(user=request.user, message=msg, image=image, is_admin_reply=False)
    return JsonResponse({'status': 'ok'})

@login_required
def api_get_chat(request):
    msgs = SupportMessage.objects.filter(user=request.user).order_by('timestamp')
    data = []
    
    for m in msgs:
        data.append({
            'message': m.message, 
            'image_url': m.image.url if m.image else None, 
            'is_admin': m.is_admin_reply, 
            'time': m.timestamp.strftime('%H:%M')
        })
        
    return JsonResponse({'messages': data})
def create_superuser_view(request):
    from django.contrib.auth.models import User
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "Admin123!")
        return "✅ Admin created! Go to /admin/ — Username: admin | Password: Admin123!"
    return "User already exists — just go to /admin/ and log in!"