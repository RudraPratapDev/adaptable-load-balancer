import socket
import select

class NetworkProxy:
    def __init__(self, timeout=5):
        self.timeout = timeout
    
    def create_server_connection(self, server_host, server_port):
        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(self.timeout)
            srv_sock.connect((server_host, server_port))
            return srv_sock
        except:
            return None
    
    def forward_data(self, client_sock, server_sock):
        try:
            sockets = [client_sock, server_sock]
            
            while True:
                ready, _, _ = select.select(sockets, [], [], 1.0)
                if not ready:
                    break
                
                for sock in ready:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            return
                            
                        if sock is client_sock:
                            server_sock.sendall(data)
                        else:
                            client_sock.sendall(data)
                    except:
                        return
        except:
            pass
    
    def handle_connection(self, client_sock, server_host, server_port):
        server_sock = self.create_server_connection(server_host, server_port)
        if not server_sock:
            return False
        
        try:
            self.forward_data(client_sock, server_sock)
            return True
        finally:
            try:
                server_sock.close()
            except:
                pass