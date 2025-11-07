#!/usr/bin/env python3

try:
    from mininet.net import Mininet
    from mininet.topo import Topo
    from mininet.node import Host
    from mininet.cli import CLI
    from mininet.log import setLogLevel
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False
    print("Warning: Mininet not available. Install with: sudo apt-get install mininet")

import threading
import time
import socket
import sys
import subprocess

if MININET_AVAILABLE:
    class LoadBalancerTopo(Topo):
        def build(self):
            # create switch
            switch = self.addSwitch('s1')
            
            # add load balancer host
            lb_host = self.addHost('lb', ip='10.0.0.1/24')
            self.addLink(lb_host, switch)
            
            # add backend servers
            for i in range(3):
                server = self.addHost(f'server{i+1}', ip=f'10.0.0.{i+2}/24')
                self.addLink(server, switch)
            
            # add client hosts
            for i in range(3):
                client = self.addHost(f'client{i+1}', ip=f'10.0.0.{i+5}/24')
                self.addLink(client, switch)
else:
    class LoadBalancerTopo:
        pass

class BackendServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        
    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        print(f"Backend server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_sock,)).start()
            except:
                break
                
    def handle_client(self, client_sock):
        try:
            data = client_sock.recv(1024)
            if data:
                response = f"HTTP/1.1 200 OK\r\nContent-Length: 25\r\n\r\nServer {self.port} response"
                client_sock.send(response.encode())
        except:
            pass
        finally:
            client_sock.close()
            
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()

class TestClient:
    def __init__(self, lb_host, lb_port):
        self.lb_host = lb_host
        self.lb_port = lb_port
        
    def send_request(self, request_id):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.lb_host, self.lb_port))
            
            request = f"GET /test{request_id} HTTP/1.1\r\nHost: {self.lb_host}\r\n\r\n"
            sock.send(request.encode())
            
            response = sock.recv(1024)
            print(f"Request {request_id}: {response.decode().strip()}")
            
            sock.close()
            return True
        except Exception as e:
            print(f"Request {request_id} failed: {e}")
            return False
            
    def concurrent_test(self, num_requests):
        threads = []
        for i in range(num_requests):
            t = threading.Thread(target=self.send_request, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()

def setup_network():
    if not MININET_AVAILABLE:
        return None
        
    topo = LoadBalancerTopo()
    net = Mininet(topo=topo)
    net.start()
    
    print("Network topology created:")
    print("- Load Balancer: 10.0.0.1")
    print("- Server1: 10.0.0.2")
    print("- Server2: 10.0.0.3") 
    print("- Server3: 10.0.0.4")
    print("- Clients: 10.0.0.5, 10.0.0.6, 10.0.0.7")
    
    return net

def start_backend_servers(net):
    servers = []
    
    # start servers on different hosts
    for i in range(3):
        host = net.get(f'server{i+1}')
        port = 8080 + i
        
        # run server in background on mininet host
        server_code = f'''
import socket, threading
def handle(sock):
    try:
        data = sock.recv(1024)
        if data:
            resp = "HTTP/1.1 200 OK\\r\\nContent-Length: 25\\r\\n\\r\\nServer {port} response"
            sock.send(resp.encode())
    except: pass
    finally: sock.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("10.0.0.{i+2}", {port}))
s.listen(10)
print("Server {i+1} listening on port {port}")

while True:
    try:
        c, a = s.accept()
        threading.Thread(target=handle, args=(c,)).start()
    except: break
'''
        cmd = f'python3 -c "{server_code}" &'
        
        host.cmd(cmd)
        servers.append((f'10.0.0.{i+2}', port))
        
    time.sleep(2)  # let servers start
    return servers

def run_client_tests(net, lb_host='10.0.0.1', lb_port=8000):
    client_host = net.get('client1')
    
    print("\nRunning client tests...")
    
    # test single request
    single_test_code = f'''
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("{lb_host}", {lb_port}))
    s.send(b"GET /test HTTP/1.1\\r\\nHost: {lb_host}\\r\\n\\r\\n")
    resp = s.recv(1024)
    print("Single request response:", resp.decode().strip())
    s.close()
except Exception as e:
    print("Single request failed:", e)
'''
    cmd = f'python3 -c "{single_test_code}"'
    
    result = client_host.cmd(cmd)
    print(result)
    
    # test concurrent requests
    concurrent_test_code = f'''
import socket, threading, time

def send_req(req_id):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(("{lb_host}", {lb_port}))
        s.send(f"GET /test{{req_id}} HTTP/1.1\\r\\nHost: {lb_host}\\r\\n\\r\\n".encode())
        resp = s.recv(1024)
        print(f"Request {{req_id}}: {{resp.decode().strip()}}")
        s.close()
    except Exception as e:
        print(f"Request {{req_id}} failed: {{e}}")

print("\\nRunning 5 concurrent requests...")
threads = []
for i in range(5):
    t = threading.Thread(target=send_req, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
'''
    cmd = f'python3 -c "{concurrent_test_code}"'
    
    result = client_host.cmd(cmd)
    print(result)

def main():
    if not MININET_AVAILABLE:
        print("Mininet is not installed. Please install it first:")
        print("  sudo apt-get update")
        print("  sudo apt-get install mininet")
        print("\nAlternatively, use the basic test environment:")
        print("  python3 test_environment.py servers")
        sys.exit(1)
        
    setLogLevel('info')
    
    if len(sys.argv) > 1 and sys.argv[1] == 'interactive':
        # interactive mode with CLI
        net = setup_network()
        servers = start_backend_servers(net)
        
        print("\nBackend servers started:")
        for host, port in servers:
            print(f"  {host}:{port}")
            
        print("\nStarting Mininet CLI...")
        print("You can now start the load balancer manually and test")
        CLI(net)
        net.stop()
        
    else:
        # automated testing mode
        net = setup_network()
        servers = start_backend_servers(net)
        
        print("\nBackend servers started:")
        for host, port in servers:
            print(f"  {host}:{port}")
            
        print("\nWaiting for load balancer to start...")
        print("Start your load balancer on 10.0.0.1:8000 in another terminal")
        print("Then press Enter to run tests...")
        input()
        
        run_client_tests(net)
        
        print("\nTests completed. Press Enter to cleanup...")
        input()
        net.stop()

if __name__ == '__main__':
    main()