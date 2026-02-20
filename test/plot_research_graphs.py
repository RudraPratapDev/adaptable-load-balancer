import sys
import os
import time
import threading
import statistics
import random
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid threading issues
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer.server_pool import ServerPool
from load_balancer.strategies import (
    RoundRobinStrategy,
    LeastConnectionsStrategy,
    ResponseTimeBasedStrategy,
    ALPHA1Strategy,
    BETA1Strategy
)
from workload_generator import WorkloadGenerator
from mock_server import MockServer

# Set style for research papers
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 14,
    'axes.titlesize': 16,
    'axes.labelsize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 12,
    'figure.figsize': (10, 6),
    'lines.linewidth': 2.5
})

class DataCollectorSimulation:
    def __init__(self):
        self.base_num_requests = 5000  # Matches realistic_simulation_suite.py
        self.concurrent_clients = 20   # Matches realistic_simulation_suite.py
        
    def setup_environment(self, scenario_name):
        """Setup servers and pool based on scenario requirements"""
        pool = ServerPool()
        servers = []
        
        if scenario_name == "Heterogeneous":
            # Server A: 1x, B: 0.7x, C: 1.3x, D: Random Spikes
            configs = [
                (8001, 1.0, 0.0),   # Server A: 1x Speed
                (8002, 0.7, 0.0),   # Server B: 0.7x Speed (Slower)
                (8003, 1.3, 0.0),   # Server C: 1.3x Speed (Faster)
                (8004, 1.0, 0.3),   # Server D: 1x Speed + 30% Interference (Spikes)
                (8005, 1.0, 0.0)    # Normal backup
            ]
            for port, speed, interference in configs:
                srv = MockServer('127.0.0.1', port, speed_multiplier=speed, interference_level=interference)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "HeavyTailed":
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port, interference_level=0.1)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "BurstTraffic":
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "PartialFailures":
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "CacheLocality":
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port, cache_size=20) 
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
        
        return pool, servers

    def run_strategy(self, scenario_name, strategy_name, strategy_cls):
        pool, servers = self.setup_environment(scenario_name)
        server_map = {f"{s.host}:{s.port}": s for s in servers}
        
        # Configure Workload
        zipf_alpha = 1.2
        if scenario_name == "HeavyTailed": zipf_alpha = 1.2
        elif scenario_name == "CacheLocality": zipf_alpha = 2.5
        
        wg = WorkloadGenerator(zipf_alpha=zipf_alpha)
        strategy = strategy_cls()
        
        # Data storage
        raw_data = [] # List of dicts: {time, latency, success, strategy}
        
        lock = threading.Lock()
        stop_event = threading.Event()
        start_time_global = time.time()
        
        def fault_injector():
            """Injects faults for Partial Failures scenario - Matches realistic_simulation_suite.py"""
            if scenario_name != "PartialFailures": return
            
            # 1. Slowdown
            time.sleep(2)
            if "127.0.0.1:8001" in server_map: 
                server_map["127.0.0.1:8001"].temporary_slowdown_factor = 1.3
            
            # 2. Packet Drops
            time.sleep(3)
            if "127.0.0.1:8002" in server_map:
                server_map["127.0.0.1:8002"].set_packet_drop_rate(0.05)
            
            # 3. Recovery
            time.sleep(3)
            if "127.0.0.1:8001" in server_map: server_map["127.0.0.1:8001"].temporary_slowdown_factor = 1.0
            if "127.0.0.1:8002" in server_map: server_map["127.0.0.1:8002"].set_packet_drop_rate(0.0)

        def client_worker(client_id):
            reqs_done = 0
            target = self.base_num_requests // self.concurrent_clients
            
            while reqs_done < target and not stop_event.is_set():
                if scenario_name == "BurstTraffic":
                    # Matches realistic_simulation_suite.py
                    if reqs_done % 100 < 20: # 20% burst
                        time.sleep(0.001) 
                    else: 
                        time.sleep(0.01)
                else:
                    time.sleep(random.uniform(0.005, 0.015))
                
                key, size = wg.generate_request()
                
                req_start = time.time()
                healthy = pool.get_healthy_servers()
                
                if not healthy:
                    with lock:
                        raw_data.append({
                            'Time': req_start - start_time_global,
                            'Latency': 0, # Or some penalty
                            'Success': False,
                            'Outcome': 'Error',
                            'Strategy': strategy_name
                        })
                    continue
                    
                if hasattr(strategy, 'select_server_with_key'):
                    selected = strategy.select_server_with_key(healthy, key)
                else:
                    selected = strategy.select_server(healthy)
                
                if not selected: continue
                
                s_key = f"{selected['host']}:{selected['port']}"
                srv = server_map.get(s_key)
                
                pool.increment_connections(selected['host'], selected['port'])
                success, lat, is_hit, reason = srv.process_request(key, size)
                pool.decrement_connections(selected['host'], selected['port'])
                
                if hasattr(strategy, 'record_response_time'):
                     strategy.record_response_time(selected['host'], selected['port'], lat / 1000.0)
                if success:
                     pool.mark_healthy(selected['host'], selected['port'])
                     pool.record_response_time(selected['host'], selected['port'], lat / 1000.0)

                with lock:
                    raw_data.append({
                        'Time': req_start - start_time_global,
                        'Latency': lat,
                        'Success': success,
                        'Outcome': 'Hit' if is_hit else ('Miss' if success else reason),
                        'Strategy': strategy_name
                    })
                
                reqs_done += 1

        threads = []
        injector = threading.Thread(target=fault_injector)
        if scenario_name == "PartialFailures": injector.start()
        
        for i in range(self.concurrent_clients):
            t = threading.Thread(target=client_worker, args=(i,))
            t.start()
            threads.append(t)
            
        for t in threads: t.join()
        if scenario_name == "PartialFailures": injector.join()
        
        return raw_data

def plot_latency_cdf(df, title, filename):
    plt.figure(figsize=(8, 5))
    sns.ecdfplot(data=df, x="Latency", hue="Strategy", linewidth=2)
    plt.title(f"{title} - Latency CDF")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Cumulative Probability")
    plt.grid(True, alpha=0.3)
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()

def plot_latency_timeline(df, title, filename):
    plt.figure(figsize=(10, 5))
    # Rolling average for smoother lines
    for strategy in df['Strategy'].unique():
        subset = df[df['Strategy'] == strategy].sort_values('Time')
        # rolling mean over 50 requests
        subset['RollingLatency'] = subset['Latency'].rolling(window=50).mean()
        plt.plot(subset['Time'], subset['RollingLatency'], label=strategy, alpha=0.8)
    
    plt.title(f"{title} - Latency Over Time")
    plt.xlabel("Time (s)")
    plt.ylabel("Latency (ms) - Rolling Avg")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()

def plot_outcome_breakdown(df, title, filename):
    plt.figure(figsize=(8, 5))
    # Count outcomes per strategy
    outcome_counts = df.groupby(['Strategy', 'Outcome']).size().reset_index(name='Count')
    
    # Calculate percentages
    total_counts = df.groupby('Strategy').size().reset_index(name='Total')
    outcome_counts = outcome_counts.merge(total_counts, on='Strategy')
    outcome_counts['Percentage'] = (outcome_counts['Count'] / outcome_counts['Total']) * 100
    
    sns.barplot(data=outcome_counts, x="Strategy", y="Percentage", hue="Outcome")
    plt.title(f"{title} - Request Outcomes")
    plt.ylabel("Percentage of Requests (%)")
    plt.legend(title="Outcome")
    plt.ylim(0, 100)
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()

def main():
    sim = DataCollectorSimulation()
    os.makedirs("test/plots/helios", exist_ok=True)
    os.makedirs("test/plots/aura", exist_ok=True)
    
    # --- HELIOS (BETA1) vs Others ---
    print("Generating HELIOS (Cache-Aware) Visualizations...")
    
    # Scenario: Cache Locality
    print("-> Running Cache Locality Scenario...")
    data_helios = []
    data_helios.extend(sim.run_strategy("CacheLocality", "Round Robin", RoundRobinStrategy))
    data_helios.extend(sim.run_strategy("CacheLocality", "Least Connections", LeastConnectionsStrategy))
    data_helios.extend(sim.run_strategy("CacheLocality", "Least Response Time", ResponseTimeBasedStrategy))
    data_helios.extend(sim.run_strategy("CacheLocality", "Helios (BETA1)", BETA1Strategy))
    
    df_helios = pd.DataFrame(data_helios)
    plot_latency_cdf(df_helios, "Cache Efficiency", "test/plots/helios/cdf_cache_locality.png")
    plot_outcome_breakdown(df_helios, "Cache Efficiency", "test/plots/helios/outcomes_cache.png")
    
    # Scenario: Burst Traffic
    print("-> Running Burst Traffic Scenario...")
    data_burst = []
    data_burst.extend(sim.run_strategy("BurstTraffic", "Round Robin", RoundRobinStrategy))
    data_burst.extend(sim.run_strategy("BurstTraffic", "Least Connections", LeastConnectionsStrategy))
    data_burst.extend(sim.run_strategy("BurstTraffic", "Least Response Time", ResponseTimeBasedStrategy))
    data_burst.extend(sim.run_strategy("BurstTraffic", "Helios (BETA1)", BETA1Strategy))
    
    df_burst = pd.DataFrame(data_burst)
    plot_latency_timeline(df_burst, "Burst Traffic Handling", "test/plots/helios/timeline_burst.png")

    # --- AURA (ALPHA1) vs Others ---
    print("\nGenerating AURA (Lateny-Aware) Visualizations...")
    
    # Scenario: Heterogeneous Servers
    print("-> Running Heterogeneous Servers Scenario...")
    data_aura = []
    data_aura.extend(sim.run_strategy("Heterogeneous", "Round Robin", RoundRobinStrategy))
    data_aura.extend(sim.run_strategy("Heterogeneous", "Least Connections", LeastConnectionsStrategy))
    data_aura.extend(sim.run_strategy("Heterogeneous", "Least Response Time", ResponseTimeBasedStrategy))
    data_aura.extend(sim.run_strategy("Heterogeneous", "Aura (ALPHA1)", ALPHA1Strategy))
    
    df_aura = pd.DataFrame(data_aura)
    plot_latency_cdf(df_aura, "Heterogeneous Servers", "test/plots/aura/cdf_heterogeneous.png")
    plot_latency_timeline(df_aura, "Load Balancing Stability", "test/plots/aura/timeline_heterogeneous.png")

    # Scenario: Partial Failures
    print("-> Running Partial Failures Scenario...")
    data_fail = []
    data_fail.extend(sim.run_strategy("PartialFailures", "Round Robin", RoundRobinStrategy))
    data_fail.extend(sim.run_strategy("PartialFailures", "Least Connections", LeastConnectionsStrategy))
    data_fail.extend(sim.run_strategy("PartialFailures", "Least Response Time", ResponseTimeBasedStrategy))
    data_fail.extend(sim.run_strategy("PartialFailures", "Aura (ALPHA1)", ALPHA1Strategy))
    
    df_fail = pd.DataFrame(data_fail)
    plot_latency_timeline(df_fail, "Failure Recovery", "test/plots/aura/timeline_failure.png")
    plot_outcome_breakdown(df_fail, "Failure Resilience", "test/plots/aura/outcomes_failure.png")

    print("\nDone! Plots saved to test/plots/helios/ and test/plots/aura/")

if __name__ == "__main__":
    main()
