import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime

from .server_pool import ServerPool
from .strategies import (RoundRobinStrategy, LeastConnectionsStrategy, 
                        HealthScoreBasedStrategy, HistoricalFailureWeightedRoundRobin,
                        ResponseTimeBasedStrategy, ALPHA1Strategy, BETA1Strategy)
from .health_monitor import HealthMonitor
from .proxy import NetworkProxy


class LoadBalancer:
    def __init__(self, config):
        self.config = config
        self.pool = ServerPool()
        self.proxy = NetworkProxy(timeout=config['timeout'])
        self.monitor = HealthMonitor(self.pool, config)
        
        # Initialize strategy based on config
        strategy_name = config['strategy']
        if strategy_name == 'least_connections':
            self.strategy = LeastConnectionsStrategy()
        elif strategy_name == 'health_score':
            self.strategy = HealthScoreBasedStrategy()
        elif strategy_name == 'weighted_round_robin':
            self.strategy = HistoricalFailureWeightedRoundRobin()
        elif strategy_name == 'response_time':
            self.strategy = ResponseTimeBasedStrategy()
        elif strategy_name == 'alpha1':
            self.strategy = ALPHA1Strategy()
        elif strategy_name == 'beta1':
            self.strategy = BETA1Strategy()
        else:
            self.strategy = RoundRobinStrategy()
        
        self.running = False
        self.server_sock = None
        self.executor = ThreadPoolExecutor(max_workers=100)
        
        self.stats = {
            'total_requests': 0,
            'active_connections': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'start_time': datetime.now(),
            'recent_requests': [],  # Track recent requests for visualization
            'server_request_counts': {}  # Track requests per server
        }
        self.stats_lock = threading.Lock()
    
    def add_backend_server(self, host, port):
        self.pool.add_server(host, port)
        print(f"Added backend server {host}:{port}")
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.monitor.start_monitoring()
        
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(('0.0.0.0', self.config['listen_port']))
        self.server_sock.listen(50)
        
        print(f"Load balancer listening on port {self.config['listen_port']}")
        print("Press Ctrl+C to stop")
        
        try:
            while self.running:
                try:
                    self.server_sock.settimeout(1.0)  # Add timeout to make it interruptible
                    client_sock, addr = self.server_sock.accept()
                    self.executor.submit(self.handle_client, client_sock, addr)
                except socket.timeout:
                    continue  # Check if still running
                except socket.error:
                    if self.running:
                        continue
                    break
        except KeyboardInterrupt:
            print("\nReceived interrupt signal...")
        finally:
            self.stop()
    
    def handle_client(self, client_sock, addr):
        request_start = time.time()
        
        with self.stats_lock:
            self.stats['total_requests'] += 1
            self.stats['active_connections'] += 1
        
        success = False
        selected_server = None
        
        try:
            if self.pool.all_servers_down():
                self.send_error_response(client_sock)
                with self.stats_lock:
                    self.stats['failed_requests'] += 1
                return
            
            srv = self.get_next_server()
            if not srv:
                self.send_error_response(client_sock)
                with self.stats_lock:
                    self.stats['failed_requests'] += 1
                return
            
            selected_server = f"{srv['host']}:{srv['port']}"
            self.pool.increment_connections(srv['host'], srv['port'])
            
            try:
                ok = self.proxy.handle_connection(client_sock, srv['host'], srv['port'])
                if ok:
                    success = True
                    with self.stats_lock:
                        self.stats['successful_requests'] += 1
                else:
                    self.send_error_response(client_sock)
                    with self.stats_lock:
                        self.stats['failed_requests'] += 1
            except Exception as e:
                print(f"Proxy error: {e}")
                with self.stats_lock:
                    self.stats['failed_requests'] += 1
            finally:
                self.pool.decrement_connections(srv['host'], srv['port'])
                
        finally:
            request_end = time.time()
            
            # Track request for visualization
            with self.stats_lock:
                self.stats['active_connections'] -= 1
                
                # Track recent requests (keep last 100)
                request_info = {
                    'timestamp': request_end,
                    'server': selected_server,
                    'success': success,
                    'duration': request_end - request_start,
                    'client': f"{addr[0]}:{addr[1]}" if addr else "unknown"
                }
                self.stats['recent_requests'].append(request_info)
                if len(self.stats['recent_requests']) > 100:
                    self.stats['recent_requests'].pop(0)
                
                # Track server request counts
                if selected_server:
                    if selected_server not in self.stats['server_request_counts']:
                        self.stats['server_request_counts'][selected_server] = 0
                    self.stats['server_request_counts'][selected_server] += 1
                
                # Record response time for ResponseTimeBasedStrategy and ALPHA1Strategy
                if success and selected_server:
                    host, port = selected_server.split(':')
                    response_time = request_end - request_start
                    self.pool.record_response_time(host, int(port), response_time)
                    
                    # Also record in strategy if it supports response time tracking
                    if isinstance(self.strategy, (ResponseTimeBasedStrategy, ALPHA1Strategy)):
                        self.strategy.record_response_time(host, int(port), response_time)
            
            try:
                client_sock.close()
            except:
                pass
    
    def get_next_server(self):
        healthy_servers = self.pool.get_healthy_servers()
        if not healthy_servers:
            return None
        return self.strategy.select_server(healthy_servers)
    
    def send_error_response(self, client_sock):
        try:
            response = "HTTP/1.1 503 Service Unavailable\r\n\r\nService Unavailable"
            client_sock.send(response.encode())
        except:
            pass
    
    def stop(self):
        if not self.running:
            return
            
        print("Stopping load balancer...")
        self.running = False
        
        # Stop health monitoring
        self.monitor.stop_monitoring()
        
        # Close server socket
        if self.server_sock:
            try:
                self.server_sock.close()
            except:
                pass
        
        # Shutdown executor
        try:
            self.executor.shutdown(wait=True)
        except:
            pass
        
        print("Load balancer stopped")
    
    def get_performance_stats(self):
        with self.stats_lock:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            
            # Calculate success rate
            total = self.stats['successful_requests'] + self.stats['failed_requests']
            success_rate = (self.stats['successful_requests'] / max(total, 1)) * 100
            
            # Calculate average response time from recent requests
            recent_times = [r['duration'] for r in self.stats['recent_requests'] if r['success']]
            avg_response_time = (sum(recent_times) / len(recent_times)) * 1000 if recent_times else 0
            
            return {
                'total_requests': self.stats['total_requests'],
                'successful_requests': self.stats['successful_requests'],
                'failed_requests': self.stats['failed_requests'],
                'active_connections': self.stats['active_connections'],
                'uptime_seconds': round(uptime, 1),
                'success_rate': round(success_rate, 1),
                'avg_response_time_ms': round(avg_response_time, 2),
                'requests_per_minute': round((self.stats['total_requests'] / max(uptime/60, 1)), 1),
                'server_request_counts': dict(self.stats['server_request_counts']),
                'recent_requests': list(self.stats['recent_requests'][-10:])  # Last 10 requests
            }
    
    def get_status(self):
        servers = self.pool.get_all_servers()
        healthy_count = len(self.pool.get_healthy_servers())
        
        return {
            'running': self.running,
            'strategy': self.config['strategy'],
            'total_servers': len(servers),
            'healthy_servers': healthy_count
        }