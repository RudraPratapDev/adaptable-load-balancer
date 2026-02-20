from abc import ABC, abstractmethod
import threading
import time
import random
from collections import defaultdict, deque


class Strategy(ABC):
    """Base interface for load balancing strategies"""
    
    @abstractmethod
    def select_server(self, server_list):
        """Select next server from healthy server list"""
        pass


class RoundRobinStrategy(Strategy):
    def __init__(self):
        self.current = 0
        self.lock = threading.Lock()
    
    def select_server(self, server_list):
        if not server_list:
            return None
        
        with self.lock:
            if self.current >= len(server_list):
                self.current = 0
            
            srv = server_list[self.current]
            self.current += 1
            return srv


class LeastConnectionsStrategy(Strategy):
    def __init__(self):
        self._idx = 0
        self._lock = threading.Lock()

    def select_server(self, server_list):
        if not server_list:
            return None
        
        min_conn = min(srv['connections'] for srv in server_list)
        candidates = [srv for srv in server_list if srv['connections'] == min_conn]

        with self._lock:
            if not candidates:
                return server_list[0]
            if self._idx >= len(candidates):
                self._idx = 0
            srv = candidates[self._idx]
            self._idx += 1
            return srv


class HealthScoreBasedStrategy(Strategy):
    """
    Health-Score-Based Selection (HS-BS)
    
    Calculates a health score for each server based on active connections and recent failures.
    Formula: Score = (1 / (1 + Active_Connections)) * (1 / (1 + Recent_Failures))
    When scores are equal, uses round-robin among best servers.
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        self.last_selected_index = 0
    
    def select_server(self, server_list):
        if not server_list:
            return None
        
        with self.lock:
            # Calculate health scores for all servers
            server_scores = []
            best_score = -1
            
            for srv in server_list:
                connection_factor = 1 / (1 + srv['connections'])
                failure_factor = 1 / (1 + srv['failures'])
                health_score = connection_factor * failure_factor
                server_scores.append((srv, health_score))
                
                if health_score > best_score:
                    best_score = health_score
            
            # Find all servers with the best score
            best_servers = [srv for srv, score in server_scores if abs(score - best_score) < 0.001]
            
            # Round-robin among servers with equal best scores
            if len(best_servers) > 1:
                self.last_selected_index = (self.last_selected_index + 1) % len(best_servers)
                return best_servers[self.last_selected_index]
            else:
                return best_servers[0] if best_servers else server_list[0]


class HistoricalFailureWeightedRoundRobin(Strategy):
    """
    Historical Failure-Weighted Round Robin (HF-WRR)
    
    Adaptive Round Robin that assigns weights based on server stability:
    - 0 failures: weight = 10
    - 1 failure: weight = 5  
    - 2+ failures: weight = 1
    
    Each server gets requests equal to its weight before moving to next server.
    """
    
    def __init__(self):
        self.server_weights = {}
        self.current_server = None
        self.current_weight_remaining = 0
        self.server_index = 0
        self.lock = threading.Lock()
    
    def _calculate_weight(self, failures):
        """Calculate weight based on failure count"""
        if failures == 0:
            return 10
        elif failures == 1:
            return 5
        else:
            return 1
    
    def select_server(self, server_list):
        if not server_list:
            return None
        
        with self.lock:
            # Update weights for all servers
            for srv in server_list:
                server_key = f"{srv['host']}:{srv['port']}"
                self.server_weights[server_key] = self._calculate_weight(srv['failures'])
            
            # If no current server or current server not in list, start fresh
            if (self.current_server is None or 
                self.current_server not in [f"{s['host']}:{s['port']}" for s in server_list] or
                self.current_weight_remaining <= 0):
                
                self.server_index = 0
                if self.server_index < len(server_list):
                    srv = server_list[self.server_index]
                    self.current_server = f"{srv['host']}:{srv['port']}"
                    self.current_weight_remaining = self.server_weights[self.current_server]
            
            # Find current server in list
            current_srv = None
            for srv in server_list:
                if f"{srv['host']}:{srv['port']}" == self.current_server:
                    current_srv = srv
                    break
            
            if current_srv is None:
                # Fallback to first server
                current_srv = server_list[0]
                self.current_server = f"{current_srv['host']}:{current_srv['port']}"
                self.current_weight_remaining = self.server_weights[self.current_server]
            
            # Decrement weight
            self.current_weight_remaining -= 1
            
            # Move to next server if weight exhausted
            if self.current_weight_remaining <= 0:
                self.server_index = (self.server_index + 1) % len(server_list)
                next_srv = server_list[self.server_index]
                self.current_server = f"{next_srv['host']}:{next_srv['port']}"
                self.current_weight_remaining = self.server_weights[self.current_server]
            
            return current_srv


class ResponseTimeBasedStrategy(Strategy):
    """
    Recent Response Time-Biased Selection (RRT-BS)
    
    Selects the server with the lowest average response time over recent requests.
    When no response time data exists, uses round-robin to build initial data.
    """
    
    def __init__(self, max_history=100):
        self.response_times = defaultdict(list)  # server_key -> [response_times]
        self.max_history = max_history
        self.lock = threading.Lock()
        self.round_robin_index = 0
    
    def record_response_time(self, host, port, response_time):
        """Record response time for a server"""
        server_key = f"{host}:{port}"
        with self.lock:
            self.response_times[server_key].append(response_time)
            # Keep only recent history
            if len(self.response_times[server_key]) > self.max_history:
                self.response_times[server_key].pop(0)
    
    def _get_average_response_time(self, server_key):
        """Get average response time for a server"""
        if server_key not in self.response_times or not self.response_times[server_key]:
            return None  # No data available
        
        times = self.response_times[server_key]
        return sum(times) / len(times)
    
    def select_server(self, server_list):
        if not server_list:
            return None
        
        with self.lock:
            # Check if we have response time data for servers
            servers_with_data = []
            servers_without_data = []
            
            for srv in server_list:
                server_key = f"{srv['host']}:{srv['port']}"
                avg_time = self._get_average_response_time(server_key)
                
                if avg_time is not None:
                    servers_with_data.append((srv, avg_time))
                else:
                    servers_without_data.append(srv)
            
            # If no servers have response time data, use round-robin to build initial data
            if not servers_with_data:
                self.round_robin_index = (self.round_robin_index + 1) % len(server_list)
                return server_list[self.round_robin_index]
            
            # If some servers don't have data, give them a chance (round-robin among them)
            if servers_without_data and len(servers_with_data) < len(server_list):
                # Occasionally select servers without data to build their response time history
                import random
                if random.random() < 0.2:  # 20% chance to select server without data
                    return random.choice(servers_without_data)
            
            # Select server with lowest average response time
            best_server, best_time = min(servers_with_data, key=lambda x: x[1])
            return best_server



class ALPHA1Strategy(Strategy):
    """
    ALPHA1 - Tail Latency Reduction Strategy
    
    Designed to reduce tail latency (p95-p99.9) in heavy-tailed workloads with 
    noisy co-tenancy interference and stragglers.
    
    Key Features:
    1. Two-Choice Sampling: Randomly picks 2 servers (power of two choices)
    2. Tail-Risk Scoring: Estimates risk using work_remaining + interference + queue_age
    3. SLO-Aware Conditional Hedging: Only hedges when predicted finish time exceeds SLO
    4. Feedback Control: Adjusts weights based on recent p99 behavior
    
    Formula: Tail-Risk Score = EWMA(work_remaining) + β*interference + γ*head_request_age
    """
    
    def __init__(self, slo_threshold_ms=100, hedge_threshold_multiplier=1.5):
        self.lock = threading.Lock()
        
        # Configuration
        self.slo_threshold_ms = slo_threshold_ms  # Target SLO in milliseconds
        self.hedge_threshold_multiplier = hedge_threshold_multiplier  # When to hedge
        
        # Adaptive weights for tail-risk scoring
        self.beta = 0.3   # Weight for interference signal
        self.gamma = 0.4  # Weight for head request age
        
        # EWMA smoothing factor (0.3 = 30% new, 70% old)
        self.ewma_alpha = 0.3
        
        # Per-server state tracking
        self.server_state = defaultdict(lambda: {
            'work_queue_ewma': 0.0,           # EWMA of estimated work in queue
            'interference_signal': 0.0,        # Simulated interference metric
            'head_request_age': 0.0,           # Age of oldest request in queue
            'last_update': time.time(),
            'request_timestamps': deque(maxlen=10),  # Track recent request times
            'response_times': deque(maxlen=100),     # Track response times for p99
        })
        
        # Global metrics for feedback control
        self.recent_latencies = deque(maxlen=1000)  # Track recent latencies for p99
        self.target_p99_ms = slo_threshold_ms * 0.9  # Target p99 slightly below SLO
        self.feedback_adjustment_interval = 100  # Adjust weights every N requests
        self.request_count = 0
        
        # Hedging statistics
        self.hedge_count = 0
        self.total_requests = 0
        
    def select_server(self, server_list):
        """
        Main selection logic using ALPHA1 algorithm
        """
        if not server_list:
            return None
        
        if len(server_list) == 1:
            return server_list[0]
        
        with self.lock:
            # Step 1: Two-Choice Sampling (Power of Two Choices)
            s1 = random.choice(server_list)
            s2 = random.choice(server_list)
            
            # Ensure we pick two different servers if possible
            attempts = 0
            while s1 == s2 and len(server_list) > 1 and attempts < 3:
                s2 = random.choice(server_list)
                attempts += 1
            
            # Step 2: Compute Tail-Risk Score for each candidate
            score1 = self._compute_tail_risk(s1)
            score2 = self._compute_tail_risk(s2)
            
            # Step 3: Choose server with lower tail-risk score
            if score1 <= score2:
                primary = s1
                backup = s2
            else:
                primary = s2
                backup = s1
            
            # Step 4: Update server state (simulate queue dynamics)
            self._update_server_state(primary)
            
            # Step 5: Track request for feedback control
            self.total_requests += 1
            self.request_count += 1
            
            # Step 6: Periodic feedback control adjustment
            if self.request_count >= self.feedback_adjustment_interval:
                self._adjust_weights_feedback()
                self.request_count = 0
            
            # Note: Hedging logic would require request-level context
            # For now, we return the primary server
            # In a full implementation, hedging would be handled at dispatch level
            
            return primary
    
    def _compute_tail_risk(self, server):
        """
        Compute tail-risk score for a server
        Score = EWMA(work_remaining) + β*interference + γ*head_request_age
        """
        server_key = f"{server['host']}:{server['port']}"
        state = self.server_state[server_key]
        
        # Component 1: Estimated work remaining (based on connections and recent activity)
        work_remaining = state['work_queue_ewma']
        
        # Component 2: Interference signal (simulated from connection patterns)
        interference = state['interference_signal']
        
        # Component 3: Head request age (oldest request waiting time)
        head_age = state['head_request_age']
        
        # Compute composite tail-risk score
        tail_risk_score = work_remaining + (self.beta * interference) + (self.gamma * head_age)
        
        return tail_risk_score
    
    def _update_server_state(self, server):
        """
        Update server state with new request assignment
        Simulates queue dynamics and interference
        """
        server_key = f"{server['host']}:{server['port']}"
        state = self.server_state[server_key]
        current_time = time.time()
        
        # Update work queue EWMA based on current connections
        # Higher connections = more work in queue
        current_work = server['connections'] * 10  # Arbitrary work units
        state['work_queue_ewma'] = (
            self.ewma_alpha * current_work + 
            (1 - self.ewma_alpha) * state['work_queue_ewma']
        )
        
        # Calculate interference signal based on response time volatility
        # More volatile response times = higher interference (CPU contention, noisy neighbors)
        state['request_timestamps'].append(current_time)
        if len(state['response_times']) >= 5:
            # Calculate response time variance as interference proxy
            times = list(state['response_times'])
            avg_time = sum(times) / len(times)
            variance = sum((x - avg_time) ** 2 for x in times) / len(times)
            # Normalize variance to 0-10 scale (variance in ms², divide by 1000 for scaling)
            state['interference_signal'] = min(variance / 1000.0, 10.0)  # Cap at 10
        else:
            # Not enough response time data yet, use neutral interference
            state['interference_signal'] = 0.0
        
        # Update head request age (time since oldest request)
        time_since_last = current_time - state['last_update']
        if server['connections'] > 0:
            # If there are connections, age increases
            state['head_request_age'] = min(state['head_request_age'] + time_since_last, 5.0)
        else:
            # If queue is empty, reset age
            state['head_request_age'] = 0.0
        
        state['last_update'] = current_time
    
    def _adjust_weights_feedback(self):
        """
        Feedback control: Adjust β and γ weights based on recent p99 performance
        If p99 > target, increase weights to be more sensitive to interference/age
        If p99 < target, decay weights to avoid over-correction
        """
        if len(self.recent_latencies) < 100:
            return  # Not enough data yet
        
        # Calculate current p99
        sorted_latencies = sorted(self.recent_latencies)
        p99_index = int(len(sorted_latencies) * 0.99)
        current_p99 = sorted_latencies[p99_index] if p99_index < len(sorted_latencies) else sorted_latencies[-1]
        
        # Feedback adjustment
        if current_p99 > self.target_p99_ms:
            # p99 is too high, increase sensitivity to interference and age
            self.beta = min(self.beta * 1.1, 1.0)   # Increase by 10%, cap at 1.0
            self.gamma = min(self.gamma * 1.1, 1.0)
        else:
            # p99 is good, slowly decay weights to avoid over-sensitivity
            self.beta = max(self.beta * 0.95, 0.1)  # Decay by 5%, floor at 0.1
            self.gamma = max(self.gamma * 0.95, 0.1)
    
    def record_response_time(self, host, port, response_time_seconds):
        """
        Record response time for feedback control
        """
        server_key = f"{host}:{port}"
        response_time_ms = response_time_seconds * 1000
        
        with self.lock:
            # Track in server state
            if server_key in self.server_state:
                self.server_state[server_key]['response_times'].append(response_time_ms)
            
            # Track globally for p99 calculation
            self.recent_latencies.append(response_time_ms)
    
    def should_hedge(self, server, estimated_service_time_ms):
        """
        Determine if request should be hedged based on SLO
        Returns True if predicted finish time exceeds SLO threshold
        """
        server_key = f"{server['host']}:{server['port']}"
        state = self.server_state[server_key]
        
        # Predict finish time = current queue work + new request service time
        predicted_finish_ms = state['work_queue_ewma'] + estimated_service_time_ms
        
        # Hedge if predicted finish exceeds SLO threshold
        threshold = self.slo_threshold_ms * self.hedge_threshold_multiplier
        
        if predicted_finish_ms > threshold:
            self.hedge_count += 1
            return True
        
        return False
    
    def get_metrics(self):
        """
        Return algorithm-specific metrics for monitoring
        """
        with self.lock:
            hedge_rate = (self.hedge_count / max(self.total_requests, 1)) * 100
            
            # Calculate current p99 if we have data
            current_p99 = 0.0
            if len(self.recent_latencies) >= 10:
                sorted_latencies = sorted(self.recent_latencies)
                p99_index = int(len(sorted_latencies) * 0.99)
                current_p99 = sorted_latencies[p99_index]
            
            return {
                'beta': round(self.beta, 3),
                'gamma': round(self.gamma, 3),
                'hedge_rate': round(hedge_rate, 2),
                'total_requests': self.total_requests,
                'current_p99_ms': round(current_p99, 2),
                'target_p99_ms': self.target_p99_ms,
                'slo_threshold_ms': self.slo_threshold_ms
            }
    
    def get_server_metrics(self, host, port):
        """
        Get tail-risk metrics for a specific server
        """
        server_key = f"{host}:{port}"
        with self.lock:
            if server_key not in self.server_state:
                return {}
            
            state = self.server_state[server_key]
            
            # Calculate server p99 if we have data
            server_p99 = 0.0
            if len(state['response_times']) >= 10:
                sorted_times = sorted(state['response_times'])
                p99_index = int(len(sorted_times) * 0.99)
                server_p99 = sorted_times[p99_index]
            
            return {
                'work_queue_ewma': round(state['work_queue_ewma'], 2),
                'interference_signal': round(state['interference_signal'], 3),
                'head_request_age': round(state['head_request_age'], 3),
                'server_p99_ms': round(server_p99, 2)
            }



class BETA1Strategy(Strategy):
    """
    BETA1 - Bounded-Load Cache-Aware Rendezvous Hashing (BLCRW)
    
    Targets cache locality problems in load balancing by providing key affinity
    while preventing hotspots and handling scaling gracefully.
    
    Key Features:
    1. Rendezvous (HRW) Hashing: Stable key-to-server assignment
    2. Bounded-Load Admission Control: Prevents overload (current_load ≤ c × avg_load)
    3. Warm-Up Mode: Gradual traffic shift during scaling events
    4. Popularity-Aware Spill: Tracks recent keys to maintain cache warmth
    
    Formula: weight(key, server) = hash(key || server_id)
    """
    
    def __init__(self, capacity_factor=1.25, warmup_duration=60, warmup_quota_factor=0.3):
        self.lock = threading.Lock()
        
        # Configuration
        self.capacity_factor = capacity_factor  # Max load = capacity_factor × average_load
        self.warmup_duration = warmup_duration  # Seconds for warm-up period
        self.warmup_quota_factor = warmup_quota_factor  # Fraction of traffic during warm-up
        
        # Server state tracking
        self.server_state = defaultdict(lambda: {
            'total_requests': 0,
            'recent_keys': set(),  # Track recent keys (simple cache-aware tracking)
            'warmup_start_time': None,
            'warmup_requests': 0,
            'is_new': False,
        })
        
        # Global state
        self.total_requests = 0
        self.known_servers = set()  # Track server additions/removals
        
        # Recent key tracking (popularity-aware)
        self.recent_key_limit = 1000  # Keep track of last N keys per server
        
        # Statistics
        self.cache_hits = 0  # Requests sent to preferred server
        self.bounded_load_redirects = 0  # Requests redirected due to overload
        self.warmup_redirects = 0  # Requests redirected due to warm-up
        
    def select_server(self, server_list):
        """
        Main selection logic using BETA1 (BLCRW) algorithm
        """
        if not server_list:
            return None
        
        if len(server_list) == 1:
            return server_list[0]
        
        with self.lock:
            # Detect new servers (scaling event)
            self._detect_scaling_events(server_list)
            
            # For cache-aware routing, we need a key
            # Since we don't have request context here, we'll use a pseudo-key
            # based on timestamp and request count for demonstration
            # In a real implementation, this would come from the request
            pseudo_key = f"req_{self.total_requests}_{int(time.time() * 1000) % 10000}"
            
            # Step 1: Rank servers using HRW (Rendezvous Hashing)
            ranked_servers = self._hrw_rank(pseudo_key, server_list)
            
            # Step 2: Find first non-overloaded server in ranking
            chosen_server = None
            average_load = self._calculate_average_load(server_list)
            
            for server in ranked_servers:
                server_key = f"{server['host']}:{server['port']}"
                
                # Check if server is overloaded
                if self._is_overloaded(server, average_load):
                    continue
                
                # Check warm-up constraints
                if self._in_warmup_mode(server_key):
                    if self._warmup_quota_exceeded(server_key, average_load):
                        self.warmup_redirects += 1
                        continue
                
                # Check popularity-aware selection (cache warmth)
                if self._key_is_recent_on(pseudo_key, server_key):
                    # Cache hit - key recently seen on this server
                    chosen_server = server
                    self.cache_hits += 1
                    break
                
                # Server is available and not overloaded
                chosen_server = server
                break
            
            # Step 3: Fallback to top-ranked server if all are overloaded (rare)
            if chosen_server is None:
                chosen_server = ranked_servers[0]
                self.bounded_load_redirects += 1
            
            # Update state
            server_key = f"{chosen_server['host']}:{chosen_server['port']}"
            self._update_server_state(server_key, pseudo_key)
            self.total_requests += 1
            
            return chosen_server
    
    def select_server_with_key(self, server_list, request_key):
        """
        Enhanced selection with explicit request key for true cache affinity
        This method can be called when request context is available
        """
        if not server_list:
            return None
        
        if len(server_list) == 1:
            return server_list[0]
        
        with self.lock:
            # Detect new servers
            self._detect_scaling_events(server_list)
            
            # Step 1: Rank servers using HRW
            ranked_servers = self._hrw_rank(request_key, server_list)
            
            # Step 2: Find first non-overloaded server
            chosen_server = None
            average_load = self._calculate_average_load(server_list)
            
            for server in ranked_servers:
                server_key = f"{server['host']}:{server['port']}"
                
                if self._is_overloaded(server, average_load):
                    continue
                
                if self._in_warmup_mode(server_key):
                    if self._warmup_quota_exceeded(server_key, average_load):
                        self.warmup_redirects += 1
                        continue
                
                if self._key_is_recent_on(request_key, server_key):
                    chosen_server = server
                    self.cache_hits += 1
                    break
                
                chosen_server = server
                break
            
            if chosen_server is None:
                chosen_server = ranked_servers[0]
                self.bounded_load_redirects += 1
            
            # Update state
            server_key = f"{chosen_server['host']}:{chosen_server['port']}"
            self._update_server_state(server_key, request_key)
            self.total_requests += 1
            
            return chosen_server
    
    def _hrw_rank(self, key, server_list):
        """
        Rendezvous (Highest Random Weight) Hashing
        Returns servers sorted by descending hash weight for the given key
        """
        import hashlib
        
        server_weights = []
        for server in server_list:
            server_id = f"{server['host']}:{server['port']}"
            # Compute hash weight: hash(key || server_id)
            combined = f"{key}:{server_id}".encode('utf-8')
            hash_value = int(hashlib.sha256(combined).hexdigest(), 16)
            server_weights.append((server, hash_value))
        
        # Sort by hash weight (descending)
        server_weights.sort(key=lambda x: x[1], reverse=True)
        
        return [server for server, weight in server_weights]
    
    def _is_overloaded(self, server, average_load):
        """
        Check if server is overloaded based on bounded-load constraint
        current_load ≤ capacity_factor × average_load
        """
        current_load = server['connections']
        threshold = self.capacity_factor * average_load
        return current_load > threshold
    
    def _calculate_average_load(self, server_list):
        """
        Calculate average load across all servers
        """
        if not server_list:
            return 0
        
        total_load = sum(server['connections'] for server in server_list)
        return total_load / len(server_list)
    
    def _in_warmup_mode(self, server_key):
        """
        Check if server is in warm-up mode
        """
        state = self.server_state[server_key]
        if not state['is_new'] or state['warmup_start_time'] is None:
            return False
        
        elapsed = time.time() - state['warmup_start_time']
        return elapsed < self.warmup_duration
    
    def _warmup_quota_exceeded(self, server_key, average_load):
        """
        Check if warm-up server has exceeded its quota
        During warm-up, server should only receive warmup_quota_factor × average_load
        """
        state = self.server_state[server_key]
        warmup_quota = self.warmup_quota_factor * average_load * self.warmup_duration
        
        return state['warmup_requests'] >= warmup_quota
    
    def _key_is_recent_on(self, key, server_key):
        """
        Check if key was recently seen on this server (cache warmth check)
        """
        state = self.server_state[server_key]
        return key in state['recent_keys']
    
    def _update_server_state(self, server_key, key):
        """
        Update server state with new request
        """
        state = self.server_state[server_key]
        state['total_requests'] += 1
        
        # Track recent keys (simple LRU-like behavior)
        state['recent_keys'].add(key)
        if len(state['recent_keys']) > self.recent_key_limit:
            # Remove oldest keys (in practice, use a proper LRU or Bloom filter)
            # For simplicity, we'll clear half when limit is reached
            keys_list = list(state['recent_keys'])
            state['recent_keys'] = set(keys_list[-self.recent_key_limit // 2:])
        
        # Update warm-up counters
        if state['is_new']:
            state['warmup_requests'] += 1
    
    def _detect_scaling_events(self, server_list):
        """
        Detect when servers are added or removed (scaling events)
        """
        current_servers = {f"{s['host']}:{s['port']}" for s in server_list}
        
        # Detect new servers
        new_servers = current_servers - self.known_servers
        for server_key in new_servers:
            state = self.server_state[server_key]
            state['is_new'] = True
            state['warmup_start_time'] = time.time()
            state['warmup_requests'] = 0
        
        # Detect removed servers (cleanup)
        removed_servers = self.known_servers - current_servers
        for server_key in removed_servers:
            if server_key in self.server_state:
                del self.server_state[server_key]
        
        # Update known servers
        self.known_servers = current_servers
        
        # Check if warm-up period has ended for any servers
        for server_key in current_servers:
            state = self.server_state[server_key]
            if state['is_new'] and state['warmup_start_time']:
                elapsed = time.time() - state['warmup_start_time']
                if elapsed >= self.warmup_duration:
                    state['is_new'] = False
                    state['warmup_start_time'] = None
    
    def get_metrics(self):
        """
        Return algorithm-specific metrics for monitoring
        """
        with self.lock:
            cache_hit_rate = (self.cache_hits / max(self.total_requests, 1)) * 100
            redirect_rate = (self.bounded_load_redirects / max(self.total_requests, 1)) * 100
            warmup_redirect_rate = (self.warmup_redirects / max(self.total_requests, 1)) * 100
            
            # Count servers in warm-up
            warmup_servers = sum(
                1 for state in self.server_state.values()
                if state['is_new'] and state['warmup_start_time']
            )
            
            return {
                'capacity_factor': self.capacity_factor,
                'warmup_duration_sec': self.warmup_duration,
                'total_requests': self.total_requests,
                'cache_hit_rate': round(cache_hit_rate, 2),
                'bounded_load_redirects': self.bounded_load_redirects,
                'redirect_rate': round(redirect_rate, 2),
                'warmup_redirects': self.warmup_redirects,
                'warmup_redirect_rate': round(warmup_redirect_rate, 2),
                'servers_in_warmup': warmup_servers,
            }
    
    def get_server_metrics(self, host, port):
        """
        Get cache-aware metrics for a specific server
        """
        server_key = f"{host}:{port}"
        with self.lock:
            if server_key not in self.server_state:
                return {}
            
            state = self.server_state[server_key]
            
            # Calculate warm-up progress
            warmup_progress = 0.0
            if state['is_new'] and state['warmup_start_time']:
                elapsed = time.time() - state['warmup_start_time']
                warmup_progress = min((elapsed / self.warmup_duration) * 100, 100.0)
            
            return {
                'total_requests': state['total_requests'],
                'cached_keys_count': len(state['recent_keys']),
                'is_warming_up': state['is_new'],
                'warmup_progress': round(warmup_progress, 1),
                'warmup_requests': state['warmup_requests'],
            }
    
    def record_response_time(self, host, port, response_time_seconds):
        """
        Record response time (for compatibility with other strategies)
        BETA1 doesn't use response time directly, but we track it for monitoring
        """
        # BETA1 focuses on cache affinity, not response time
        # This method is here for interface compatibility
        pass
