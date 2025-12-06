import os
import json
import base64
import time
import re
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from google.cloud import firestore

app = FastAPI(title="Data Processing Worker")

db = firestore.Client()

def simulate_heavy_processing(text):
    char_count = len(text)
    sleep_time = char_count * 0.05
    print(f"Processing {char_count} characters, sleeping for {sleep_time}s")
    time.sleep(sleep_time)
    
    # Redact phone numbers (various formats)
    # Matches: 555-1234, 555-123-4567, 5551234567, (555) 123-4567
    modified_text = re.sub(r'\b\d{3}[-.]?\d{4}\b', '[REDACTED]', text)
    modified_text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED]', modified_text)
    modified_text = re.sub(r'\(\d{3}\)\s*\d{3}[-.]?\d{4}', '[REDACTED]', modified_text)
    
    # Redact emails
    modified_text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', modified_text)
    return modified_text

def store_to_firestore(tenant_id, log_id, data):
    doc_ref = db.collection("tenants").document(tenant_id).collection("processed_logs").document(log_id)
    doc_ref.set(data)
    print(f"Stored document: tenants/{tenant_id}/processed_logs/{log_id}")

@app.post("/process")
async def process_message(request: Request):
    try:
        envelope = await request.json()
        
        if "message" not in envelope:
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")
        
        pubsub_message = envelope["message"]
        
        if "data" not in pubsub_message:
            raise HTTPException(status_code=400, detail="No data in Pub/Sub message")
        
        message_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        message = json.loads(message_data)
        
        print(f"Received message for tenant: {message.get('tenant_id')}, log_id: {message.get('log_id')}")
        
        tenant_id = message["tenant_id"]
        log_id = message["log_id"]
        original_text = message["text"]
        source_type = message.get("source_type", "unknown")
        received_at = message.get("received_at")
        
        modified_text = simulate_heavy_processing(original_text)
        
        processed_document = {
            "source": f"{source_type}_upload",
            "original_text": original_text,
            "modified_data": modified_text,
            "char_count": len(original_text),
            "processing_time_seconds": len(original_text) * 0.05,
            "received_at": received_at,
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "status": "completed"
        }
        
        store_to_firestore(tenant_id, log_id, processed_document)
        
        return {"status": "processed", "log_id": log_id}
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON in message")
    
    except KeyError as e:
        print(f"Missing required field: {e}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    
    except Exception as e:
        print(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Processing failed, will retry")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "worker"}

