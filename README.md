# Payment API

A payment processing API built with Django REST Framework, featuring async transaction processing, refunds, webhooks, and comprehensive testing.

## Features

✅ Async transaction processing (Celery)    
✅ Full refund support with validation  
✅ Webhook notifications with retry logic   
✅ Payment key authentication   
✅ Idempotency support  
✅ JWT + Token authentication   
✅ Redis caching with pagination    
✅ Comprehensive error logging  
✅ Query optimizations   
✅ 10+ test cases   

## Quick Start

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)

### Setup

1. **Clone and enter directory:**
```bash
git clone https://github.com/hasan00gad148/payment-api
cd payment-api
```

2. **Create .env file:**
```bash
cp .env.example .env
# Edit .env and set SECRET_KEY to a random string
```

3. **Start services:**
```bash
docker-compose up --build -d
```

4. **Run migrations:**
```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

5. **Create superuser (optional):**
```bash
docker-compose exec web python manage.py createsuperuser
```

6. **Run tests:**
```bash
docker-compose exec web python manage.py test
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - Register merchant
- `POST /api/auth/login/` - Login (get Token)
- `POST /api/auth/token/` - Get JWT token pair
- `POST /api/auth/token/refresh/` - Refresh JWT

### Payment Keys
- `POST /api/payments/payment_key/` - Generate payment key

### Transactions
- `POST /api/transactions/pay` - Create transaction (requires payment_key)
- `GET /api/transactions/` - List transactions (paginated)
- `GET /api/transactions/{id}/` - Get transaction details

### Refunds
- `POST /api/refunds/` - Create refund
- `GET /api/refunds/{id}/` - Get refund details

### Webhooks
- `POST /api/webhooks/` - Register webhook
- `GET /api/webhooks/` - List webhooks
- `DELETE /api/webhooks/{id}/` - Delete webhook

## Usage Examples

### 1. Register Merchant
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "merchant@example.com", "password": "securepass123"}'
```

### 2. Generate Payment Key
```bash
curl -X POST http://localhost:8000/api/payments/payment_key/ \
  -H "Authorization: Token YOUR_API_KEY"
```

### 3. Create Transaction
```bash
curl -X POST http://localhost:8000/api/transactions/pay \
  -H "Authorization: Token YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "payment_key": "pk_YOUR_PAYMENT_KEY",
    "amount": "100.00",
    "currency": "USD",
    "description": "Order #123"
  }'
```

### 4. Create Refund
```bash
curl -X POST http://localhost:8000/api/refunds/ \
  -H "Authorization: Token YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction": 1,
    "amount": "50.00",
    "reason": "Customer request"
  }'
```

## Development

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f worker
```

### Run Tests
```bash
docker-compose exec web python manage.py test
```

### Access Django Shell
```bash
docker-compose exec web python manage.py shell
```

### Access Admin Panel
1. Create superuser: `docker-compose exec web python manage.py createsuperuser`
2. Visit: http://localhost:8000/admin/

## Architecture

- **Web Container**: Django REST API (port 8000)
- **Worker Container**: Celery background tasks
- **PostgreSQL**: Database (port 5432)
- **Redis**: Cache + task queue (port 6379)


## Testing

```bash
docker-compose exec web python manage.py test
```

Expected output: 14 tests passed

## Troubleshooting

### Services won't start
```bash
docker-compose down
docker-compose up --build
```

### Database errors
```bash
docker-compose exec web python manage.py migrate --run-syncdb
```

### Clear everything and restart
```bash
docker-compose down -v
docker-compose up --build
```
