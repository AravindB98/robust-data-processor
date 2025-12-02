import os
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from google.cloud import pubsub_v1
from typing import Optional
from concurrent.futures import TimeoutError as FuturesTimeoutError

app = FastAPI(title="Data Ingestion API")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-6d17c522-407f-4550-a42")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "ingestion-topic")
publisher = None


def get_publisher():
    global publisher
    if publisher is None:
        publisher = pubsub_v1.PublisherClient()
    return publisher


def get_topic_path():
    return get_publisher().topic_path(PROJECT_ID, TOPIC_ID)


def normalize_to_internal_format(tenant_id, text, source_type, log_id=None):
    return {
        "tenant_id": tenant_id,
        "log_id": log_id or str(uuid.uuid4()),
        "text": text,
        "source_type": source_type,
        "received_at": datetime.utcnow().isoformat() + "Z"
    }


async def publish_to_pubsub(message):
    topic_path = get_topic_path()
    message_bytes = json.dumps(message).encode("utf-8")
    future = get_publisher().publish(
        topic_path,
        message_bytes,
        tenant_id=message["tenant_id"],
        log_id=message["log_id"]
    )
    try:
        return future.result(timeout=1.0)
    except FuturesTimeoutError:
        return "pending"


@app.post("/ingest", status_code=202)
async def ingest(
    request: Request,
    content_type: str = Header(None, alias="Content-Type"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
):
    try:
        if content_type and "application/json" in content_type:
            body = await request.json()
            if "tenant_id" not in body:
                raise HTTPException(status_code=400, detail="Missing tenant_id")
            if "text" not in body:
                raise HTTPException(status_code=400, detail="Missing text")
            normalized = normalize_to_internal_format(
                body["tenant_id"],
                body["text"],
                "json",
                body.get("log_id")
            )
        elif content_type and "text/plain" in content_type:
            if not x_tenant_id:
                raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")
            text = (await request.body()).decode("utf-8")
            if not text.strip():
                raise HTTPException(status_code=400, detail="Empty text payload")
            normalized = normalize_to_internal_format(x_tenant_id, text, "text")
        else:
            raise HTTPException(status_code=415, detail="Unsupported Content-Type")

        message_id = await publish_to_pubsub(normalized)
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "log_id": normalized["log_id"],
                "tenant_id": normalized["tenant_id"],
                "message_id": str(message_id)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
