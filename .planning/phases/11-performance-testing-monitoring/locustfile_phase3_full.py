"""
Phase 11: Load Testing Script - Full Pipeline E2E (Phase 3)
==========================================================

Usage:
    locust -f locustfile_phase3_full.py --host http://localhost:8000
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

TEST_ENDPOINT = "/api/v1/ask"

test_results = {"success": 0, "failure": 0, "responses_ms": []}

class FullRAGTasks(TaskSet):
    @task
    def test_full_rag_endpoint(self):
        query = random.choice(LEGAL_QUERIES)
        with self.client.post(
            TEST_ENDPOINT,
            json={"query": query},
            catch_response=True,
            timeout=60
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    test_results["success"] += 1
                    # In a real app we'd measure time ourselves, 
                    # but Locust tracks it automatically for the request.
                    # We'll just collect it.
                    test_results["responses_ms"].append(response.elapsed.total_seconds() * 1000)
                    response.success()
                except Exception as e:
                    test_results["failure"] += 1
                    response.failure(f"JSON error: {e}")
            else:
                test_results["failure"] += 1
                response.failure(f"Status {response.status_code}")

class FullRAGUser(HttpUser):
    tasks = [FullRAGTasks]
    wait_time = between(2, 5)

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
        print("PHASE 3: FULL PIPELINE E2E PERFORMANCE TEST RESULTS")
        print("="*60)
        print(f"\nRequests: {test_results['success']} success, {test_results['failure']} failed ({success_rate:.1f}% success)")
        print(f"\nLatency (ms):")
        print(f"  P50:  {p50_ms:.0f}")
        print(f"  Mean: {avg_ms:.0f}")
        print(f"  P95:  {p95_ms:.0f}")
        print(f"  P99:  {p99_ms:.0f}")
        
        if p95_ms < 15000:
            print(f"\n✓ Full pipeline latency is acceptable (p95 < 15000ms)")
        else:
            print(f"\n✗ Full pipeline latency exceeds target (p95 > 15000ms)")
        print("="*60 + "\n")
