import asyncio
import aiohttp
import random
import time

API_URL = "https://ingestion-api-321099247148.us-central1.run.app/ingest"
REQUESTS_PER_MINUTE = 1000
DURATION_SECONDS = 60
TENANTS = ["acme_corp", "beta_inc", "gamma_ltd", "delta_co"]

async def send_request(session, request_id):
    tenant = random.choice(TENANTS)
    
    if random.random() < 0.5:
        # JSON payload
        payload = {
            "tenant_id": tenant,
            "log_id": f"load-{request_id}",
            "text": f"Test message {request_id} from user 555-{random.randint(1000,9999)}"
        }
        headers = {"Content-Type": "application/json"}
        data = None
        json_data = payload
    else:
        # Text payload
        headers = {
            "Content-Type": "text/plain",
            "X-Tenant-ID": tenant
        }
        data = f"Log entry {request_id} from user{random.randint(100,999)}@email.com"
        json_data = None
    
    start = time.time()
    try:
        async with session.post(API_URL, headers=headers, json=json_data, data=data) as resp:
            elapsed = (time.time() - start) * 1000
            status = resp.status
            return {"success": status == 202, "status": status, "time_ms": elapsed, "tenant": tenant}
    except Exception as e:
        return {"success": False, "status": 0, "time_ms": 0, "tenant": tenant, "error": str(e)}

async def main():
    print(f"Starting load test: {REQUESTS_PER_MINUTE} requests over {DURATION_SECONDS} seconds")
    print(f"Target: {API_URL}")
    print("-" * 50)
    
    delay = DURATION_SECONDS / REQUESTS_PER_MINUTE
    results = []
    
    connector = aiohttp.TCPConnector(limit=100)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        start_time = time.time()
        
        for i in range(REQUESTS_PER_MINUTE):
            task = asyncio.create_task(send_request(session, i))
            tasks.append(task)
            
            if (i + 1) % 100 == 0:
                print(f"Dispatched {i + 1}/{REQUESTS_PER_MINUTE} requests...")
            
            await asyncio.sleep(delay)
        
        print("Waiting for all requests to complete...")
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
    
    # Results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print("\n" + "=" * 50)
    print("LOAD TEST RESULTS")
    print("=" * 50)
    print(f"Total Requests: {len(results)}")
    print(f"Successful (202): {len(successful)} ({100*len(successful)/len(results):.1f}%)")
    print(f"Failed: {len(failed)} ({100*len(failed)/len(results):.1f}%)")
    print(f"Actual Duration: {total_time:.1f}s")
    print(f"Actual RPM: {len(results) / (total_time/60):.0f}")
    
    if successful:
        times = [r["time_ms"] for r in successful]
        print(f"\nResponse Times (ms):")
        print(f"  Min: {min(times):.0f}")
        print(f"  Max: {max(times):.0f}")
        print(f"  Avg: {sum(times)/len(times):.0f}")
        times.sort()
        print(f"  P95: {times[int(len(times)*0.95)]:.0f}")
    
    print(f"\nRequests by Tenant:")
    for tenant in TENANTS:
        count = len([r for r in results if r["tenant"] == tenant])
        success = len([r for r in successful if r["tenant"] == tenant])
        print(f"  {tenant}: {success}/{count}")

if __name__ == "__main__":
    asyncio.run(main())