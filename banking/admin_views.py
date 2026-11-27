from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from .models import WithdrawalRequest, AuditLog, AdminPaymentSettings, AdminInstruction, SupportMessage, Account, Transaction
from decimal import Decimal

def is_admin(user): return user.is_staff or user.is_superuser

@user_passes_test(is_admin)
def admin_dashboard(request):
    users = User.objects.all().select_related('account')
    withdrawals = WithdrawalRequest.objects.all().order_by('-created_at')
    pending_transfers = Transaction.objects.filter(status='Pending', transaction_type__in=['Wire Transfer', 'Local Transfer', 'Transfer']).order_by('-timestamp')
    audit_logs = AuditLog.objects.all().order_by('-timestamp')[:10]
    settings, created = AdminPaymentSettings.objects.get_or_create(id=1)
    instructions = AdminInstruction.objects.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_payments':
            settings.bitcoin_address = request.POST.get('bitcoin_address')
            settings.ethereum_address = request.POST.get('ethereum_address')
            settings.usdt_address = request.POST.get('usdt_address')
            settings.bank_name = request.POST.get('bank_name')
            settings.account_name = request.POST.get('account_name')
            settings.account_number = request.POST.get('account_number')
            settings.swift_code = request.POST.get('swift_code')
            settings.save()
        elif action == 'add_instruction':
            user_id = request.POST.get('user_id')
            if user_id:
                target_user = User.objects.get(id=user_id)
                instruction, created = AdminInstruction.objects.get_or_create(user=target_user)
                instruction.instruction_text = request.POST.get('instruction_text')
                instruction.required_code = request.POST.get('required_code')
                instruction.save()
        elif action == 'clear_instruction':
            user_id = request.POST.get('user_id')
            if user_id: AdminInstruction.objects.filter(user_id=user_id).delete()
        return redirect('admin_dashboard')

    context = {'users': users, 'withdrawals': withdrawals, 'pending_transfers': pending_transfers, 'audit_logs': audit_logs, 'settings': settings, 'instructions': instructions}
    return render(request, 'admin_dashboard.html', context)

@user_passes_test(is_admin)
def manage_withdrawal(request, request_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=request_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        admin_note = request.POST.get('admin_note')
        req_code = request.POST.get('required_code')
        
        if req_code and admin_note:
            instruction, created = AdminInstruction.objects.get_or_create(user=withdrawal.user)
            instruction.instruction_text = admin_note
            instruction.required_code = req_code
            instruction.save()
        elif new_status == 'Completed' or new_status == 'Rejected':
             AdminInstruction.objects.filter(user=withdrawal.user).delete()

        target_tx = Transaction.objects.filter(account=withdrawal.user.account, transaction_type="Withdrawal", amount=-Decimal(withdrawal.amount)).order_by('-timestamp').first()

        if new_status == 'Completed' and withdrawal.status != 'Completed':
            account = withdrawal.user.account
            amount = Decimal(withdrawal.amount)
            if account.balance >= amount:
                account.balance -= amount
                account.total_expense += amount
                account.save()
                if target_tx:
                    target_tx.status = "Completed"
                    target_tx.save()
                else:
                    Transaction.objects.create(account=account, transaction_type="Withdrawal", amount=-amount, beneficiary_name=withdrawal.account_name, status="Completed")
                messages.success(request, f"Withdrawal completed. ${amount} deducted.")
            else:
                messages.error(request, "Error: User does not have enough balance.")
                return redirect('manage_withdrawal', request_id=request_id)
        elif new_status == 'Rejected' and withdrawal.status != 'Rejected':
            if target_tx:
                target_tx.status = "Rejected"
                target_tx.save()
            messages.info(request, "Withdrawal rejected. History updated.")
        elif withdrawal.status == 'Completed' and new_status != 'Completed':
            account = withdrawal.user.account
            amount = Decimal(withdrawal.amount)
            account.balance += amount
            account.total_expense -= amount
            account.save()
            messages.info(request, "Withdrawal reverted. Funds refunded to user.")

        if target_tx: target_tx.status = new_status; target_tx.save()

        withdrawal.status = new_status
        withdrawal.admin_note = admin_note
        withdrawal.required_code = req_code
        withdrawal.save()
        return redirect('admin_dashboard')
    return render(request, 'admin_manage_withdrawal.html', {'withdrawal': withdrawal})

@user_passes_test(is_admin)
def manage_transaction(request, tx_id):
    tx = get_object_or_404(Transaction, id=tx_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status == 'Rejected' and tx.status == 'Pending':
            account = tx.account
            amount = abs(Decimal(tx.amount))
            account.balance += amount
            account.total_expense -= amount
            account.save()
            messages.info(request, f"Transfer rejected. ${amount} refunded to {tx.account.user.username}.")
        tx.status = new_status
        tx.save()
        return redirect('admin_dashboard')
    return render(request, 'admin_manage_transaction.html', {'tx': tx})

@user_passes_test(is_admin)
def edit_user_balance(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        account = user.account
        old_balance = account.balance
        account.balance = Decimal(request.POST.get('balance'))
        new_currency = request.POST.get('currency')
        if new_currency: account.currency = new_currency
        account.save()
        AuditLog.objects.create(admin=request.user, target_user=user, action=f"Changed balance to ${account.balance} {account.currency}")
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
def admin_chat_list(request):
    users_with_chats = User.objects.filter(support_messages__isnull=False).distinct()
    chats = []
    for u in users_with_chats:
        last_msg = SupportMessage.objects.filter(user=u).last()
        chats.append({'user': u, 'last_msg': last_msg})
    return render(request, 'admin_chat_list.html', {'chats': chats})

@user_passes_test(is_admin)
def admin_chat_detail(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    messages_list = SupportMessage.objects.filter(user=target_user).order_by('timestamp')
    if request.method == 'POST':
        reply = request.POST.get('reply')
        image = request.FILES.get('image')
        if reply or image:
            SupportMessage.objects.create(user=target_user, message=reply, image=image, is_admin_reply=True)
            return redirect('admin_chat_detail', user_id=user_id)
    return render(request, 'admin_chat_detail.html', {'target_user': target_user, 'messages': messages_list})

# --- NEW EDIT/DELETE MESSAGE FUNCTIONS ---
@user_passes_test(is_admin)
def admin_delete_message(request, msg_id):
    msg = get_object_or_404(SupportMessage, id=msg_id)
    user_id = msg.user.id
    msg.delete()
    return redirect('admin_chat_detail', user_id=user_id)

@user_passes_test(is_admin)
def admin_edit_message(request, msg_id):
    if request.method == 'POST':
        msg = get_object_or_404(SupportMessage, id=msg_id)
        new_text = request.POST.get('new_text')
        if new_text is not None:
            msg.message = new_text
            msg.save()
        return redirect('admin_chat_detail', user_id=msg.user.id)
    return redirect('admin_chat_list')

# --- NEW API FOR POLLING ---
@user_passes_test(is_admin)
def admin_api_get_chat(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    msgs = SupportMessage.objects.filter(user=target_user).order_by('timestamp')
    data = []
    for m in msgs:
        data.append({
            'id': m.id,
            'message': m.message,
            'image_url': m.image.url if m.image else None,
            'is_admin': m.is_admin_reply,
            'time': m.timestamp.strftime('%H:%M')
        })
    return JsonResponse({'messages': data})