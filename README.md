# Robust Data Processor

A scalable, fault-tolerant multi-tenant data ingestion pipeline built on Google Cloud Platform.

**Built for:** Memory Machines Backend Engineering Challenge  
**Author:** Aravind Balaji | Northeastern University

---

## Live API

**Endpoint:** `https://ingestion-api-321099247148.us-central1.run.app/ingest`

---

## Architecture
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ROBUST DATA PROCESSOR                                    │
│                                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐                  │
│  │    JSON      │      │              │      │              │                  │
│  │   Payload    │─────▶│              │      │              │                  │
│  │              │      │   Cloud Run  │      │   Pub/Sub    │                  │
│  └──────────────┘      │    (API)     │─────▶│   (Queue)    │                  │
│                        │              │      │              │                  │
│  ┌──────────────┐      │  Normalize   │      │  Decouple &  │                  │
│  │    TXT       │      │  & Publish   │      │    Buffer    │                  │
│  │   Payload    │─────▶│              │      │              │                  │
│  │              │      │              │      │              │                  │
│  └──────────────┘      └──────┬───────┘      └───────┬──────┘                  │
│                               │                      │                          │
│                               ▼                      │                          │
│                        202 Accepted                  │                          │
│                        (instant)                     ▼                          │
│                                              ┌──────────────┐                   │
│                                              │  Cloud Run   │                   │
│                                              │  (Worker)    │                   │
│                                              │              │                   │
│                                              │  Process &   │                   │
│                                              │  Redact PII  │                   │
│                                              └───────┬──────┘                   │
│                                                      │                          │
│                                                      ▼                          │
│                                              ┌──────────────┐                   │
│                                              │  Firestore   │                   │
│                                              │              │                   │
│                                              │  tenants/    │                   │
│                                              │  ├─ acme/    │                   │
│                                              │  ├─ beta/    │                   │
│                                              │  └─ gamma/   │                   │
│                                              └──────────────┘                   │
│                                                                                 │
│                            MULTI-TENANT ISOLATION                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

---


### How TXT and JSON Paths Merge
```
                         ┌─────────────────────────────────────────┐
                         │            INPUT SOURCES                │
                         └─────────────────────────────────────────┘
                                          
    ┌──────────────────────────┐              ┌──────────────────────────┐
    │       JSON PAYLOAD       │              │       TXT PAYLOAD        │
    │                          │              │                          │
    │  Content-Type:           │              │  Content-Type:           │
    │  application/json        │              │  text/plain              │
    │                          │              │                          │
    │  Body:                   │              │  Header:                 │
    │  {                       │              │  X-Tenant-ID: beta_inc   │
    │   "tenant_id": "acme",   │              │                          │
    │   "log_id": "123",       │              │  Body:                   │
    │   "text": "User 555..."  │              │  "Raw log text..."       │
    │  }                       │              │                          │
    └────────────┬─────────────┘              └─────────────┬────────────┘
                 │                                          │
                 │         POST /ingest                     │
                 │                                          │
                 └─────────────────┬────────────────────────┘
                                   │
                                   ▼
                 ┌─────────────────────────────────────────┐
                 │         CLOUD RUN (API SERVICE)         │
                 │                                         │
                 │   ┌─────────────────────────────────┐   │
                 │   │     NORMALIZE TO INTERNAL       │   │
                 │   │          FORMAT                 │   │
                 │   │                                 │   │
                 │   │  Both JSON and TXT become:     │   │
                 │   │  {                             │   │
                 │   │    "tenant_id": "...",         │   │
                 │   │    "log_id": "...",            │   │
                 │   │    "text": "...",              │   │
                 │   │    "source_type": "json|text", │   │
                 │   │    "received_at": "..."        │   │
                 │   │  }                             │   │
                 │   └─────────────────────────────────┘   │
                 │                                         │
                 └──────────────────┬──────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
      ┌─────────────────────────┐    ┌─────────────────────────┐
      │     202 Accepted        │    │    GOOGLE PUB/SUB       │
      │   (instant response)    │    │    ingestion-topic      │
      │                         │    │                         │
      │  Returned to client     │    │  • Buffers messages     │
      │  immediately            │    │  • Guarantees delivery  │
      │                         │    │  • Enables retry        │
      └─────────────────────────┘    └────────────┬────────────┘
                                                  │
                                        Push Subscription
                                                  │
                                                  ▼
                                   ┌─────────────────────────────┐
                                   │  CLOUD RUN (WORKER SERVICE) │
                                   │                             │
                                   │  1. Receive message         │
                                   │  2. Sleep 0.05s per char    │
                                   │  3. Redact phone numbers    │
                                   │  4. Redact emails           │
                                   │  5. Store to Firestore      │
                                   │  6. Acknowledge message     │
                                   │                             │
                                   └──────────────┬──────────────┘
                                                  │
                                                  ▼
                                   ┌─────────────────────────────┐
                                   │         FIRESTORE           │
                                   │    (Multi-Tenant Storage)   │
                                   │                             │
                                   │  tenants/                   │
                                   │  ├── acme_corp/             │
                                   │  │   └── processed_logs/    │
                                   │  │       ├── log-001        │
                                   │  │       └── log-002        │
                                   │  ├── beta_inc/              │
                                   │  │   └── processed_logs/    │
                                   │  │       └── log-001        │
                                   │  └── gamma_ltd/             │
                                   │      └── processed_logs/    │
                                   │          └── log-001        │
                                   │                             │
                                   │   STRICT TENANT ISOLATION   │
                                   └─────────────────────────────┘
```

### Data Flow Summary

| Step | JSON Payload | TXT Payload |
|------|--------------|-------------|
| 1. Input | `Content-Type: application/json` | `Content-Type: text/plain` |
| 2. Tenant ID | From JSON body: `tenant_id` | From header: `X-Tenant-ID` |
| 3. Normalize | ✅ Same internal format | ✅ Same internal format |
| 4. Publish | ✅ Same Pub/Sub topic | ✅ Same Pub/Sub topic |
| 5. Process | ✅ Same worker | ✅ Same worker |
| 6. Store | ✅ Same Firestore structure | ✅ Same Firestore structure |

**Key Point:** Both JSON and TXT payloads merge into a single normalized format at the API layer, then follow the same path through Pub/Sub → Worker → Firestore.

---

## Features

| Feature | Description |
|---------|-------------|
| **Non-blocking API** | Returns 202 Accepted instantly, processes async |
| **Multi-tenant Isolation** | Each tenant's data in separate Firestore subcollection |
| **PII Redaction** | Auto-redacts phone numbers and emails |
| **Crash Recovery** | Pub/Sub redelivers failed messages automatically |
| **Scale to Zero** | Serverless - no cost when idle |
| **High Throughput** | Handles 1000+ requests per minute |

---

## Project Structure
```
robust-data-processor/
├── api/
│   ├── main.py              # FastAPI ingestion endpoint
│   ├── Dockerfile           # Container configuration
│   └── requirements.txt     # Python dependencies
├── worker/
│   ├── main.py              # Pub/Sub message processor
│   ├── Dockerfile           # Container configuration
│   └── requirements.txt     # Python dependencies
├── test_load.py             # Load testing script (1000 RPM)
└── README.md
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Gateway | Cloud Run + FastAPI | Non-blocking request handling |
| Message Broker | Google Pub/Sub | Async processing, guaranteed delivery |
| Worker | Cloud Run + FastAPI | CPU-intensive processing |
| Database | Firestore | Multi-tenant NoSQL storage |

---

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

### Response (202 Accepted)
```json
{
  "status": "accepted",
  "log_id": "123",
  "tenant_id": "acme_corp",
  "message_id": "17168465053306822"
}
```

### Health Check
```bash
curl "https://ingestion-api-321099247148.us-central1.run.app/health"
```

---

## Multi-Tenant Database Structure

Data is strictly isolated using Firestore subcollections:
```
tenants/
├── acme_corp/
│   └── processed_logs/
│       ├── log-001
│       ├── log-002
│       └── log-003
├── beta_inc/
│   └── processed_logs/
│       └── log-001
├── gamma_ltd/
│   └── processed_logs/
│       └── log-001
└── delta_co/
    └── processed_logs/
        └── log-001
```

### Sample Document
```json
{
  "source": "json_upload",
  "original_text": "User 555-1234 logged in from user@email.com",
  "modified_data": "User [REDACTED] logged in from [EMAIL_REDACTED]",
  "char_count": 43,
  "processing_time_seconds": 2.15,
  "received_at": "2025-12-02T21:55:28.056901Z",
  "processed_at": "2025-12-02T21:55:30.899071Z",
  "status": "completed"
}
```

---

## Load Testing

### Run the Load Test (1000 RPM)
```bash
# Install dependency
pip install aiohttp

# Run test
python test_load.py
```

### Expected Output
```
Starting load test: 1000 requests over 60 seconds
Target: https://ingestion-api-321099247148.us-central1.run.app/ingest
--------------------------------------------------
Dispatched 100/1000 requests...
Dispatched 200/1000 requests...
...
==================================================
LOAD TEST RESULTS
==================================================
Total Requests: 1000
Successful (202): 1000 (100.0%)
Failed: 0 (0.0%)
Actual Duration: 61.0s
Actual RPM: 984

Response Times (ms):
  Min: 58
  Max: 7163
  Avg: 597
  P95: 4103

Requests by Tenant:
  acme_corp: 225/225
  beta_inc: 244/244
  gamma_ltd: 258/258
  delta_co: 273/273
```

---

---

## Crash Recovery ("Crash Simulation" Handling)

The system is designed to handle worker crashes gracefully:

### How It Works
```
1. API publishes message to Pub/Sub
2. Pub/Sub delivers message to Worker
3. Worker processes message
4. Worker returns 200 OK → Pub/Sub marks message as "acknowledged"
5. If Worker CRASHES before step 4 → message is NOT acknowledged
6. Pub/Sub automatically RETRIES delivery with exponential backoff
```

### Key Design Decisions

**1. Pub/Sub Acknowledgment Deadline (600 seconds):**
- Worker has 10 minutes to process before Pub/Sub retries
- Allows for long-running processing (0.05s × characters)

**2. Idempotent Worker:**
- Uses `log_id` as Firestore document ID
- Reprocessing same message overwrites existing document
- No duplicate data even if message is delivered multiple times

**3. At-Least-Once Delivery:**
- Pub/Sub guarantees message is delivered at least once
- Combined with idempotent worker = exactly-once processing semantics

### Failure Scenarios

| Scenario | What Happens |
|----------|--------------|
| Worker crashes mid-process | Pub/Sub redelivers after ack deadline |
| Worker returns 500 error | Pub/Sub retries with exponential backoff |
| Firestore unavailable | Worker fails, Pub/Sub retries |
| API crashes | Cloud Run auto-restarts, Pub/Sub buffers messages |
| High traffic spike | Cloud Run auto-scales, Pub/Sub absorbs burst |

### Why This Architecture?

Using Pub/Sub as a message broker between API and Worker means:
- **No data loss**: Messages persist in Pub/Sub until acknowledged
- **Decoupled services**: API doesn't need to know if Worker is running
- **Automatic retries**: No custom retry logic needed
- **Scalability**: Can add more workers without changing API

---

---

## Processing Logic

1. **Receive message** from Pub/Sub
2. **Simulate heavy processing**: Sleep for `0.05s × character_count`
3. **Redact PII**:
   - Phone numbers: `555-1234` → `[REDACTED]`
   - Emails: `user@email.com` → `[EMAIL_REDACTED]`
4. **Store to Firestore** under tenant's subcollection

---

## Author

**Aravind Balaji**  
Masters in Information Systems  
Northeastern University  
aravind.b98@gmail.com
www.linkedin.com/in/aravind-balaji-17a7b2115
