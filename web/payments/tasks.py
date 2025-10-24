import random
import time
import requests
import logging
from celery import shared_task, Task
from django.db import transaction
from .models import Transaction, Webhook

logger = logging.getLogger(__name__)

class WebhookTask(Task):
    """Custom task class with retry logic for webhooks"""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 2, 'countdown': 3}
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Webhook delivery failed permanently: {exc}", exc_info=einfo)

@shared_task(bind=True)
def process_transaction(self, transaction_id):
    """Process transaction asynchronously with 3-5 second delay"""
    try:
        logger.info(f"Processing transaction {transaction_id}...")
        time.sleep(random.uniform(3, 5))
        
        with transaction.atomic():
            tx = Transaction.objects.select_for_update().get(id=transaction_id)
            # 80% success rate
            tx.status = 'succeeded' if random.random() > 0.2 else 'failed'
            tx.save()
            logger.info(f"Transaction {transaction_id} processed: {tx.status}")
        
        # Send webhooks after transaction is updated
        send_webhooks.delay(tx.id)
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} does not exist")
    except Exception as e:
        logger.error(f"Error processing transaction {transaction_id}: {str(e)}", exc_info=True)
        raise

@shared_task(bind=True, base=WebhookTask)
def deliver_webhook(self, webhook_id, payload):
    """Deliver webhook with automatic retry (2 retries = 3 total attempts)"""
    try:
        wb = Webhook.objects.get(id=webhook_id)
        logger.info(f"Delivering webhook {webhook_id} to {wb.url}")
        
        resp = requests.post(
            wb.url, 
            json=payload, 
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        resp.raise_for_status()
        
        logger.info(f"Webhook {webhook_id} delivered successfully")
        
    except Webhook.DoesNotExist:
        logger.error(f"Webhook {webhook_id} does not exist")
        raise
    except requests.RequestException as e:
        logger.warning(f"Webhook {webhook_id} delivery failed (attempt {self.request.retries + 1}/3): {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error delivering webhook {webhook_id}: {str(e)}", exc_info=True)
        raise

@shared_task
def send_webhooks(transaction_id):
    """Send webhooks to all registered merchant webhooks"""
    try:
        tx = Transaction.objects.select_related('merchant').get(id=transaction_id)
        webhooks = Webhook.objects.filter(merchant=tx.merchant)
        
        if not webhooks.exists():
            logger.info(f"No webhooks registered for transaction {transaction_id}")
            return
        
        payload = {
            'id': tx.id,
            'status': tx.status,
            'amount': str(tx.amount),
            'currency': tx.currency,
            'description': tx.description,
            'created_at': tx.created_at.isoformat(),
            'updated_at': tx.updated_at.isoformat(),
        }
        
        for wb in webhooks:
            deliver_webhook.delay(wb.id, payload)
            
        logger.info(f"Queued {webhooks.count()} webhooks for transaction {transaction_id}")
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} does not exist for webhook delivery")
    except Exception as e:
        logger.error(f"Error sending webhooks for transaction {transaction_id}: {str(e)}", exc_info=True)