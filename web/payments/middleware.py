import json
import logging
from django.db import transaction
from rest_framework.response import Response
from .models import IdempotencyKey

logger = logging.getLogger(__name__)

class IdempotencyMiddleware:
    """Store and return responses for requests with an Idempotency-Key header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.headers.get('Idempotency-Key')
        flag_store_response = False

        if key and request.method in ('POST', 'PUT'):
            try:
                with transaction.atomic():
                    existing = IdempotencyKey.objects.select_for_update().filter(key=key).first()
                    if existing and existing.response_body is not None:
                        logger.info(f"Returning cached response for idempotency key: {key[:20]}...")
                        # existing.response_body is stored as JSON string, decode it
                        try:
                            data = json.loads(existing.response_body)
                        except Exception:
                            data = existing.response_body
                        return Response(data=data, status=existing.response_status)
                    flag_store_response = True
            except Exception as e:
                logger.error(f"Error checking idempotency key: {str(e)}")

        # Call the view / next middleware
        response = self.get_response(request)

        # Store response for future idempotent requests
        if flag_store_response:
            body = None
            try:
                # DRF Response: render first
                response = response.render()

                # Use .data if available
                if hasattr(response, 'data'):
                    body = json.dumps(response.data)
                else:
                    body = response.content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not extract response body: {str(e)}")
                body = json.dumps({"message": "Failed to capture response"})

            # Store in DB
            try:
                with transaction.atomic():
                    IdempotencyKey.objects.update_or_create(
                        key=key,
                        defaults={
                            'method': request.method,
                            'path': request.path,
                            'response_status': response.status_code,
                            'response_body': body,
                        }
                    )
                    logger.info(f"Stored idempotency key: {key[:20]}...")
            except Exception as e:
                logger.error(f"Error storing idempotency key: {str(e)}")

        return response
