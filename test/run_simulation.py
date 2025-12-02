import sys
import os
import time
import threading
import statistics
import random
from collections import defaultdict

# Add parent directory to path to import load_balancer modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer.server_pool import ServerPool
from load_balancer.strategies import (
    RoundRobinStrategy,
    LeastConnectionsStrategy,
    ResponseTimeBasedStrategy,
    ALPHA1Strategy,
    BETA1Strategy
)
from workload_generator import WorkloadGenerator
from mock_server import MockServer

class SimulationRunner:
    def __init__(self, num_requests=50000, concurrent_clients=50):
        self.num_requests = num_requests
        self.concurrent_clients = concurrent_clients
        self.workload_gen = WorkloadGenerator(num_unique_keys=1000, zipf_alpha=1.2)
        self.servers = []
        self.pool = ServerPool()
        
        # Network Delay Config (simulating RTT)
        self.min_network_delay = 0.005  # 5ms
        self.max_network_delay = 0.015  # 15ms
        
        # Setup Servers with varying interference
        # Server 0: Fast, Stable
        # Server 1: Fast, Stable
        # Server 2: Slow, Stable
        # Server 3: Fast, High Interference (Noisy Neighbor)
        # Server 4: Fast, High Interference
        configs = [
            (8001, 0.0), (8002, 0.0), (8003, 0.0), (8004, 0.2), (8005, 0.3)
        ]
        
        for port, interference in configs:
            srv = MockServer('127.0.0.1', port, cache_size=50, interference_level=interference)
            self.servers.append(srv)
            self.pool.add_server('127.0.0.1', port)
            
        self.server_map = {f"{s.host}:{s.port}": s for s in self.servers}

    def run_strategy(self, strategy_name, strategy_class):
        print(f"\nTesting {strategy_name}...")
        
        # Reset Servers & Pool for fair comparison
        for s in self.servers:
            s.cache.clear()
            s.stats = {'requests': 0, 'hits': 0, 'misses': 0, 'timeouts': 0, 'overloaded': 0, 'total_latency': 0.0}
            
            # Reset Pool Health
            self.pool.mark_healthy(s.host, s.port)
            # Reset connection counts in pool manually since mark_healthy doesn't do it
            with self.pool.lock:
                key = f"{s.host}:{s.port}"
                if key in self.pool.servers:
                    self.pool.servers[key]['connections'] = 0
                    self.pool.servers[key]['failures'] = 0
        
        strategy = strategy_class()
        
        results = {
            'latencies': [],
            'hits': 0,
            'misses': 0,
            'timeouts': 0,
            'errors': 0
        }
        
        lock = threading.Lock()
        
        def client_worker(num_reqs):
            for _ in range(num_reqs):
                key, size = self.workload_gen.generate_request()
                
                # 1. Select Server
                healthy = self.pool.get_healthy_servers()
                if not healthy:
                    with lock: results['errors'] += 1
                    continue
                
                # Use key-aware selection if available (BETA1)
                if hasattr(strategy, 'select_server_with_key'):
                    selected = strategy.select_server_with_key(healthy, key)
                else:
                    selected = strategy.select_server(healthy)
                
                if not selected:
                    with lock: results['errors'] += 1
                    continue
                    
                s_key = f"{selected['host']}:{selected['port']}"
                mock_server = self.server_map.get(s_key)
                
                # Simulate Network Delay (RTT)
                time.sleep(random.uniform(self.min_network_delay, self.max_network_delay))
                
                # 2. Simulate Processing
                self.pool.increment_connections(selected['host'], selected['port'])
                
                success, latency, is_hit, _ = mock_server.process_request(key, size)
                
                self.pool.decrement_connections(selected['host'], selected['port'])
                
                # 3. Record Stats
                with lock:
                    results['latencies'].append(latency)
                    if is_hit: results['hits'] += 1
                    else: results['misses'] += 1
                    if not success: results['timeouts'] += 1
                
                # 4. Feedback to Strategy (if supported)
                if hasattr(strategy, 'record_response_time'):
                    # Convert ms to seconds for the strategy API
                    strategy.record_response_time(selected['host'], selected['port'], latency / 1000.0)
                
                # Update Pool
                if success:
                    self.pool.mark_healthy(selected['host'], selected['port'])
                    self.pool.record_response_time(selected['host'], selected['port'], latency / 1000.0)
                else:
                    # Don't mark unhealthy immediately in simulation to keep load high
                    pass

        # Run Clients
        threads = []
        reqs_per_client = self.num_requests // self.concurrent_clients
        
        start_time = time.time()
        
        for _ in range(self.concurrent_clients):
            t = threading.Thread(target=client_worker, args=(reqs_per_client,))
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        duration = time.time() - start_time
        
        # Analyze Results
        latencies = sorted(results['latencies'])
        p50 = latencies[int(len(latencies)*0.5)] if latencies else 0
        p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
        p99 = latencies[int(len(latencies)*0.99)] if latencies else 0
        p999 = latencies[int(len(latencies)*0.999)] if latencies else 0
        
        hit_rate = (results['hits'] / (results['hits'] + results['misses'])) * 100 if (results['hits'] + results['misses']) > 0 else 0
        
        # Load Balancing Metrics
        server_requests = [s.stats['requests'] for s in self.servers]
        stdev_requests = statistics.stdev(server_requests) if len(server_requests) > 1 else 0
        
        # Jain's Fairness Index = (sum(x_i))^2 / (n * sum(x_i^2))
        sum_reqs = sum(server_requests)
        sum_sq_reqs = sum(r*r for r in server_requests)
        n = len(server_requests)
        fairness_index = (sum_reqs ** 2) / (n * sum_sq_reqs) if sum_sq_reqs > 0 else 0
        
        print(f"  Duration: {duration:.2f}s")
        print(f"  RPS: {self.num_requests / duration:.2f}")
        print(f"  Avg Latency: {statistics.mean(latencies):.2f}ms")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")
        print(f"  P99.9: {p999:.2f}ms")
        print(f"  Cache Hit Rate: {hit_rate:.2f}%")
        print(f"  Timeouts: {results['timeouts']}")
        print(f"  Load Stdev: {stdev_requests:.2f}")
        print(f"  Fairness Index: {fairness_index:.4f}")
        
        return {
            'strategy': strategy_name,
            'p99': p99,
            'p999': p999,
            'hit_rate': hit_rate,
            'rps': self.num_requests / duration,
            'stdev': stdev_requests,
            'fairness': fairness_index
        }

if __name__ == "__main__":
    sim = SimulationRunner(num_requests=50000, concurrent_clients=50)
    
    strategies = [
        ("Round Robin", RoundRobinStrategy),
        ("Least Conn", LeastConnectionsStrategy),
        ("Response Time", ResponseTimeBasedStrategy),
        ("ALPHA1 (AURA)", ALPHA1Strategy),
        ("BETA1 (HELIOS)", BETA1Strategy)
    ]
    
    final_results = []
    for name, cls in strategies:
        final_results.append(sim.run_strategy(name, cls))
        
    print("\n=== FINAL SUMMARY ===")
    print(f"{'Strategy':<20} {'P99 (ms)':<10} {'P99.9 (ms)':<12} {'Hit Rate (%)':<15} {'RPS':<10} {'Stdev':<10} {'Fairness':<10}")
    print("-" * 100)
    for r in final_results:
        print(f"{r['strategy']:<20} {r['p99']:<10.2f} {r['p999']:<12.2f} {r['hit_rate']:<15.2f} {r['rps']:<10.2f} {r['stdev']:<10.2f} {r['fairness']:<10.4f}")
