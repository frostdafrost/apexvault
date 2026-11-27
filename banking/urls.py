from django.urls import path
from . import views, admin_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('logout/', views.custom_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('transfer/', views.transfer, name='transfer'),
    path('deposit/', views.deposit, name='deposit'),
    path('history/', views.history, name='history'),
    path('manage-account/', views.manage_account, name='manage_account'),
    path('security-settings/', views.security_settings, name='security_settings'),
    path('notifications/', views.notifications, name='notifications'),
    path('feature/<str:feature_name>/', views.universal_feature, name='universal_feature'),
    path('page/<str:page_name>/', views.public_page, name='public_page'),
    path('withdraw/', views.withdraw_page, name='withdraw_page'),
    path('verify-withdrawal/<int:request_id>/', views.verify_withdrawal, name='verify_withdrawal'),
    path('api/chat/send/', views.api_send_chat, name='api_send_chat'),
    path('api/chat/get/', views.api_get_chat, name='api_get_chat'),
    path('control-panel/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('control-panel/withdrawal/<int:request_id>/', admin_views.manage_withdrawal, name='manage_withdrawal'),
    path('control-panel/transaction/<int:tx_id>/', admin_views.manage_transaction, name='manage_transaction'),
    path('control-panel/user/<int:user_id>/balance/', admin_views.edit_user_balance, name='edit_user_balance'),
    path('control-panel/user/<int:user_id>/freeze/', admin_views.toggle_freeze_account, name='toggle_freeze_account'),
    path('control-panel/chats/', admin_views.admin_chat_list, name='admin_chat_list'),
    path('control-panel/chats/<int:user_id>/', admin_views.admin_chat_detail, name='admin_chat_detail'),
    path('control-panel/message/<int:msg_id>/delete/', admin_views.admin_delete_message, name='admin_delete_message'),
    path('control-panel/message/<int:msg_id>/edit/', admin_views.admin_edit_message, name='admin_edit_message'),
    # --- NEW API PATH ---
    path('control-panel/chats/<int:user_id>/api/', admin_views.admin_api_get_chat, name='admin_api_get_chat'),
]