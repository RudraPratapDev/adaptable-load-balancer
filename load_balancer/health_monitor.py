import socket
import threading
import time


class HealthMonitor:
    def __init__(self, server_pool, config):
        self.pool = server_pool
        self.config = config
        self.running = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        while self.running:
            servers = self.pool.get_all_servers()
            
            for srv in servers:
                self.check_server_health(srv['host'], srv['port'])
            
            time.sleep(self.config['health_check_interval'])
    
    def check_server_health(self, host, port):
        """Check server health with retry logic to avoid false negatives"""
        max_retries = 2
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config['timeout'])
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    self.pool.mark_healthy(host, port)
                    return
                
                # If first attempt failed, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
        
        # Only mark unhealthy after all retries failed
        self.pool.mark_unhealthy(host, port)