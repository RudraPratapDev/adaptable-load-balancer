#!/usr/bin/env python3

import json
import threading
import time
import concurrent.futures
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import socket
import os


class WebAppHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, load_balancer=None, **kwargs):
        self.lb = load_balancer
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/api/status':
            self.serve_status()
        elif path == '/api/servers':
            self.serve_servers()
        elif path == '/api/performance':
            self.serve_performance()
        elif path == '/api/realtime':
            self.serve_realtime_data()
        elif path == '/api/requests':
            self.serve_recent_requests()
        elif path == '/api/algorithm-metrics':
            self.serve_algorithm_metrics()
        elif path.startswith('/static/'):
            self.serve_static(path)
        else:
            self.send_error(404)
    
    def do_POST(self):
        path = urlparse(self.path).path
        
        if path == '/api/servers/toggle':
            self.toggle_server()
        elif path == '/api/strategy':
            self.change_strategy()
        elif path == '/api/load-test':
            self.run_load_test()
        elif path == '/api/stress-test':
            self.run_stress_test()
        else:
            self.send_error(404)
    
    def serve_dashboard(self):
        with open(os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html'), 'r') as f:
            html = f.read()
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_status(self):
        if self.lb:
            status = self.lb.get_status()
        else:
            status = {'running': False, 'error': 'Load balancer not available'}
        
        self.send_json_response(status)
    
    def serve_servers(self):
        if self.lb:
            servers = self.lb.pool.get_all_servers()
            response = {'servers': servers}
        else:
            response = {'servers': []}
        
        self.send_json_response(response)
    
    def serve_performance(self):
        if self.lb:
            perf = self.lb.get_performance_stats()
        else:
            perf = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'active_connections': 0,
                'uptime_seconds': 0,
                'success_rate': 100.0,
                'avg_response_time_ms': 0,
                'requests_per_minute': 0,
                'server_request_counts': {},
                'recent_requests': []
            }
        
        self.send_json_response(perf)
    
    def serve_realtime_data(self):
        # combined endpoint for real-time updates
        data = {
            'timestamp': time.time(),
            'status': self.lb.get_status() if self.lb else {'running': False},
            'performance': self.lb.get_performance_stats() if self.lb else {},
            'servers': self.lb.pool.get_all_servers() if self.lb else []
        }
        self.send_json_response(data)
    
    def serve_recent_requests(self):
        if self.lb:
            stats = self.lb.get_performance_stats()
            data = {
                'recent_requests': stats.get('recent_requests', []),
                'server_request_counts': stats.get('server_request_counts', {}),
                'timestamp': time.time()
            }
        else:
            data = {
                'recent_requests': [],
                'server_request_counts': {},
                'timestamp': time.time()
            }
        self.send_json_response(data)
    
    def serve_algorithm_metrics(self):
        """Serve algorithm-specific metrics"""
        if not self.lb:
            self.send_json_response({'error': 'Load balancer not available'})
            return
        
        strategy_name = self.lb.config.get('strategy', 'round_robin')
        servers = self.lb.pool.get_all_servers()
        
        metrics = {
            'strategy': strategy_name,
            'servers': []
        }
        
        # Add algorithm-specific metrics for each server
        for srv in servers:
            server_metrics = {
                'host': srv['host'],
                'port': srv['port'],
                'healthy': srv['healthy'],
                'connections': srv['connections'],
                'failures': srv['failures']
            }
            
            # Add health score for HS-BS
            if strategy_name == 'health_score':
                connection_factor = 1 / (1 + srv['connections'])
                failure_factor = 1 / (1 + srv['failures'])
                health_score = connection_factor * failure_factor
                server_metrics['health_score'] = round(health_score, 3)
            
            # Add weight for HF-WRR
            elif strategy_name == 'weighted_round_robin':
                if srv['failures'] == 0:
                    weight = 10
                elif srv['failures'] == 1:
                    weight = 5
                else:
                    weight = 1
                server_metrics['weight'] = weight
            
            # Add response time for RRT-BS
            elif strategy_name == 'response_time':
                avg_response_time = self.lb.pool.get_average_response_time(srv['host'], srv['port'])
                server_metrics['avg_response_time'] = round(avg_response_time * 1000, 2)  # Convert to ms
            
            metrics['servers'].append(server_metrics)
        
        self.send_json_response(metrics)
    
    def toggle_server(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        host = data.get('host')
        port = data.get('port')
        
        if self.lb and host and port:
            srv_info = self.lb.pool.get_server_info(host, port)
            if srv_info:
                if srv_info['healthy']:
                    self.lb.pool.manually_disable_server(host, port)
                    result = {'success': True, 'action': 'stopped', 'server': f'{host}:{port}'}
                else:
                    self.lb.pool.manually_enable_server(host, port)
                    result = {'success': True, 'action': 'started', 'server': f'{host}:{port}'}
            else:
                result = {'success': False, 'error': 'Server not found'}
        else:
            result = {'success': False, 'error': 'Invalid request'}
        
        self.send_json_response(result)
    
    def change_strategy(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        strategy = data.get('strategy')
        valid_strategies = ['round_robin', 'least_connections', 'health_score', 'weighted_round_robin', 'response_time']
        
        if self.lb and strategy in valid_strategies:
            self.lb.config['strategy'] = strategy
            
            # update strategy instance
            if strategy == 'least_connections':
                from load_balancer.strategies import LeastConnectionsStrategy
                self.lb.strategy = LeastConnectionsStrategy()
            elif strategy == 'health_score':
                from load_balancer.strategies import HealthScoreBasedStrategy
                self.lb.strategy = HealthScoreBasedStrategy()
            elif strategy == 'weighted_round_robin':
                from load_balancer.strategies import HistoricalFailureWeightedRoundRobin
                self.lb.strategy = HistoricalFailureWeightedRoundRobin()
            elif strategy == 'response_time':
                from load_balancer.strategies import ResponseTimeBasedStrategy
                self.lb.strategy = ResponseTimeBasedStrategy()
            else:
                from load_balancer.strategies import RoundRobinStrategy
                self.lb.strategy = RoundRobinStrategy()
            
            result = {'success': True, 'strategy': strategy}
        else:
            result = {'success': False, 'error': 'Invalid strategy'}
        
        self.send_json_response(result)
    
    def run_load_test(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        requests = data.get('requests', 50)
        concurrent_workers = data.get('concurrent', 10)
        
        result = self._execute_load_test(requests, concurrent_workers)
        self.send_json_response(result)
    
    def run_stress_test(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        duration = data.get('duration', 30)  # seconds
        concurrent_workers = data.get('concurrent', 50)
        
        result = self._execute_stress_test(duration, concurrent_workers)
        self.send_json_response(result)
    
    def _execute_load_test(self, requests, concurrent_workers):
        def make_request():
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                
                # Connect to load balancer
                result = sock.connect_ex(('127.0.0.1', self.lb.config['listen_port']))
                if result != 0:
                    sock.close()
                    return None
                
                # Send HTTP request
                request = b'GET /loadtest HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
                sock.send(request)
                
                # Read response with timeout
                response = b''
                sock.settimeout(5)
                try:
                    while True:
                        data = sock.recv(4096)
                        if not data:
                            break
                        response += data
                        # Break if we got a complete HTTP response
                        if b'\r\n\r\n' in response:
                            break
                except socket.timeout:
                    pass
                
                sock.close()
                duration = time.time() - start
                
                # Check if we got a valid response
                if len(response) > 0:
                    return duration
                else:
                    return None
                    
            except Exception as e:
                print(f"Load test request error: {e}")
                return None
        
        start_time = time.time()
        successful = 0
        failed = 0
        response_times = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = [executor.submit(make_request) for _ in range(requests)]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result is not None:
                    successful += 1
                    response_times.append(result)
                else:
                    failed += 1
        
        duration = time.time() - start_time
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'test_type': 'load_test',
            'total_requests': requests,
            'successful': successful,
            'failed': failed,
            'avg_response_time': round(avg_response_time * 1000, 2),
            'min_response_time': round(min(response_times) * 1000, 2) if response_times else 0,
            'max_response_time': round(max(response_times) * 1000, 2) if response_times else 0,
            'duration': round(duration, 2),
            'requests_per_second': round(requests / duration, 2)
        }
    
    def _execute_stress_test(self, duration, concurrent_workers):
        def continuous_requests(stop_event):
            requests = 0
            successful = 0
            response_times = []
            
            while not stop_event.is_set():
                try:
                    start = time.time()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    
                    result = sock.connect_ex(('127.0.0.1', self.lb.config['listen_port']))
                    if result == 0:
                        request = b'GET /stresstest HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
                        sock.send(request)
                        
                        # Try to read response
                        try:
                            data = sock.recv(1024)
                            if data:
                                response_times.append(time.time() - start)
                                successful += 1
                        except:
                            pass
                    
                    sock.close()
                except:
                    pass
                
                requests += 1
                time.sleep(0.05)  # Small delay to prevent overwhelming
            
            return requests, successful, response_times
        
        stop_event = threading.Event()
        
        # start stress test threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = [executor.submit(continuous_requests, stop_event) for _ in range(concurrent_workers)]
            
            # let it run for specified duration
            time.sleep(duration)
            stop_event.set()
            
            # collect results
            total_requests = 0
            total_successful = 0
            all_response_times = []
            
            for future in concurrent.futures.as_completed(futures):
                requests, successful, response_times = future.result()
                total_requests += requests
                total_successful += successful
                all_response_times.extend(response_times)
        
        avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
        
        return {
            'test_type': 'stress_test',
            'duration': duration,
            'concurrent_users': concurrent_workers,
            'total_requests': total_requests,
            'successful': total_successful,
            'failed': total_requests - total_successful,
            'avg_response_time': round(avg_response_time * 1000, 2),
            'requests_per_second': round(total_requests / duration, 2),
            'success_rate': round(total_successful / max(total_requests, 1) * 100, 1)
        }
    
    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
    
    def log_message(self, format, *args):
        # suppress default logging
        pass


class WebApp:
    def __init__(self, load_balancer, port=8090):
        self.lb = load_balancer
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        def handler(*args, **kwargs):
            return WebAppHandler(*args, load_balancer=self.lb, **kwargs)
        
        self.server = HTTPServer(('0.0.0.0', self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        print(f"Web Dashboard: http://localhost:{self.port}")
    
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()