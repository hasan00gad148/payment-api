from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Merchant, PaymentKey, Transaction, Refund, Webhook
import logging

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'], 
            email=validated_data['email'], 
            password=validated_data['password']
        )
        merchant = Merchant.objects.create(user=user)
        logger.info(f"New merchant registered: {merchant.user.email}")
        return merchant

class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['id', 'transaction', 'amount', 'reason', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than zero")
        return value

class TransactionListSerializer(serializers.ModelSerializer):
    refund = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'currency', 'status', 'created_at', 'refund']

    def get_refund(self, obj):
        try:
            refund = obj.refund
            return {'id': refund.id, 'amount': str(refund.amount), 'status': refund.status}
        except Refund.DoesNotExist:
            return None

class TransactionDetailSerializer(serializers.ModelSerializer):
    refund = RefundSerializer(read_only=True)
    payment_key = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'currency', 'description', 'status', 'created_at', 'updated_at', 'refund', 'payment_key']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Transaction amount must be greater than zero")
        return value

    def validate_payment_key(self, value):
        try:
            payment_key = PaymentKey.objects.get(key=value, is_active=True)
            self.context['payment_key'] = payment_key
            return value
        except PaymentKey.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive payment key")

class PaymentKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentKey
        fields = ['id', 'key', 'is_active', 'created_at']
        read_only_fields = ['id', 'key', 'created_at']

class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = ['id', 'url', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_url(self, value):
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must start with http:// or https://")
        return value