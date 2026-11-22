import sys
import time
import json
import urllib.request
import urllib.error
import concurrent.futures
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
from backend.app.core.config import settings

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", body=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            latency_ms = (time.perf_counter() - start) * 1000.0
            return resp.status, latency_ms, len(content)
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return e.code, latency_ms, 0
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return 500, latency_ms, 0

def benchmark_endpoint(name, path, method="GET", body=None, headers=None, runs=15, pause_sec=0.05):
    latencies = []
    statuses = []
    
    for _ in range(runs):
        st, lat, _ = make_request(path, method, body, headers)
        statuses.append(st)
        latencies.append(lat)
        if pause_sec > 0:
            time.sleep(pause_sec)
        
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean = statistics.mean(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    success_rate = (statuses.count(200) / len(statuses)) * 100.0

    return {
        "name": name,
        "runs": runs,
        "success_rate": success_rate,
        "min_ms": round(min_lat, 2),
        "mean_ms": round(mean, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max_lat, 2),
        "statuses": {s: statuses.count(s) for s in set(statuses)}
    }

def run_concurrency_test(path, method="GET", body=None, headers=None, total_requests=100, workers=10):
    start_total = time.perf_counter()
    latencies = []
    statuses = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(make_request, path, method, body, headers) for _ in range(total_requests)]
        for f in concurrent.futures.as_completed(futures):
            st, lat, _ = f.result()
            statuses.append(st)
            latencies.append(lat)
            
    total_time = time.perf_counter() - start_total
    rps = total_requests / total_time
    latencies.sort()
    
    return {
        "total_requests": total_requests,
        "concurrency_workers": workers,
        "duration_sec": round(total_time, 2),
        "requests_per_sec": round(rps, 2),
        "success_rate": (statuses.count(200) / len(statuses)) * 100.0,
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 2),
        "max_ms": round(max(latencies), 2),
        "statuses": {s: statuses.count(s) for s in set(statuses)}
    }

def main():
    print("=" * 80)
    print("WattSense AI™ — Production Performance & Latency Benchmark")
    print(f"Target: {BASE_URL} | Database: PostgreSQL 18.4")
    print("=" * 80)

    # 1. Admin Authentication for admin tests
    url = f"{BASE_URL}/api/v1/admin/auth"
    req = urllib.request.Request(url, data=json.dumps({"passkey": settings.ADMIN_SECRET_KEY}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        auth_data = json.loads(resp.read().decode("utf-8"))
    admin_token = auth_data["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    endpoints = [
        ("Public Liveness Probe (/health)", "/health", "GET", None, None),
        ("Admin DB Health (/admin/db-health)", "/api/v1/admin/db-health", "GET", None, admin_headers),
        ("Admin Dataset Audit (/admin/datasets)", "/api/v1/admin/datasets", "GET", None, admin_headers),
        ("Admin Model Metrics (/admin/metrics)", "/api/v1/admin/metrics", "GET", None, admin_headers),
        ("Admin Forecasting Benchmarks", "/api/v1/admin/forecasting-benchmarks", "GET", None, admin_headers),
        ("Admin Wastage Benchmarks", "/api/v1/admin/wastage-benchmarks", "GET", None, admin_headers),
    ]

    print("\n1. System & Admin Endpoints Latency Distribution (20 runs each):")
    print(f"{'Endpoint':<36} | {'Success':<8} | {'Min':<7} | {'p50':<7} | {'p95':<7} | {'p99':<7} | {'Max':<7} (ms)")
    print("-" * 92)

    benchmark_results = []
    for name, path, method, body, headers in endpoints:
        res = benchmark_endpoint(name, path, method, body, headers, runs=20, pause_sec=0.01)
        benchmark_results.append(res)
        print(f"{res['name']:<36} | {res['success_rate']:>6.1f}% | {res['min_ms']:>6.2f} | {res['p50_ms']:>6.2f} | {res['p95_ms']:>6.2f} | {res['p99_ms']:>6.2f} | {res['max_ms']:>6.2f}")

    print("\n2. Concurrency Load Test on Public Health Probe (100 requests, 10 workers):")
    health_c = run_concurrency_test("/health", total_requests=100, workers=10)
    print(f"Throughput:   {health_c['requests_per_sec']} req/sec | Success: {health_c['success_rate']}% | p50: {health_c['p50_ms']}ms | p95: {health_c['p95_ms']}ms")

    print("\n3. Concurrency Load Test on Admin DB Health (100 requests, 10 workers):")
    admin_c = run_concurrency_test("/api/v1/admin/db-health", headers=admin_headers, total_requests=100, workers=10)
    print(f"Throughput:   {admin_c['requests_per_sec']} req/sec | Success: {admin_c['success_rate']}% | p50: {admin_c['p50_ms']}ms | p95: {admin_c['p95_ms']}ms")

    print("\n4. Rate Limiting Throttling Verification (Rapid Burst Attack Simulation):")
    burst_statuses = []
    burst_latencies = []
    for _ in range(30):
        st, lat, _ = make_request("/api/v1/customer/lookup", method="POST", body={"consumer_number": "CONS-RES-1001"})
        burst_statuses.append(st)
        burst_latencies.append(lat)
    
    rate_limited_count = burst_statuses.count(429)
    p50_throttle = statistics.median(burst_latencies)
    print(f"Burst Requests: 30 | HTTP 429 Throttle Count: {rate_limited_count} | Median Throttle Latency: {p50_throttle:.2f} ms")
    assert rate_limited_count > 0, "Rate limiter did not throttle burst attack!"
    print("VERIFIED: Anti-enumeration rate limiter proactively throttles abusive bursts with 429 Too Many Requests.")

    # Save benchmark JSON for report
    bench_file = root / "reports" / "phase10_benchmark_data.json"
    with open(bench_file, "w", encoding="utf-8") as f:
        json.dump({
            "sequential": benchmark_results,
            "concurrency_health": health_c,
            "concurrency_admin_db": admin_c,
            "rate_limiting_test": {
                "burst_count": 30,
                "throttled_count": rate_limited_count,
                "median_latency_ms": round(p50_throttle, 2)
            }
        }, f, indent=2)
    print(f"\nSaved raw performance metrics to: {bench_file}")

if __name__ == "__main__":
    main()
