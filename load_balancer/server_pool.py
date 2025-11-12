import threading
from datetime import datetime
from collections import defaultdict


class ServerPool:
    def __init__(self):
        self.servers = {}
        self.lock = threading.Lock()
        self.manually_disabled = set()  # Track manually disabled servers
        self.response_times = defaultdict(list)  # Track response times for each server
    
    def add_server(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            self.servers[key] = {
                'host': host,
                'port': port,
                'healthy': True,
                'connections': 0,
                'failures': 0
            }
    
    def get_healthy_servers(self):
        with self.lock:
            return [srv for srv in self.servers.values() if srv['healthy']]
    
    def mark_unhealthy(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            if key in self.servers:
                self.servers[key]['failures'] += 1
                # Only mark unhealthy after multiple consecutive failures
                if self.servers[key]['failures'] >= 3:
                    self.servers[key]['healthy'] = False
    
    def mark_healthy(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            if key in self.servers:
                # Don't mark healthy if manually disabled
                if key not in self.manually_disabled:
                    self.servers[key]['healthy'] = True
                    self.servers[key]['failures'] = 0
    
    def manually_disable_server(self, host, port):
        """Manually disable a server (won't be re-enabled by health monitor)"""
        with self.lock:
            key = f"{host}:{port}"
            self.manually_disabled.add(key)
            if key in self.servers:
                self.servers[key]['healthy'] = False
    
    def manually_enable_server(self, host, port):
        """Manually enable a server"""
        with self.lock:
            key = f"{host}:{port}"
            self.manually_disabled.discard(key)
            if key in self.servers:
                self.servers[key]['healthy'] = True
                self.servers[key]['failures'] = 0
    
    def increment_connections(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            if key in self.servers:
                self.servers[key]['connections'] += 1
    
    def decrement_connections(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            if key in self.servers and self.servers[key]['connections'] > 0:
                self.servers[key]['connections'] -= 1
    
    def get_server_info(self, host, port):
        with self.lock:
            key = f"{host}:{port}"
            return self.servers.get(key, None)
    
    def get_all_servers(self):
        with self.lock:
            servers = []
            for srv in self.servers.values():
                key = f"{srv['host']}:{srv['port']}"
                servers.append({
                    'host': srv['host'],
                    'port': srv['port'],
                    'healthy': srv['healthy'],
                    'connections': srv['connections'],
                    'failures': srv['failures'],
                    'manually_disabled': key in self.manually_disabled
                })
            return servers
    
    def all_servers_down(self):
        with self.lock:
            if not self.servers:
                return False
            return not any(srv['healthy'] for srv in self.servers.values())
    
    def record_response_time(self, host, port, response_time):
        """Record response time for a server"""
        with self.lock:
            key = f"{host}:{port}"
            self.response_times[key].append(response_time)
            # Keep only recent 100 response times
            if len(self.response_times[key]) > 100:
                self.response_times[key].pop(0)
    
    def get_average_response_time(self, host, port):
        """Get average response time for a server"""
        with self.lock:
            key = f"{host}:{port}"
            if key not in self.response_times or not self.response_times[key]:
                return 0.0
            times = self.response_times[key]
            return sum(times) / len(times)