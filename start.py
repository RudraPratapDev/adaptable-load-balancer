#!/usr/bin/env python3

import subprocess
import time
import sys
import signal
import os


class LoadBalancerDemo:
    def __init__(self):
        self.processes = []
        self.running = True
    
    def start_backend_server(self, port, name):
        cmd = ['python3', 'backend_server.py', str(port), name]
        proc = subprocess.Popen(cmd)
        self.processes.append(proc)
        print(f"Started {name} on port {port}")
        return proc
    
    def start_load_balancer(self):
        cmd = ['python3', 'run.py']
        proc = subprocess.Popen(cmd)
        self.processes.append(proc)
        print("Started load balancer with web interface")
        return proc
    
    def cleanup(self):
        print("\nShutting down all services...")
        for proc in self.processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        self.processes.clear()
        print("All services stopped")
    
    def signal_handler(self, signum, frame):
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("Starting Load Balancer Demo")
        print("=" * 40)
        
        # start backend servers
        servers = [
            (8081, "Server-1"),
            (8082, "Server-2"), 
            (8083, "Server-3")
        ]
        
        for port, name in servers:
            self.start_backend_server(port, name)
            time.sleep(0.5)
        
        # wait for servers to start
        time.sleep(2)
        
        # start load balancer
        self.start_load_balancer()
        
        print("\nDemo is ready!")
        print("=" * 40)
        print("Web Dashboard: http://localhost:8090")
        print("Load Balancer: http://localhost:8080")
        print("Backend Servers:")
        for port, name in servers:
            print(f"  {name}: http://localhost:{port}")
        print("\nPress Ctrl+C to stop all services")
        print("=" * 40)
        
        # keep running until interrupted
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        self.cleanup()


if __name__ == "__main__":
    demo = LoadBalancerDemo()
    demo.run()