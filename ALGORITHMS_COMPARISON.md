# Load Balancing Algorithms Comparison

## Overview

This project implements **7 load balancing algorithms**, each optimized for different use cases and workload characteristics.

## Algorithm Summary

| Algorithm | Strategy Name | Primary Goal | Best For |
|-----------|---------------|--------------|----------|
| Round Robin | `round_robin` | Equal distribution | Simple, homogeneous servers |
| Least Connections | `least_connections` | Balance active load | Variable request durations |
| Health Score Based | `health_score` | Reliability-aware | Unreliable servers |
| Weighted Round Robin | `weighted_round_robin` | Failure-aware distribution | Failure-prone environments |
| Response Time Based | `response_time` | Performance optimization | Latency-sensitive apps |
| ALPHA1 | `alpha1` | Tail latency reduction | p99/p99.9 optimization |
| BETA1 | `beta1` | Cache affinity | Caching/stateful services |

## Detailed Comparison

### 1. Round Robin (RR)

**How it works:**
- Distributes requests sequentially across servers
- Simple rotation: Server 1 → Server 2 → Server 3 → Server 1...

**Pros:**
- ✅ Simple and predictable
- ✅ Equal distribution
- ✅ No state tracking needed
- ✅ Fast selection

**Cons:**
- ❌ Ignores server load
- ❌ Ignores server performance
- ❌ Ignores failures
- ❌ No cache affinity

**Metrics:** None

**Use when:** All servers are identical and requests have similar processing times

---

### 2. Least Connections (LC)

**How it works:**
- Routes to server with fewest active connections
- Fair tie-breaking among servers with equal connections

**Pros:**
- ✅ Load-aware
- ✅ Adapts to request duration
- ✅ Fair distribution
- ✅ Immediate recovery

**Cons:**
- ❌ Doesn't consider response time
- ❌ No failure memory
- ❌ No cache affinity
- ❌ Can be fooled by slow requests

**Metrics:**
- Active connections per server

**Use when:** Request processing times vary significantly

---

### 3. Health Score Based (HS-BS)

**How it works:**
- Calculates health score: `(1/(1+connections)) × (1/(1+failures))`
- Routes to server with highest health score
- Gradual recovery for failed servers

**Pros:**
- ✅ Failure-aware
- ✅ Load-aware
- ✅ Gradual recovery
- ✅ Prevents overloading recovering servers

**Cons:**
- ❌ Not performance-aware
- ❌ Slow servers get same score if stable
- ❌ No cache affinity

**Metrics:**
- Health score per server
- Connection count
- Failure count

**Use when:** Servers fail intermittently and need gradual recovery

---

### 4. Weighted Round Robin (HF-WRR)

**How it works:**
- Assigns weights based on failure history:
  - 0 failures → weight 10
  - 1 failure → weight 5
  - 2+ failures → weight 1
- Each server gets requests equal to its weight

**Pros:**
- ✅ Failure memory
- ✅ Reduces traffic to unstable servers
- ✅ Predictable distribution
- ✅ Gradual recovery

**Cons:**
- ❌ Not performance-aware
- ❌ Slow but stable servers get full weight
- ❌ No cache affinity

**Metrics:**
- Weight per server
- Failure count

**Use when:** Some servers are historically less reliable

---

### 5. Response Time Based (RRT-BS)

**How it works:**
- Tracks average response time (last 100 requests)
- Routes to server with lowest average response time
- Uses round-robin initially to build data

**Pros:**
- ✅ Performance-aware
- ✅ Real-time adaptation
- ✅ Minimizes response time
- ✅ Dynamic optimization

**Cons:**
- ❌ No failure memory
- ❌ Needs warm-up period
- ❌ No cache affinity
- ❌ Can be affected by outliers

**Metrics:**
- Average response time per server (ms)

**Use when:** Minimizing response time is critical

---

### 6. ALPHA1 (Tail Latency Reduction)

**How it works:**
- Two-choice sampling (power of two choices)
- Tail-risk scoring: `EWMA(work) + β×interference + γ×age`
- SLO-aware conditional hedging
- Feedback control for adaptive weights

**Pros:**
- ✅ Reduces tail latency (p95-p99.9)
- ✅ Interference detection
- ✅ Queue age awareness
- ✅ Adaptive weights
- ✅ SLO-aware hedging
- ✅ Handles stragglers

**Cons:**
- ❌ More complex
- ❌ Higher overhead
- ❌ No cache affinity
- ❌ Requires tuning

**Metrics:**
- work_queue_ewma
- interference_signal
- head_request_age
- server_p99_ms
- beta/gamma weights
- hedge_rate
- current_p99_ms

**Use when:** Tail latency (p99/p99.9) is critical, heavy-tailed workloads

---

### 7. BETA1 (Cache-Aware Rendezvous Hashing)

**How it works:**
- Rendezvous (HRW) hashing for key affinity
- Bounded-load admission control
- Warm-up mode for new servers
- Popularity-aware key tracking

**Pros:**
- ✅ Strong key affinity
- ✅ High cache hit rates
- ✅ Hotspot prevention
- ✅ Graceful scaling
- ✅ No coordination needed
- ✅ Bounded imbalance

**Cons:**
- ❌ Requires key extraction
- ❌ Memory overhead for key tracking
- ❌ Not response-time aware
- ❌ Warm-up delay

**Metrics:**
- total_requests per server
- cached_keys_count
- is_warming_up
- warmup_progress
- cache_hit_rate
- bounded_load_redirects
- servers_in_warmup

**Use when:** Cache locality is critical (Redis, Memcached, stateful services)

---

## Feature Matrix

| Feature | RR | LC | HS-BS | HF-WRR | RRT-BS | ALPHA1 | BETA1 |
|---------|----|----|-------|--------|--------|--------|-------|
| **Load Awareness** | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| **Failure Awareness** | ❌ | ❌ | ✅ | ✅ | ❌ | ⚠️ | ❌ |
| **Performance Awareness** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Cache Affinity** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Tail Latency Optimization** | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ | ❌ |
| **Hotspot Prevention** | ❌ | ⚠️ | ⚠️ | ❌ | ❌ | ⚠️ | ✅ |
| **Graceful Scaling** | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ |
| **Adaptive Weights** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **State Tracking** | None | Minimal | Moderate | Moderate | Moderate | High | High |
| **Complexity** | Low | Low | Medium | Medium | Medium | High | High |

**Legend:**
- ✅ Full support
- ⚠️ Partial support
- ❌ No support

## Performance Characteristics

### Latency Impact

| Algorithm | Selection Overhead | Best Case | Worst Case |
|-----------|-------------------|-----------|------------|
| Round Robin | O(1) | Very Low | Very Low |
| Least Connections | O(n) | Low | Low |
| Health Score | O(n) | Low | Medium |
| Weighted RR | O(1) | Low | Low |
| Response Time | O(n) | Low | Medium |
| ALPHA1 | O(1) | Medium | High |
| BETA1 | O(n log n) | Medium | High |

### Memory Usage

| Algorithm | Per-Server State | Global State | Total |
|-----------|------------------|--------------|-------|
| Round Robin | None | Index | Minimal |
| Least Connections | None | None | Minimal |
| Health Score | Failures | None | Low |
| Weighted RR | Failures, Weight | Current server | Low |
| Response Time | Response times (100) | None | Medium |
| ALPHA1 | Work, interference, age, times (100) | Latencies (1000) | High |
| BETA1 | Requests, keys (1000), warmup | Known servers | High |

## Use Case Decision Tree

```
Start
│
├─ Need cache affinity?
│  └─ YES → BETA1
│
├─ Need tail latency optimization (p99)?
│  └─ YES → ALPHA1
│
├─ Need performance optimization (avg)?
│  └─ YES → Response Time Based
│
├─ Servers fail frequently?
│  ├─ YES, need gradual recovery → Health Score Based
│  └─ YES, need failure memory → Weighted Round Robin
│
├─ Variable request durations?
│  └─ YES → Least Connections
│
└─ Simple, homogeneous servers?
   └─ YES → Round Robin
```

## Workload Recommendations

### E-commerce / Web Applications
**Recommended:** Least Connections or Response Time Based
- Variable request processing times
- Need good average performance
- Moderate traffic patterns

### Microservices with Caching
**Recommended:** BETA1
- High cache hit rates critical
- Stateful services
- Session affinity needed

### Real-Time / Gaming
**Recommended:** ALPHA1 or Response Time Based
- Tail latency critical (p99/p99.9)
- User experience sensitive to outliers
- Heavy-tailed workloads

### API Gateway
**Recommended:** Health Score Based or Weighted Round Robin
- Backend services may fail
- Need graceful degradation
- Gradual recovery important

### Database Proxy / Sharding
**Recommended:** BETA1
- Strong key affinity needed
- Minimize connection overhead
- Cache query results

### CDN / Content Delivery
**Recommended:** BETA1 or Response Time Based
- Cache locality critical
- Performance matters
- Geographic distribution

### Batch Processing
**Recommended:** Round Robin or Least Connections
- Long-running jobs
- Equal distribution preferred
- Simple is better

## Switching Strategies

All algorithms can be switched dynamically without restarting:

### Via Dashboard
1. Open http://localhost:8090
2. Select algorithm from dropdown
3. Click "Update"

### Via API
```bash
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"<algorithm_name>"}'
```

### Via Config
```python
# config.py
config = {
    'strategy': 'alpha1',  # or 'beta1', 'round_robin', etc.
    # ...
}
```

## Monitoring & Metrics

Each algorithm exposes specific metrics via `/api/algorithm-metrics`:

- **Round Robin**: None
- **Least Connections**: connections per server
- **Health Score**: health_score per server
- **Weighted RR**: weight per server
- **Response Time**: avg_response_time per server
- **ALPHA1**: work_queue_ewma, interference_signal, head_request_age, p99
- **BETA1**: cached_keys_count, warmup_progress, cache_hit_rate

## Testing Recommendations

### Load Testing
```bash
# Use built-in load test
curl -X POST http://localhost:8090/api/load-test \
  -H "Content-Type: application/json" \
  -d '{"requests":100,"concurrent":10}'
```

### Stress Testing
```bash
# Use built-in stress test
curl -X POST http://localhost:8090/api/stress-test \
  -H "Content-Type: application/json" \
  -d '{"duration":30,"concurrent":50}'
```

### Algorithm-Specific Testing
- **ALPHA1**: Create slow servers with `?delay=ms` parameter
- **BETA1**: Send requests with consistent keys to test affinity
- **Response Time**: Vary server delays to test adaptation
- **Health Score**: Stop/start servers to test recovery

## Conclusion

Choose your algorithm based on:
1. **Workload characteristics** (request patterns, durations)
2. **Performance requirements** (average vs tail latency)
3. **Server characteristics** (reliability, homogeneity)
4. **Application needs** (cache affinity, statefulness)
5. **Operational complexity** (monitoring, tuning)

For most applications, start with **Least Connections** or **Response Time Based**, then upgrade to **ALPHA1** or **BETA1** if you have specific tail latency or cache affinity requirements.
