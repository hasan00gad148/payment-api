from django.db import models
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

class Merchant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.user.email

class PaymentKey(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='payment_keys')
    key = models.CharField(max_length=128, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.key[:20]}... ({'active' if self.is_active else 'inactive'})"

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.id} - {self.status} - {self.amount} {self.currency}"

class Refund(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='refund')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Refund {self.id} for Transaction {self.transaction.id}"

class Webhook(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField()
    secret = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.id} - {self.url}"

class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True, db_index=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['key']),
        ]

    def __str__(self):
        return f"Idempotency {self.key[:20]}..."