config = {
    'listen_port': 8080,
    'strategy': 'round_robin',  # Options: round_robin, least_connections, health_score, weighted_round_robin, response_time
    'health_check_interval': 5,
    'max_failures': 3,
    'timeout': 3,
    'max_connections': 200,
    'buffer_size': 4096,
    'connection_pool_size': 10,
    'servers': [
        ('127.0.0.1', 8081),
        ('127.0.0.1', 8082),
        ('127.0.0.1', 8083)
    ]
}

def get_config():
    return config