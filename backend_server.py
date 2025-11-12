#!/usr/bin/env python3

import socket
import threading
import time
import sys
import random
import json


class BackendServer:
    def __init__(self, port, name=None):
        self.port = port
        self.name = name or f"Server-{port}"
        self.running = False
        self.server_sock = None
        self.connections = 0
        self.total_requests = 0
        self.fixed_delay_ms = 0
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Increase backlog to handle more concurrent connections
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        try:
            self.server_sock.bind(('0.0.0.0', self.port))
            self.server_sock.listen(50)  # Increased from 10 to 50
            print(f"{self.name} listening on port {self.port}")
            
            while self.running:
                try:
                    self.server_sock.settimeout(1.0)  # Make it interruptible
                    client_sock, addr = self.server_sock.accept()
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_sock, addr),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue  # Check if still running
                except socket.error:
                    if self.running:
                        continue
                    break
        except Exception as e:
            print(f"Error starting {self.name}: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_sock, addr):
        self.connections += 1
        self.total_requests += 1
        
        try:
            # read request
            request = client_sock.recv(1024).decode('utf-8')
            
            # parse optional ?delay=ms from the request line
            delay_ms = 0
            try:
                first_line = request.splitlines()[0] if request else ""
                path = first_line.split(" ")[1] if " " in first_line else ""
                # Handle control endpoint to set fixed delay
                if path.startswith('/control'):
                    import urllib.parse as up
                    qs = up.urlparse(path).query
                    params = up.parse_qs(qs)
                    if 'set_delay_ms' in params and params['set_delay_ms']:
                        try:
                            self.fixed_delay_ms = max(0, int(params['set_delay_ms'][0]))
                        except Exception:
                            pass
                    # respond and return early (no normal processing)
                    resp = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    )
                    body = json.dumps({"server": self.name, "fixed_delay_ms": self.fixed_delay_ms})
                    client_sock.sendall(resp.encode('utf-8') + body.encode('utf-8'))
                    return
                if "delay=" in path:
                    import urllib.parse as up
                    qs = up.urlparse(path).query
                    params = up.parse_qs(qs)
                    if 'delay' in params and params['delay']:
                        delay_ms = int(params['delay'][0])
            except Exception:
                pass

            # simulate some processing time (base + optional delay)
            processing_time = random.uniform(0.01, 0.05)
            total_delay_ms = (delay_ms if delay_ms > 0 else 0) + (self.fixed_delay_ms if self.fixed_delay_ms > 0 else 0)
            if total_delay_ms > 0:
                time.sleep(total_delay_ms / 1000.0)
            else:
                time.sleep(processing_time)
            
            # send response
            body = json.dumps({
                "server": self.name,
                "port": self.port,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "request_id": self.total_requests,
                "processing_time": round(processing_time, 3),
                "applied_delay_ms": delay_ms,
                "fixed_delay_ms": self.fixed_delay_ms
            })
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                f"X-Backend: {self.name}:{self.port}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            client_sock.sendall(headers.encode('utf-8') + body.encode('utf-8'))
            
        except Exception as e:
            print(f"{self.name} error handling client: {e}")
        finally:
            client_sock.close()
            self.connections -= 1
    
    def stop(self):
        if not self.running:
            return
        
        print(f"Stopping {self.name}...")
        self.running = False
        
        if self.server_sock:
            self.server_sock.close()
    
    def get_stats(self):
        return {
            'name': self.name,
            'port': self.port,
            'running': self.running,
            'connections': self.connections,
            'total_requests': self.total_requests
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python backend_server.py <port> [name]")
        sys.exit(1)
    
    port = int(sys.argv[1])
    name = sys.argv[2] if len(sys.argv) > 2 else None
    
    server = BackendServer(port, name)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print(f"\nShutting down {server.name}...")
        server.stop()


if __name__ == "__main__":
    main()