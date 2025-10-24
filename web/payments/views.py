from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db import transaction as db_transaction
from decimal import Decimal
from .models import Merchant, PaymentKey, Transaction, Refund, Webhook,IdempotencyKey
from .serializers import (
    RegisterSerializer, PaymentKeySerializer,
    TransactionListSerializer, TransactionDetailSerializer,
    RefundSerializer, WebhookSerializer
)
from .tasks import process_transaction
import secrets
import logging

logger = logging.getLogger(__name__)

def standard_response(success, data=None, error=None, status_code=200):
    """Helper function to return standardized API responses"""
    return Response({
        'success': success,
        'data': data,
        'error': error
    }, status=status_code)

class RegisterView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            merchant = serializer.save()
            token, _ = Token.objects.get_or_create(user=merchant.user)
            return standard_response(True, {'api_key': token.key}, None, status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            return standard_response(False, None, str(e), status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            
            if not email or not password:
                return standard_response(False, None, 'Email and password are required', status.HTTP_400_BAD_REQUEST)
            
            user = authenticate(username=email, password=password)
            if not user:
                logger.warning(f"Failed login attempt for email: {email}")
                return standard_response(False, None, 'Invalid credentials', status.HTTP_400_BAD_REQUEST)
            
            token, _ = Token.objects.get_or_create(user=user)
            logger.info(f"User logged in: {email}")
            return standard_response(True, {'api_key': token.key}, None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Internal server error', status.HTTP_500_INTERNAL_SERVER_ERROR)

class PaymentKeyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            merchant = get_object_or_404(Merchant, user=request.user)
            key = 'pk_' + secrets.token_urlsafe(32)
            pk = PaymentKey.objects.create(merchant=merchant, key=key, is_active=True)
            logger.info(f"Payment key created for merchant {merchant.id}")
            return standard_response(True, PaymentKeySerializer(pk).data, None, status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating payment key: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Failed to create payment key', status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransactionCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            idempotency_key = request.headers.get('Idempotency-Key')
    
            if idempotency_key:
                existing = IdempotencyKey.objects.filter(
                    key=idempotency_key, 
                ).first()
                
                if existing and existing.response_body:
                    return Response(existing.response_body, status=existing.response_status)

            merchant = get_object_or_404(Merchant, user=request.user)
            serializer = TransactionDetailSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            
            # Validate that payment key belongs to the merchant
            payment_key = serializer.context.get('payment_key')
            if payment_key.merchant != merchant:
                logger.warning(f"Payment key mismatch for merchant {merchant.id}")
                return standard_response(False, None, 'Payment key does not belong to this merchant', status.HTTP_403_FORBIDDEN)
            
            with db_transaction.atomic():
                tx = Transaction.objects.create(
                    merchant=merchant,
                    amount=serializer.validated_data['amount'],
                    currency=serializer.validated_data['currency'],
                    description=serializer.validated_data.get('description', ''),
                    status='pending'
                )
                logger.info(f"Transaction {tx.id} created for merchant {merchant.id}")

            # Process transaction asynchronously
            process_transaction.delay(tx.id)
            
            # Invalidate cache
            cache.delete_pattern(f"merchant:{merchant.id}:transactions:*")
            
            res = standard_response(True, TransactionDetailSerializer(tx).data, None, status.HTTP_201_CREATED)
            if idempotency_key:
                IdempotencyKey.objects.create(
                    key=idempotency_key,
                    method='POST',
                    path=request.path,
                    response_status=201,
                    response_body={'success': True, 'data': TransactionDetailSerializer(tx).data, 'error': None}
                )
            return res
        except Exception as e:
            logger.error(f"Error creating transaction: {str(e)}", exc_info=True)
            return standard_response(False, None, str(e), status.HTTP_400_BAD_REQUEST)

class TransactionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionListSerializer
    filterset_fields = ['currency', 'status']

    def get_queryset(self):
        merchant = get_object_or_404(Merchant, user=self.request.user)
        qs = Transaction.objects.filter(merchant=merchant).select_related('merchant').prefetch_related('refund').order_by('-created_at')
        return qs

    def list(self, request, *args, **kwargs):
        try:
            merchant = get_object_or_404(Merchant, user=request.user)
            page = request.query_params.get('page', '1')
            
            # Build cache key from query params
            cache_params = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
            cache_key = f"merchant:{merchant.id}:transactions:page:{page}:{cache_params}"
            
            # Check cache
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Returning cached transaction list for merchant {merchant.id}")
                return standard_response(True, cached, None, status.HTTP_200_OK)
            
            # Get paginated response
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)
            
            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                paginated_data = {
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                    'results': serializer.data
                }
                
                # Cache the result
                cache.set(cache_key, paginated_data, timeout=30)
                return standard_response(True, paginated_data, None, status.HTTP_200_OK)
            
            serializer = self.get_serializer(queryset, many=True)
            return standard_response(True, serializer.data, None, status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Failed to retrieve transactions', status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransactionDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        merchant = get_object_or_404(Merchant, user=self.request.user)
        return Transaction.objects.filter(merchant=merchant).select_related('merchant').prefetch_related('refund')

    def retrieve(self, request, *args, **kwargs):
        try:
            pk = kwargs.get('id')
            cache_key = f"transaction:{pk}"
            
            # Check cache
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Returning cached transaction {pk}")
                return standard_response(True, cached, None, status.HTTP_200_OK)
            
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            # Cache the result
            cache.set(cache_key, serializer.data, timeout=30)
            return standard_response(True, serializer.data, None, status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving transaction: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Transaction not found', status.HTTP_404_NOT_FOUND)

class RefundCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            merchant = get_object_or_404(Merchant, user=request.user)
            serializer = RefundSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Get transaction and validate ownership
            tx = get_object_or_404(Transaction, id=serializer.validated_data['transaction'].id, merchant=merchant)
            
            # Validate transaction status
            if tx.status != 'succeeded':
                logger.warning(f"Refund attempt on non-succeeded transaction {tx.id}")
                return standard_response(False, None, 'Only succeeded transactions can be refunded', status.HTTP_400_BAD_REQUEST)
            
            # Check if already refunded
            if hasattr(tx, 'refund'):
                logger.warning(f"Refund attempt on already refunded transaction {tx.id}")
                return standard_response(False, None, 'Transaction already refunded', status.HTTP_400_BAD_REQUEST)
            
            # Validate refund amount
            refund_amount = serializer.validated_data['amount']
            if refund_amount > tx.amount:
                logger.warning(f"Refund amount {refund_amount} exceeds transaction amount {tx.amount} for transaction {tx.id}")
                return standard_response(False, None, f'Refund amount cannot exceed transaction amount of {tx.amount}', status.HTTP_400_BAD_REQUEST)
            
            # Create refund
            with db_transaction.atomic():
                refund = Refund.objects.create(
                    transaction=tx,
                    amount=refund_amount,
                    reason=serializer.validated_data.get('reason', ''),
                    status='succeeded'
                )
                logger.info(f"Refund {refund.id} created for transaction {tx.id}")
            
            # Invalidate cache
            cache.delete(f"transaction:{tx.id}")
            cache.delete_pattern(f"merchant:{merchant.id}:transactions:*")
            
            return standard_response(True, RefundSerializer(refund).data, None, status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}", exc_info=True)
            return standard_response(False, None, str(e), status.HTTP_400_BAD_REQUEST)

class RefundDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RefundSerializer
    lookup_field = 'id'

    def get_queryset(self):
        merchant = get_object_or_404(Merchant, user=self.request.user)
        return Refund.objects.filter(transaction__merchant=merchant).select_related('transaction')

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return standard_response(True, serializer.data, None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error retrieving refund: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Refund not found', status.HTTP_404_NOT_FOUND)

class WebhookListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List webhooks"""
        try:
            merchant = get_object_or_404(Merchant, user=request.user)
            webhooks = Webhook.objects.filter(merchant=merchant)
            serializer = WebhookSerializer(webhooks, many=True)
            return standard_response(True, serializer.data, None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error listing webhooks: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Failed to retrieve webhooks', status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Create webhook"""
        try:
            merchant = get_object_or_404(Merchant, user=request.user)
            serializer = WebhookSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            wb = Webhook.objects.create(
                merchant=merchant,
                url=serializer.validated_data['url'],
                secret=secrets.token_urlsafe(16)
            )
            logger.info(f"Webhook {wb.id} created for merchant {merchant.id}")
            
            return standard_response(True, WebhookSerializer(wb).data, None, status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating webhook: {str(e)}", exc_info=True)
            return standard_response(False, None, str(e), status.HTTP_400_BAD_REQUEST)

class WebhookDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WebhookSerializer
    lookup_field = 'id'

    def get_queryset(self):
        merchant = get_object_or_404(Merchant, user=self.request.user)
        return Webhook.objects.filter(merchant=merchant)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            webhook_id = instance.id
            self.perform_destroy(instance)
            logger.info(f"Webhook {webhook_id} deleted")
            return standard_response(True, {'message': 'Webhook deleted successfully'}, None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error deleting webhook: {str(e)}", exc_info=True)
            return standard_response(False, None, 'Webhook not found', status.HTTP_404_NOT_FOUND)
