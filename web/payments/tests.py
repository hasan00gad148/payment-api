from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from decimal import Decimal
from .models import Merchant, Transaction, PaymentKey, Refund
import logging

# Disable logging during tests
logging.disable(logging.CRITICAL)

class PaymentAPITestCase(TestCase):
    def setUp(self):
        # Create user and merchant
        self.user = User.objects.create_user(
            username='test@example.com', 
            email='test@example.com', 
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(user=self.user)
        
        # Setup API client
        self.client = APIClient()
        resp = self.client.post('/api/auth/login/', {
            'email': 'test@example.com', 
            'password': 'testpass123'
        }, format='json')
        
        self.token = resp.data['data']['api_key']
        # print("token  ",self.token)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        
        # Create payment key
        resp = self.client.post('/api/payments/payment_key/')
        self.payment_key = resp.data['data']['key']

    def test_register_merchant(self):
        """Test merchant registration"""
        client = APIClient()
        resp = client.post('/api/auth/register/', {
            'email': 'newmerchant@example.com',
            'password': 'newpass123'
        }, format='json')
        
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['success'])
        self.assertIn('api_key', resp.data['data'])

    def test_login(self):
        """Test merchant login"""
        client = APIClient()
        resp = client.post('/api/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        }, format='json')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertIn('api_key', resp.data['data'])

    def test_create_payment_key(self):
        """Test payment key creation"""
        resp = self.client.post('/api/payments/payment_key/')
        
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['success'])
        self.assertIn('key', resp.data['data'])
        self.assertTrue(resp.data['data']['key'].startswith('pk_'))

    def test_create_transaction(self):
        """Test transaction creation with valid payment key"""
        resp = self.client.post('/api/transactions/pay', {
            'payment_key': self.payment_key,
            'amount': '100.00',
            'currency': 'USD',
            'description': 'Test payment'
        }, format='json')
        
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['data']['status'], 'pending')
        self.assertEqual(resp.data['data']['amount'], '100.00')

    def test_create_transaction_invalid_payment_key(self):
        """Test transaction creation with invalid payment key"""
        resp = self.client.post('/api/transactions/pay', {
            'payment_key': 'invalid_key',
            'amount': '100.00',
            'currency': 'USD'
        }, format='json')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])

    def test_create_transaction_negative_amount(self):
        """Test transaction creation with negative amount"""
        resp = self.client.post('/api/transactions/pay', {
            'payment_key': self.payment_key,
            'amount': '-10.00',
            'currency': 'USD'
        }, format='json')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])

    def test_list_transactions(self):
        """Test listing transactions with pagination"""
        # Create a transaction
        Transaction.objects.create(
            merchant=self.merchant,
            amount=Decimal('50.00'),
            currency='USD',
            status='succeeded'
        )
        
        resp = self.client.get('/api/transactions/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertIn('results', resp.data['data'])
        self.assertGreater(len(resp.data['data']['results']), 0)

    def test_refund_succeeded_transaction(self):
        """Test creating refund for succeeded transaction"""
        tx = Transaction.objects.create(
            merchant=self.merchant,
            amount=Decimal('100.00'),
            currency='USD',
            status='succeeded'
        )
        
        resp = self.client.post('/api/refunds/', {
            'transaction': tx.id,
            'amount': '50.00',
            'reason': 'Customer request'
        }, format='json')
        
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['data']['amount'], '50.00')

    def test_refund_pending_transaction(self):
        """Test refund fails for pending transaction"""
        tx = Transaction.objects.create(
            merchant=self.merchant,
            amount=Decimal('100.00'),
            currency='USD',
            status='pending'
        )
        
        resp = self.client.post('/api/refunds/', {
            'transaction': tx.id,
            'amount': '50.00'
        }, format='json')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])

    def test_refund_exceeds_amount(self):
        """Test refund fails when amount exceeds transaction amount"""
        tx = Transaction.objects.create(
            merchant=self.merchant,
            amount=Decimal('100.00'),
            currency='USD',
            status='succeeded'
        )
        
        resp = self.client.post('/api/refunds/', {
            'transaction': tx.id,
            'amount': '150.00'
        }, format='json')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])
        self.assertIn('cannot exceed', resp.data['error'])

    def test_duplicate_refund(self):
        """Test refund fails when transaction already refunded"""
        tx = Transaction.objects.create(
            merchant=self.merchant,
            amount=Decimal('100.00'),
            currency='USD',
            status='succeeded'
        )
        
        # Create first refund
        Refund.objects.create(
            transaction=tx,
            amount=Decimal('50.00'),
            status='succeeded'
        )
        
        # Try to create second refund
        resp = self.client.post('/api/refunds/', {
            'transaction': tx.id,
            'amount': '30.00'
        }, format='json')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])

    def test_webhook_creation(self):
        """Test webhook registration"""
        resp = self.client.post('/api/webhooks/', {
            'url': 'https://example.com/webhook'
        }, format='json')
        
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['data']['url'], 'https://example.com/webhook')

    def test_webhook_list(self):
        """Test listing webhooks"""
        # Create a webhook first
        self.client.post('/api/webhooks/', {
            'url': 'https://example.com/webhook'
        }, format='json')
        
        resp = self.client.get('/api/webhooks/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertIsInstance(resp.data['data'], list)

    def test_idempotency(self):
        """Test idempotency key prevents duplicate transactions"""
        idempotency_key = 'test-idempotency-key-12345'
        
        # First request
        resp1 = self.client.post('/api/transactions/pay', {
            'payment_key': self.payment_key,
            'amount': '100.00',
            'currency': 'USD'
        }, format='json', HTTP_IDEMPOTENCY_KEY=idempotency_key)
        
        self.assertEqual(resp1.status_code, 201)
        
        # Second request with same key (should return cached response)
        resp2 = self.client.post('/api/transactions/pay', {
            'payment_key': self.payment_key,
            'amount': '200.00',  # Different amount
            'currency': 'EUR'      # Different currency
        }, format='json', HTTP_IDEMPOTENCY_KEY=idempotency_key)
        
        # Both should return same response (same transaction ID and amount)
        self.assertEqual(resp1.status_code, resp2.status_code)
        self.assertEqual(resp1.data['data']['id'], resp2.data['data']['id'])
        self.assertEqual(resp1.data['data']['amount'], resp2.data['data']['amount'])
        self.assertEqual(resp1.data['data']['currency'], resp2.data['data']['currency'])
