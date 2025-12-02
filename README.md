# Robust Data Processor

A scalable, fault-tolerant multi-tenant data ingestion pipeline built on Google Cloud Platform for Memory Machines take-home challenge.

## Live API

**Endpoint:** `https://ingestion-api-321099247148.us-central1.run.app/ingest`

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ JSON / TXT  │────▶│  Cloud Run  │────▶│   Pub/Sub   │────▶│  Cloud Run  │
│  Payloads   │     │    (API)    │     │   (Queue)   │     │  (Worker)   │
└─────────────┘     └──────┬──────┘     └─────────────┘     └──────┬──────┘
                           │                                       │
                           ▼                                       ▼
                    202 Accepted                            ┌─────────────┐
                     (instant)                              │  Firestore  │
                                                            │  tenants/   │
                                                            │   {id}/     │
                                                            │    logs/    │
                                                            └─────────────┘
```

## Features

- **Non-blocking API**: Returns 202 Accepted instantly
- **Multi-tenant isolation**: Data stored at `tenants/{tenant_id}/processed_logs/{log_id}`
- **PII Redaction**: Automatically redacts phone numbers and emails
- **Crash Recovery**: Pub/Sub redelivers unacknowledged messages
- **Scale to Zero**: Serverless architecture with no idle costs

## API Usage

### JSON Payload
```bash
curl -X POST "https://ingestion-api-321099247148.us-central1.run.app/ingest" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "acme_corp", "log_id": "123", "text": "User 555-1234 logged in"}'
```

### Text Payload
```bash
curl -X POST "https://ingestion-api-321099247148.us-central1.run.app/ingest" \
  -H "Content-Type: text/plain" \
  -H "X-Tenant-ID: beta_inc" \
  -d "Server log from user@email.com"
```

### Response
```json
{
  "status": "accepted",
  "log_id": "123",
  "tenant_id": "acme_corp",
  "message_id": "17168465053306822"
}
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| API | Cloud Run + FastAPI |
| Message Broker | Google Pub/Sub |
| Worker | Cloud Run + FastAPI |
| Database | Firestore (NoSQL) |

## Multi-Tenant Isolation

Data is strictly isolated using Firestore subcollections:

```
tenants/
├── acme_corp/
│   └── processed_logs/
│       ├── log-001
│       └── log-002
└── beta_inc/
    └── processed_logs/
        └── log-001
```

## Crash Recovery

The system handles crashes gracefully:

1. API publishes message to Pub/Sub
2. Pub/Sub delivers to Worker via push subscription
3. If Worker crashes, message is NOT acknowledged
4. Pub/Sub automatically redelivers with exponential backoff
5. Worker is idempotent - reprocessing overwrites existing document

## Processing Logic

- Sleep for `0.05s × character_count` (simulates heavy processing)
- Redact phone numbers: `555-1234` → `[REDACTED]`
- Redact emails: `user@email.com` → `[EMAIL_REDACTED]`

## Project Structure

```
robust-data-processor/
├── api/
│   ├── main.py           # FastAPI ingestion endpoint
│   ├── Dockerfile
│   └── requirements.txt
├── worker/
│   ├── main.py           # Pub/Sub message processor
│   ├── Dockerfile
│   └── requirements.txt
└── README.md
```

## Author

**Aravind Balaji**  
Masters in Information Systems  
Northeastern University
www.linkedin.com/in/aravind-balaji-17a7b2115
