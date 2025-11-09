# Distributed Load Balancer with Advanced Algorithms

This project demonstrates a production-grade multithreaded TCP load balancer in Python that implements **7 advanced load balancing algorithms**, including cutting-edge tail latency optimization (ALPHA1) and cache-aware routing (BETA1).

## 🚀 Key Features

### 7 Load Balancing Algorithms
1. **Round Robin (RR)** - Simple sequential distribution
2. **Least Connections (LC)** - Routes to server with fewest active connections
3. **Health Score Based (HS-BS)** - Considers both load and failure history
4. **Weighted Round Robin (HF-WRR)** - Adapts weights based on failure patterns
5. **Response Time Based (RRT-BS)** - Optimizes for lowest latency
6. **ALPHA1** ⭐ - Tail latency reduction with SLO-aware hedging
7. **BETA1** ⭐ - Cache-aware routing with bounded-load control

### Advanced Capabilities
- ✅ Continuous health monitoring and automatic failover
- ✅ Real-time web dashboard with algorithm-specific metrics
- ✅ Dynamic strategy switching without restart
- ✅ Built-in load and stress testing tools
- ✅ Per-server performance tracking
- ✅ Request delay simulation for testing

## 📊 Algorithm Comparison

| Algorithm | Best For | Key Metric |
|-----------|----------|------------|
| Round Robin | Simple, homogeneous servers | Equal distribution |
| Least Connections | Variable request durations | Active connections |
| Health Score | Unreliable servers | Health score (0-1) |
| Weighted RR | Failure-prone environments | Failure-based weights |
| Response Time | Latency-sensitive apps | Avg response time |
| **ALPHA1** | p99/p99.9 optimization | Tail-risk score, p99 |
| **BETA1** | Caching/stateful services | Cache hit rate |

## 🎯 New Algorithms Deep Dive

### ALPHA1 - Tail Latency Reduction
Designed to minimize p95-p99.9 latencies in heavy-tailed workloads.

**Features:**
- Two-choice sampling (power of two choices)
- Tail-risk scoring: `EWMA(work) + β×interference + γ×age`
- SLO-aware conditional hedging
- Adaptive feedback control

**Metrics:**
- work_queue_ewma, interference_signal, head_request_age
- Current p99, target p99, hedge rate
- Adaptive beta/gamma weights

**Use Cases:**
- Real-time applications with strict SLO requirements
- Microservices with variable processing times
- Systems with stragglers or noisy neighbors

### BETA1 - Cache-Aware Rendezvous Hashing
Provides strong key affinity while preventing hotspots.

**Features:**
- Rendezvous (HRW) hashing for stable key-to-server mapping
- Bounded-load admission control (prevents overload)
- Warm-up mode for graceful scaling
- Popularity-aware key tracking

**Metrics:**
- Cache hit rate, cached keys count
- Warm-up progress, bounded-load redirects
- Per-server request distribution

**Use Cases:**
- Redis/Memcached proxies
- Session-based systems
- Sharded databases
- Content delivery with caching

## 📁 Project Structure

```
├── start.py                    # Demo launcher (3 backends + LB)
├── run.py                      # LB + dashboard only
├── config.py                   # Central configuration
├── backend_server.py           # Backend server implementation
├── load_balancer/
│   ├── load_balancer.py       # Core LB with stats tracking
│   ├── strategies.py          # All 7 algorithms
│   ├── server_pool.py         # Server state management
│   ├── health_monitor.py      # Background health checks
│   └── proxy.py               # TCP proxying logic
├── web_interface/
│   ├── app.py                 # HTTP server + API endpoints
│   └── templates/
│       └── dashboard.html     # Real-time dashboard UI
├── ALPHA1_IMPLEMENTATION.md   # ALPHA1 detailed docs
├── BETA1_IMPLEMENTATION.md    # BETA1 detailed docs
└── ALGORITHMS_COMPARISON.md   # Complete algorithm comparison
```

## 🚀 Quick Start

### 1. Start the Full Demo
```bash
python start.py
```

This starts:
- 3 backend servers (ports 8081, 8082, 8083)
- Load balancer (port 8080)
- Web dashboard (port 8090)

### 2. Access the Dashboard
Open http://localhost:8090 in your browser

### 3. Test Load Balancing
```bash
# Send requests
curl http://localhost:8080

# Or use the built-in tester
python test_load_balancer.py
```

## 🎮 Using the Dashboard

The dashboard provides:
- **System Status**: Running state, strategy, healthy servers, uptime
- **Performance Metrics**: Total requests, active connections, success rate
- **Request Flow**: Live request visualization and distribution
- **Backend Servers**: Per-server metrics with health status
- **Algorithm Controls**: Switch strategies, run tests, view algorithm-specific metrics

### Switching Algorithms

**Via Dashboard:**
1. Select algorithm from dropdown
2. Click "Update"

**Via API:**
```bash
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"alpha1"}'
```

Available strategies: `round_robin`, `least_connections`, `health_score`, `weighted_round_robin`, `response_time`, `alpha1`, `beta1`

## 🧪 Testing Algorithms

### Test ALPHA1 (Tail Latency)
```bash
# Create a slow server
curl "http://localhost:8081/control?set_delay_ms=2000"

# Send requests - ALPHA1 should avoid the slow server
for i in {1..50}; do curl -s http://localhost:8080; done

# Check p99 metrics
curl http://localhost:8090/api/algorithm-metrics | jq '.alpha1_global'
```

### Test BETA1 (Cache Affinity)
```bash
# Send requests - same keys should route to same servers
for i in {1..100}; do curl -s http://localhost:8080; done

# Check cache hit rate
curl http://localhost:8090/api/algorithm-metrics | jq '.beta1_global.cache_hit_rate'
```

### Built-in Load Test
```bash
curl -X POST http://localhost:8090/api/load-test \
  -H "Content-Type: application/json" \
  -d '{"requests":100,"concurrent":10}'
```

### Built-in Stress Test
```bash
curl -X POST http://localhost:8090/api/stress-test \
  -H "Content-Type: application/json" \
  -d '{"duration":30,"concurrent":50}'
```

## ⚙️ Configuration

Edit `config.py`:

```python
config = {
    'listen_port': 8080,
    'strategy': 'alpha1',  # Choose your algorithm
    'health_check_interval': 5,
    'max_failures': 3,
    'timeout': 3,
    'servers': [
        ('127.0.0.1', 8081),
        ('127.0.0.1', 8082),
        ('127.0.0.1', 8083)
    ]
}
```

## 📊 API Endpoints

- `GET /api/status` - Load balancer status
- `GET /api/servers` - Server list with health
- `GET /api/performance` - Performance metrics
- `GET /api/algorithm-metrics` - Algorithm-specific metrics
- `POST /api/strategy` - Change algorithm
- `POST /api/servers/toggle` - Enable/disable server
- `POST /api/load-test` - Run load test
- `POST /api/stress-test` - Run stress test

## 📈 Monitoring Metrics

### Global Metrics (All Algorithms)
- Total requests, successful/failed requests
- Active connections, success rate
- Requests per minute, average response time
- Per-server request distribution

### ALPHA1-Specific Metrics
- work_queue_ewma, interference_signal, head_request_age
- Current p99, target p99, SLO threshold
- Beta/gamma adaptive weights
- Hedge rate

### BETA1-Specific Metrics
- Cache hit rate, cached keys count
- Bounded-load redirects, redirect rate
- Warm-up progress, servers in warm-up
- Per-server request totals

## 🎯 Use Case Recommendations

| Use Case | Recommended Algorithm |
|----------|----------------------|
| E-commerce / Web Apps | Least Connections, Response Time |
| Microservices with Caching | **BETA1** |
| Real-Time / Gaming | **ALPHA1**, Response Time |
| API Gateway | Health Score, Weighted RR |
| Database Proxy / Sharding | **BETA1** |
| CDN / Content Delivery | **BETA1**, Response Time |
| Batch Processing | Round Robin, Least Connections |

## 📚 Documentation

- **[ALPHA1_IMPLEMENTATION.md](ALPHA1_IMPLEMENTATION.md)** - Complete ALPHA1 documentation
- **[BETA1_IMPLEMENTATION.md](BETA1_IMPLEMENTATION.md)** - Complete BETA1 documentation
- **[ALGORITHMS_COMPARISON.md](ALGORITHMS_COMPARISON.md)** - Detailed algorithm comparison
- **[DEMO_GUIDE.md](DEMO_GUIDE.md)** - Step-by-step demo scenarios

## 🔬 Research Background

### ALPHA1 References
- Power of Two Choices: Mitzenmacher (1996)
- Tail Latency Control: Dean & Barroso (2013)
- C3 Hedging System: Vulimiri et al. (2015)

### BETA1 References
- Rendezvous Hashing: Thaler & Ravishankar (1998)
- Consistent Hashing with Bounded Loads: Mirrokni et al. (2018)
- Cache-Aware Load Balancing: Berger et al. (2017)

## 🛠️ Requirements

- Python 3.9+
- No external dependencies for core functionality
- Optional: `requests`, `pytest` for testing

## 🚀 Advanced Features

### Backend Server Delay Control
```bash
# Set fixed delay on a specific server
curl "http://localhost:8081/control?set_delay_ms=1500"

# Or use query parameter for per-request delay
curl "http://localhost:8080?delay=1000"
```

### Manual Server Control
```bash
# Disable a server
curl -X POST http://localhost:8090/api/servers/toggle \
  -H "Content-Type: application/json" \
  -d '{"host":"127.0.0.1","port":8081}'
```

## 🎓 Educational Value

This project demonstrates:
- Advanced load balancing algorithms from research papers
- Real-world tail latency optimization techniques
- Cache-aware routing with bounded-load guarantees
- Production-grade monitoring and observability
- Dynamic algorithm switching
- Comprehensive testing methodologies

## 📝 License

For educational and demonstration purposes.

## 🤝 Contributing

This is a demonstration project showcasing advanced load balancing algorithms. Feel free to:
- Experiment with different algorithms
- Tune algorithm parameters
- Add new algorithms
- Improve monitoring and visualization

## 🎉 Highlights

- **Production-Ready**: Thread-safe, fault-tolerant, with comprehensive error handling
- **Research-Based**: Implements algorithms from peer-reviewed papers
- **Observable**: Rich metrics and real-time dashboard
- **Flexible**: Dynamic strategy switching, configurable parameters
- **Educational**: Well-documented with detailed algorithm explanations
- **Testable**: Built-in load/stress testing tools

---

**Start exploring advanced load balancing today!**

```bash
python start.py
# Open http://localhost:8090
# Select ALPHA1 or BETA1 from the dropdown
# Watch the magic happen! ✨
```
