from django.db import models
from django.contrib.auth.models import User
import random

def generate_account_number():
    return str(random.randint(1000000000, 9999999999))

class Account(models.Model):
    CURRENCY_CHOICES = (
        ('USD', 'US Dollar (USD)'), ('AUD', 'Australian Dollar (AUD)'),
        ('NZD', 'New Zealand Dollar (NZD)'), ('GBP', 'British Pound (GBP)'),
        ('FJD', 'Fijian Dollar (FJD)'), ('INR', 'Indian Rupee (INR)'), ('EUR', 'Euro (EUR)'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    account_number = models.CharField(max_length=12, unique=True, default=generate_account_number)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD') 
    is_frozen = models.BooleanField(default=False)
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.username} - {self.account_number}"

class UserProfile(models.Model):
    KYC_CHOICES = (
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Rejected', 'Rejected'),
    )
    ID_TYPES = (
        ('Passport', 'Passport'),
        ('Drivers License', 'Drivers License'),
        ('National ID', 'National ID'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    state_origin = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    
    # NEW KYC FIELDS
    id_type = models.CharField(max_length=50, choices=ID_TYPES, blank=True, null=True)
    id_front = models.ImageField(upload_to='kyc_docs/', blank=True, null=True)
    id_back = models.ImageField(upload_to='kyc_docs/', blank=True, null=True)
    selfie_verification = models.ImageField(upload_to='kyc_docs/', blank=True, null=True)
    kyc_status = models.CharField(max_length=20, choices=KYC_CHOICES, default='Pending')

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    beneficiary_name = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Pending')
    class Meta: ordering = ['-timestamp']

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (('Pending', 'Pending'), ('Requires Code', 'Requires Code'), ('Processing', 'Processing'), ('Completed', 'Completed'), ('Rejected', 'Rejected'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    country = models.CharField(max_length=50, blank=True, null=True)
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

class AdminPaymentSettings(models.Model):
    bitcoin_address = models.CharField(max_length=255, blank=True, null=True)
    ethereum_address = models.CharField(max_length=255, blank=True, null=True)
    usdt_address = models.CharField(max_length=255, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    swift_code = models.CharField(max_length=20, blank=True, null=True)

class AdminInstruction(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instruction')
    instruction_text = models.TextField(help_text="Message shown to user on transfer")
    required_code = models.CharField(max_length=20, help_text="IMT Code user must enter to proceed")

class SupportMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages')
    message = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    is_admin_reply = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['timestamp']