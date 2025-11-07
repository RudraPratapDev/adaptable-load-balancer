#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer.load_balancer import LoadBalancer
from config import get_config
from web_interface.app import WebApp


def main():
    cfg = get_config()
    
    print("Starting Load Balancer with Web Interface")
    print(f"Load Balancer Port: {cfg['listen_port']}")
    print(f"Strategy: {cfg['strategy']}")
    print(f"Health Check Interval: {cfg['health_check_interval']}s")
    
    # create and configure load balancer
    lb = LoadBalancer(cfg)
    
    # add backend servers
    print("\nBackend Servers:")
    for host, port in cfg['servers']:
        lb.add_backend_server(host, port)
        print(f"  {host}:{port}")
    
    # start web interface
    webapp = WebApp(lb, port=8090)
    webapp.start()
    
    print(f"\nWeb Dashboard: http://localhost:8090")
    print("Features:")
    print("  • Monitor real-time performance")
    print("  • Toggle servers on/off")
    print("  • Change load balancing strategies")
    print("  • Run load tests")
    
    try:
        print("\nStarting load balancer...")
        lb.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        lb.stop()
        webapp.stop()
        print("Shutdown complete")


if __name__ == "__main__":
    main()