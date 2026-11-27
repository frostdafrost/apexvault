from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Account, UserProfile, Transaction, WithdrawalRequest, Beneficiary, AuditLog, AdminPaymentSettings, AdminInstruction, SupportMessage

# ... (keep whatever is already in your admin.py) ...

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'kyc_status', 'id_type')
    list_filter = ('kyc_status', 'id_type')
    search_fields = ('user__username', 'user__email')