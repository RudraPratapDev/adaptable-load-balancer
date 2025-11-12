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
            # Set non-blocking mode for better handling
            client_sock.setblocking(False)
            server_sock.setblocking(False)
            
            sockets = [client_sock, server_sock]
            client_done = False
            server_done = False
            
            while not (client_done and server_done):
                # Use longer timeout to avoid premature disconnection
                ready, _, exceptional = select.select(sockets, [], sockets, 5.0)
                
                # Check for exceptional conditions
                if exceptional:
                    break
                
                # If no sockets ready after timeout, check if both sides are done
                if not ready:
                    break
                
                for sock in ready:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            # Connection closed
                            if sock is client_sock:
                                client_done = True
                            else:
                                server_done = True
                            continue
                            
                        if sock is client_sock:
                            server_sock.sendall(data)
                        else:
                            client_sock.sendall(data)
                    except socket.error as e:
                        # Handle would-block errors gracefully
                        if e.errno not in (socket.EAGAIN, socket.EWOULDBLOCK):
                            return
                    except Exception:
                        return
        except Exception:
            pass
        finally:
            # Restore blocking mode
            try:
                client_sock.setblocking(True)
            except:
                pass
            try:
                server_sock.setblocking(True)
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