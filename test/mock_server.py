import time
import random
import threading
from collections import deque

class MockServer:
    """
    Simulates a realistic backend server with:
    - In-memory Cache (LRU)
    - Variable Processing Time (CPU)
    - Interference (Noisy Neighbor)
    - Stragglers (heavy-tail latency)
    - Actual sleep for realistic timing
    """
    
    def __init__(self, host, port, cache_size=50, interference_level=0.0, max_connections=40):
        self.host = host
        self.port = port
        self.key = f"{host}:{port}"
        
        # Cache (smaller = harder to maintain locality)
        self.cache = {} # key -> data
        self.cache_size = cache_size
        self.lru_queue = deque(maxlen=cache_size)
        
        # Performance Config
        self.base_latency_ms = random.uniform(10, 20)  # Variable base latency per server
        self.cache_hit_latency_ms = 3.0  # Fast cache hit
        self.cache_miss_latency_ms = 200.0  # Slow DB/API fetch (more realistic)
        
        # Interference (0.0 to 1.0)
        # Represents co-tenancy effects (noisy neighbors)
        self.interference_level = interference_level
        
        # Connection limits (realistic server capacity)
        self.max_connections = max_connections
        self.current_connections = 0
        
        # Server health (can fail temporarily)
        self.is_healthy = True
        self.failure_until = 0  # Timestamp when server recovers
        
        # Stats
        self.stats = {
            'requests': 0,
            'hits': 0,
            'misses': 0,
            'timeouts': 0,
            'overloaded': 0,
            'total_latency': 0.0
        }
        self.lock = threading.Lock()

    def process_request(self, key, size_kb, timeout_ms=250, simulate_sleep=True):
        """
        Simulate realistic request processing with actual delays.
        Returns (success, latency_ms, is_hit, error_reason).
        
        Args:
            key: Request key for cache lookup
            size_kb: Request size in KB
            timeout_ms: Timeout threshold (stricter SLO)
            simulate_sleep: If True, actually sleep to simulate processing time
        """
        with self.lock:
            self.stats['requests'] += 1
            
            # 0. Check if server is healthy (temporary failures)
            if not self.is_healthy:
                if time.time() < self.failure_until:
                    return False, 0, False, "server_down"
                else:
                    self.is_healthy = True  # Recover
            
            # Random server failures (1% chance)
            if random.random() < 0.01:
                self.is_healthy = False
                self.failure_until = time.time() + random.uniform(0.5, 2.0)  # Down for 0.5-2s
                return False, 0, False, "server_failure"
            
            # Check connection limit (realistic capacity)
            if self.current_connections >= self.max_connections:
                self.stats['overloaded'] += 1
                return False, 0, False, "overloaded"
            
            self.current_connections += 1
        
        try:
            with self.lock:
                # 1. Check Cache
                is_hit = key in self.cache
                if is_hit:
                    self.stats['hits'] += 1
                    # Update LRU
                    if key in self.lru_queue:
                        self.lru_queue.remove(key)
                    self.lru_queue.append(key)
                    latency = self.base_latency_ms + self.cache_hit_latency_ms
                else:
                    self.stats['misses'] += 1
                    latency = self.base_latency_ms + self.cache_miss_latency_ms
                    # Add to cache
                    self._add_to_cache(key)
                
                # 2. Add Request Size Overhead (larger requests take longer)
                # +2% per KB (more realistic)
                size_factor = 1.0 + (size_kb / 50.0)
                latency *= size_factor
                
                # 3. Add Interference (co-tenancy noise) - BURSTY & REALISTIC
                if self.interference_level > 0:
                    current_time = time.time()
                    # Bursty interference: waves of high noise lasting 5-10 seconds
                    # Cycle: 20s quiet, 10s noisy
                    cycle_time = current_time % 30
                    is_burst_period = cycle_time > 20
                    
                    if is_burst_period and random.random() < self.interference_level:
                         # Major interference spike during burst period
                         interference_spike = random.uniform(100, 300)
                         latency += interference_spike
                    elif random.random() < (self.interference_level * 0.1):
                        # Occasional background noise
                        interference_noise = random.uniform(10, 50)
                        latency += interference_noise
                
                # 4. Simulate Stragglers (heavy-tail behavior) - BALANCED
                # 8% of requests become stragglers
                if random.random() < 0.08:
                    straggler_factor = random.uniform(2, 8)  # 2-8x slower
                    latency *= straggler_factor
                
                # 5. Queue delay based on current load
                # More connections = more queueing delay
                queue_delay = self.current_connections * random.uniform(2, 5)
                latency += queue_delay
                
                # 6. Update Stats
                self.stats['total_latency'] += latency
            
            # 7. Actually sleep to simulate processing time (realistic timing)
            if simulate_sleep:
                time.sleep(latency / 1000.0)  # Convert ms to seconds
            
            # 8. Check Timeout
            with self.lock:
                if latency > timeout_ms:
                    self.stats['timeouts'] += 1
                    return False, latency, is_hit, "timeout"
                
                return True, latency, is_hit, None
        
        finally:
            with self.lock:
                self.current_connections -= 1

    def _add_to_cache(self, key):
        if len(self.cache) >= self.cache_size:
            # Evict oldest
            if self.lru_queue:
                evicted = self.lru_queue.popleft()
                if evicted in self.cache:
                    del self.cache[evicted]
        
        self.cache[key] = True
        self.lru_queue.append(key)

    def get_stats(self):
        with self.lock:
            return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics for new test run"""
        with self.lock:
            self.cache.clear()
            self.lru_queue.clear()
            self.current_connections = 0
            self.is_healthy = True
            self.failure_until = 0
            self.stats = {
                'requests': 0,
                'hits': 0,
                'misses': 0,
                'timeouts': 0,
                'overloaded': 0,
                'total_latency': 0.0
            }
