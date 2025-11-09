# Quick Reference Guide

## 🚀 Starting the System

```bash
# Start everything (3 backends + load balancer + dashboard)
python start.py

# Or start just load balancer + dashboard (if backends already running)
python run.py
```

**Access Points:**
- Dashboard: http://localhost:8090
- Load Balancer: http://localhost:8080
- Backend Servers: http://localhost:8081, 8082, 8083

## 🎯 Switching Algorithms

### Via Dashboard
1. Open http://localhost:8090
2. Select algorithm from dropdown
3. Click "Update"

### Via API
```bash
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"STRATEGY_NAME"}'
```

### Available Strategies
- `round_robin` - Simple sequential distribution
- `least_connections` - Routes to least busy server
- `health_score` - Considers load + failures
- `weighted_round_robin` - Failure-based weights
- `response_time` - Optimizes for speed
- `alpha1` - Tail latency reduction ⭐
- `beta1` - Cache affinity ⭐

## 📊 Viewing Metrics

### System Status
```bash
curl http://localhost:8090/api/status
```

### Performance Metrics
```bash
curl http://localhost:8090/api/performance
```

### Algorithm-Specific Metrics
```bash
curl http://localhost:8090/api/algorithm-metrics | jq
```

### Server Health
```bash
curl http://localhost:8090/api/servers
```

## 🧪 Testing

### Send Single Request
```bash
curl http://localhost:8080
```

### Send Multiple Requests
```bash
for i in {1..20}; do curl -s http://localhost:8080 | jq -r '.server'; done
```

### Load Test (Built-in)
```bash
curl -X POST http://localhost:8090/api/load-test \
  -H "Content-Type: application/json" \
  -d '{"requests":100,"concurrent":10}'
```

### Stress Test (Built-in)
```bash
curl -X POST http://localhost:8090/api/stress-test \
  -H "Content-Type: application/json" \
  -d '{"duration":30,"concurrent":50}'
```

## 🎮 Testing Specific Algorithms

### Test ALPHA1 (Tail Latency)
```bash
# 1. Switch to ALPHA1
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"alpha1"}'

# 2. Create a slow server
curl "http://localhost:8081/control?set_delay_ms=2000"

# 3. Send requests
for i in {1..50}; do curl -s http://localhost:8080; done

# 4. Check p99 metrics
curl http://localhost:8090/api/algorithm-metrics | jq '.alpha1_global'
```

### Test BETA1 (Cache Affinity)
```bash
# 1. Switch to BETA1
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"beta1"}'

# 2. Send requests
for i in {1..100}; do curl -s http://localhost:8080; done

# 3. Check cache hit rate
curl http://localhost:8090/api/algorithm-metrics | jq '.beta1_global.cache_hit_rate'
```

## 🔧 Server Control

### Add Delay to Server
```bash
# Fixed delay on specific server
curl "http://localhost:8081/control?set_delay_ms=1500"

# Per-request delay
curl "http://localhost:8080?delay=1000"
```

### Disable/Enable Server
```bash
curl -X POST http://localhost:8090/api/servers/toggle \
  -H "Content-Type: application/json" \
  -d '{"host":"127.0.0.1","port":8081}'
```

## 📈 Key Metrics by Algorithm

### ALPHA1 Metrics
```bash
curl http://localhost:8090/api/algorithm-metrics | jq '.alpha1_global'
```
- `current_p99_ms` - Current p99 latency
- `target_p99_ms` - Target p99 (90% of SLO)
- `beta`, `gamma` - Adaptive weights
- `hedge_rate` - Percentage of hedged requests

### BETA1 Metrics
```bash
curl http://localhost:8090/api/algorithm-metrics | jq '.beta1_global'
```
- `cache_hit_rate` - Percentage of cache hits
- `bounded_load_redirects` - Overload redirects
- `servers_in_warmup` - Servers warming up
- `warmup_redirect_rate` - Warm-up redirects

## 🎯 Algorithm Selection Guide

**Choose ALPHA1 when:**
- Tail latency (p99/p99.9) is critical
- Heavy-tailed workloads
- Noisy neighbors or stragglers
- Strict SLO requirements

**Choose BETA1 when:**
- Cache locality is important
- Stateful services
- Session affinity needed
- Sharded data access

**Choose Response Time when:**
- Average latency matters most
- Performance optimization needed
- Servers have varying speeds

**Choose Least Connections when:**
- Request durations vary
- Simple load balancing needed
- No special requirements

**Choose Health Score when:**
- Servers fail intermittently
- Gradual recovery needed
- Reliability is key

## 🔍 Troubleshooting

### Check if System is Running
```bash
curl http://localhost:8090/api/status
```

### Check Server Health
```bash
curl http://localhost:8090/api/servers | jq '.servers[] | {port, healthy}'
```

### View Recent Requests
```bash
curl http://localhost:8090/api/performance | jq '.recent_requests'
```

### Check Active Connections
```bash
curl http://localhost:8090/api/performance | jq '.active_connections'
```

## 📚 Documentation Files

- **README_NEW.md** - Complete project overview
- **ALPHA1_IMPLEMENTATION.md** - ALPHA1 detailed docs
- **BETA1_IMPLEMENTATION.md** - BETA1 detailed docs
- **ALGORITHMS_COMPARISON.md** - All algorithms compared
- **DEMO_GUIDE.md** - Step-by-step demo scenarios
- **IMPLEMENTATION_SUMMARY.md** - Implementation details

## 🎓 Quick Tips

1. **Start Simple**: Begin with Round Robin or Least Connections
2. **Monitor Metrics**: Use the dashboard to understand behavior
3. **Test Gradually**: Try each algorithm with different workloads
4. **Use Delays**: Add delays to simulate slow servers
5. **Compare Results**: Switch algorithms and compare metrics
6. **Read Docs**: Each algorithm has detailed documentation

## 🚨 Common Commands

```bash
# Start system
python start.py

# Switch to ALPHA1
curl -X POST http://localhost:8090/api/strategy -H "Content-Type: application/json" -d '{"strategy":"alpha1"}'

# Switch to BETA1
curl -X POST http://localhost:8090/api/strategy -H "Content-Type: application/json" -d '{"strategy":"beta1"}'

# Run load test
curl -X POST http://localhost:8090/api/load-test -H "Content-Type: application/json" -d '{"requests":100,"concurrent":10}'

# Check metrics
curl http://localhost:8090/api/algorithm-metrics | jq

# View dashboard
open http://localhost:8090  # macOS
start http://localhost:8090  # Windows
```

---

**Need Help?** Check the detailed documentation files or open the dashboard at http://localhost:8090
