from django.contrib import admin
from .models import Merchant, PaymentKey, Transaction, Refund, Webhook, IdempotencyKey

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'name', 'user_email']
    search_fields = ['user__email', 'name']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

@admin.register(PaymentKey)
class PaymentKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'key_preview', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['key', 'merchant__user__email']
    
    def key_preview(self, obj):
        return f"{obj.key[:20]}..."
    key_preview.short_description = 'Key'

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['description', 'merchant__user__email']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'transaction', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reason', 'transaction__id']
    readonly_fields = ['created_at']

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'url', 'created_at']
    search_fields = ['url', 'merchant__user__email']
    readonly_fields = ['created_at']

@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'key_preview', 'method', 'path', 'response_status', 'created_at']
    list_filter = ['method', 'response_status', 'created_at']
    search_fields = ['key', 'path']
    readonly_fields = ['created_at']
    
    def key_preview(self, obj):
        return f"{obj.key[:30]}..."
    key_preview.short_description = 'Idempotency Key'
