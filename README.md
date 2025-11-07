# Distributed Load Balancer with Fault Tolerance (Demo)

This project demonstrates a multithreaded TCP load balancer in Python that forwards HTTP requests to multiple backend servers, with health checks, fault tolerance, and a live web dashboard. It supports Round Robin and Least Connections strategies, manual server toggling, built‑in load/stress tests, and a browser-driven delay to visualize concurrent connections.

## What’s Included
- Load balancer with strategies: Round Robin, Least Connections (with fair tie-break among ties)
- Continuous health checks and automatic failover
- Live web dashboard (status, per-server distribution, recent requests, tests)
- Backend servers that return JSON noting which server handled the request
- Optional delay via query param to visualize active connections from your browser

## Project Structure
- `run.py`: Starts the load balancer and the web dashboard (single process for LB + dashboard).
- `start.py`: Demo launcher that starts 3 backend servers and then runs `run.py`.
- `config.py`: Central configuration (listen port, strategy, health intervals, server list, timeouts).
- `backend_server.py`: Simple HTTP-like TCP server. Responds with JSON including server name and supports `?delay=ms` to simulate long requests.
- `test_load_balancer.py`: Sends requests to the load balancer for quick manual testing.
- `mininet_test.py`: Example Mininet script for simulated network testing (requires Mininet, root).
- `load_balancer/`:
  - `load_balancer.py`: Core LB server. Accepts client connections, selects backend, proxies data, collects stats.
  - `server_pool.py`: Tracks servers, health state, and connection counts.
  - `strategies.py`: Implements `RoundRobinStrategy` and `LeastConnectionsStrategy`.
  - `health_monitor.py`: Background health checks to mark servers healthy/unhealthy.
  - `proxy.py`: TCP proxying between client and backend, returns boolean success/failure.
- `web_interface/`:
  - `app.py`: Minimal HTTP server that serves the dashboard and API endpoints.
  - `templates/dashboard.html`: Single-page dashboard UI (status, distribution, requests, tests).
  - `main.py`: Alternate entry to run LB + dashboard (similar to `run.py`).

## Requirements
- Python 3.9+
- macOS/Linux (Windows likely works but not tested)

No external dependencies are required for the core demo.

## Quick Start (Recommended)
1) Start the full demo (3 backends, LB, dashboard):
```bash
python3 start.py
```
2) Open the dashboard:
- Dashboard: http://localhost:8090
- Load Balancer endpoint: http://localhost:8080

3) You can also start only the LB + dashboard (if you already run your own backends):
```bash
python3 run.py
```

## Using the Dashboard
The dashboard auto-updates every second. Key sections:
- System Status: Running state, strategy, healthy servers, uptime.
- Performance Metrics: Total requests, active connections, success rate, etc.
- Request Flow: Live recent requests list; bar showing per-server request distribution.
- Backend Servers: Cards for each server with health state, connections, failures, a mini chart, and a toggle button.
- Controls: Change strategy, Refresh, Load Test, Stress Test, Custom Test, Pause/Resume live updates.

## Demonstrations (Step-by-Step)

### Run-of-Show (quick script to demo in class)
1) Start everything
   - Terminal: `python3 start.py`
   - Open Dashboard: `http://localhost:8090`
2) Round Robin (normal, fast backends)
   - Ensure Strategy = Round Robin
   - Visit `http://localhost:8080` and refresh 5–10 times
   - Observe JSON `server` value rotates; distribution bar spreads evenly
3) Least Connections (normal, fast backends)
   - Switch Strategy = Least Connections
   - Refresh `http://localhost:8080` a few times
   - With short requests, LC may look similar to RR (few active connections)
4) Active requests (visible connections) with browser-only delay
   - Keep Strategy = Least Connections
   - Open multiple tabs quickly to `http://localhost:8080?delay=1500`
   - Watch Active Connections > 0 and distribution prefer less-busy servers
5) Delay one backend only (show LC favoring others)
   - In a terminal, set fixed delay on 8081: `curl "http://localhost:8081/control?set_delay_ms=1500"`
   - Keep refreshing `http://localhost:8080` (or run load test)
   - LC will bias toward 8082/8083 as 8081 stays busy; distribution and sparklines show shift
   - Remove delay: `curl "http://localhost:8081/control?set_delay_ms=0"`
6) Server down (fault tolerance)
   - In Dashboard → Backend Servers, click Stop Server on one server (e.g., 8083)
   - Send requests or run Load Test (50 req)
   - Traffic redistributes among remaining healthy servers; success stays high
   - Start Server to bring it back; after health checks it re-enters rotation
7) Built-in Load Test (accumulated distribution)
   - Click Load Test (50 req)
   - Read summary (total, success, avg response) and Distribution (since start)
   - Pause Live to discuss, Resume to continue
8) Built-in Stress Test (sustained concurrency)
   - Click Stress Test (30s)
   - Observe Active Connections, distribution, and sparklines over time
9) Continuous CLI traffic (optional alternative)
   - Terminal: `python3 test_load_balancer.py continuous`
   - Or shell loop: `while true; do curl -s http://localhost:8080 >/dev/null; sleep 0.2; done`
   - Toggle server off/on and/or set per-server delay to visualize adaptive balancing

### 1) Basic Round Robin
- Ensure strategy is `Round Robin` in the Strategy dropdown.
- Open http://localhost:8080 in your browser and refresh several times.
- Each response body shows the backend that handled it, e.g.
```json
{"server":"Server-1","port":8081,...}
```
- Watch the distribution bar and server colors shift evenly among servers.

### 2) Least Connections (with fair tie-break)
- In the Strategy dropdown, choose `Least Connections`.
- To make connections visible, open multiple tabs pointing to `http://localhost:8080?delay=1500` quickly.
- Active Connections > 0 while requests are in-flight.
- Least Connections favors less-busy servers; with ties, it rotates fairly among the tied servers.

### 3) Fault Tolerance (Server Down)
- In the Servers section, toggle one server off (Stop Server button).
- Keep sending requests (refresh browser or run a Load Test). Traffic automatically redistributes to the remaining healthy servers.
- Toggle the server back on to see it rejoin distribution after health checks.

### 4) Built-in Load Test
- Click `Load Test (50 req)`. The dashboard displays a summary: total, successful/failed, average response, min/max, and current distribution since start.
- Use Pause Live to freeze the view; Resume to continue.

### 5) Built-in Stress Test
- Click `Stress Test (30s)`. This spawns continuous concurrent requests for the given duration.
- The distribution bar, mini charts, and recent requests visualize the traffic.

### 6) Custom Tests
- Click `Custom Test` and enter requests and concurrency.
- Observe how strategies and server health affect distribution.

### 7) Manual Browser Delays (to visualize concurrency)
- Append `?delay=ms` to create long-lived requests from a browser. Examples:
  - `http://localhost:8080?delay=1000` (1 second)
  - `http://localhost:8080?delay=2000` (2 seconds)
- While those tabs are loading, the dashboard shows non-zero Active Connections and changing distribution.

## How It Works (Brief)
- The load balancer listens on `config['listen_port']` and forwards accepted TCP connections to a selected backend based on the current strategy.
- `health_monitor.py` pings backends periodically; unhealthy servers are excluded from selection until healthy again.
- `proxy.py` forwards bytes in both directions and returns success/failure; failures yield an HTTP 503 to the client.
- The dashboard polls the LB for status and recent request stats, then renders the UI with small visualizations.

## Tips and Troubleshooting
- Seeing only zeros for Active Connections: backends respond in ~10–50ms by default; increase concurrency or use `?delay=ms` to visualize connections.
- BrokenPipe in dashboard logs: handled gracefully (client closed before server wrote response).
- Strategy seems identical: Least Connections and Round Robin behave similarly when connections are short. Use delays or stress to observe differences.
- Resetting metrics: counters accumulate since start; restart the LB to reset. A reset endpoint can be added if needed.

## Notes on “Distributed” Claim
This demo uses a single LB process (no external HA). To remove the single point of failure, run multiple LB instances and front them with a virtual IP (e.g., keepalived/VRRP) and share server health via a store (e.g., Redis). The included `mininet_test.py` can help test such setups in simulated networks.

## Configuration
See `config.py`:
- `listen_port`: LB port (default 8080)
- `strategy`: `round_robin` or `least_connections`
- `servers`: list of `(host, port)` backend tuples
- `health_check_interval`, `timeout`: health checks / socket timeouts

## CLI Testing
- Simple test script:
```bash
python3 test_load_balancer.py
```
- Continuous tester:
```bash
python3 test_load_balancer.py continuous
```

## License
For educational/demo use.
