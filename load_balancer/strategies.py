from abc import ABC, abstractmethod
import threading
import time
from collections import defaultdict


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