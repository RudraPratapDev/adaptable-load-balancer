#!/usr/bin/env python3

import signal
import sys
from load_balancer.load_balancer import LoadBalancer
from config import get_config

def main():
    cfg = get_config()
    
    lb = LoadBalancer(cfg)
    
    # add backend servers
    for host, port in cfg['servers']:
        lb.add_backend_server(host, port)
    
    print(f"Load balancer starting on port {cfg['listen_port']}")
    print(f"Strategy: {cfg['strategy']}")
    print(f"Backend servers: {len(cfg['servers'])}")
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        print("\nShutdown signal received...")
        lb.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        lb.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        lb.stop()

if __name__ == "__main__":
    main()