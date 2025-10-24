from django.urls import path
from .views import (
    RegisterView, LoginView, PaymentKeyView,
    TransactionCreateView, TransactionListView, TransactionDetailView,
    RefundCreateView, RefundDetailView,
    WebhookListCreateView, WebhookDeleteView,
)

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    
    # Payment Keys
    path('payments/payment_key/', PaymentKeyView.as_view(), name='payment_key'),
    
    # Transactions (NO trailing slash for /pay endpoint as per requirements)
    path('transactions/pay', TransactionCreateView.as_view(), name='transaction_create'),
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('transactions/<int:id>/', TransactionDetailView.as_view(), name='transaction_detail'),
    
    # Refunds
    path('refunds/', RefundCreateView.as_view(), name='refund_create'),
    path('refunds/<int:id>/', RefundDetailView.as_view(), name='refund_detail'),
    
    # Webhooks - Fixed: separate create from list
    path('webhooks/', WebhookListCreateView.as_view(), name='webhook_list_create'),
    path('webhooks/<int:id>/', WebhookDeleteView.as_view(), name='webhook_delete'),
]
