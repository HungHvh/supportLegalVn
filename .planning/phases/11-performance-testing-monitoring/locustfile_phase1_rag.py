"""
Phase 11: Load Testing Script - RAG Core Baseline (Phase 1)
===========================================================

Usage:
    1. Start FastAPI: python -m uvicorn app:app --reload
    2. Locust: locust -f locustfile_phase1_rag.py --host http://localhost:8000
    3. Open http://localhost:8089
    4. Monitor: docker stats (in PowerShell)

Expected: p95 latency increases linearly with users; RAM < 3.2GB
"""

from locust import HttpUser, TaskSet, task, between, events
import random
import statistics

LEGAL_QUERIES = [
    "Tội trộm cắp tài sản",
    "Đăng ký kết hôn cần gì",
    "Luật đất đai 2024",
    "Xử lý vi phạm giao thông",
    "Hợp đồng lao động 30 ngày",
    "Quyền thừa kế pháp định",
]

# Keep endpoint in one place to avoid prefix mismatches.
TEST_ENDPOINT = "/api/v1/test-rag"

test_results = {"success": 0, "failure": 0, "responses_ms": []}

class RAGTasks(TaskSet):
    @task
    def test_rag_endpoint(self):
        query = random.choice(LEGAL_QUERIES)
        with self.client.post(
            TEST_ENDPOINT,
            json={"query": query},
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    test_results["success"] += 1
                    test_results["responses_ms"].append(data.get("elapsed_ms", 0))
                    response.success()
                except Exception as e:
                    test_results["failure"] += 1
                    response.failure(f"JSON error: {e}")
            else:
                test_results["failure"] += 1
                response.failure(f"Status {response.status_code}")

class LegalRAGUser(HttpUser):
    tasks = [RAGTasks]
    wait_time = between(1, 3)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary statistics."""
    if test_results["responses_ms"]:
        sorted_times = sorted(test_results["responses_ms"])
        avg_ms = statistics.mean(test_results["responses_ms"])
        p50_ms = sorted_times[int(len(sorted_times) * 0.5)]
        p95_ms = sorted_times[int(len(sorted_times) * 0.95)]
        p99_ms = sorted_times[int(len(sorted_times) * 0.99)]
        total = test_results["success"] + test_results["failure"]
        success_rate = (test_results["success"] / total * 100) if total > 0 else 0
        
        print("\n" + "="*60)
        print("PHASE 1: RAG CORE PERFORMANCE TEST RESULTS")
        print("="*60)
        print(f"\nRequests: {test_results['success']} success, {test_results['failure']} failed ({success_rate:.1f}% success)")
        print(f"\nLatency (ms):")
        print(f"  P50:  {p50_ms:.0f}")
        print(f"  Mean: {avg_ms:.0f}")
        print(f"  P95:  {p95_ms:.0f}")
        print(f"  P99:  {p99_ms:.0f}")
        
        # Interpretation
        if p95_ms < 3000:
            print(f"\n✓ RAG latency is acceptable (p95 < 3000ms)")
        else:
            print(f"\n✗ RAG latency may need optimization (p95 > 3000ms)")
        
        print("\nNEXT: Check docker stats for Qdrant peak RAM/CPU")
        print("      Then review detailed metrics in Locust web UI")
        print("="*60 + "\n")
