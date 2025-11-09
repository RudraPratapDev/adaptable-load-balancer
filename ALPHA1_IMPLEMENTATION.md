# ALPHA1 Algorithm Implementation

## Overview

ALPHA1 is a tail latency reduction load balancing algorithm designed to minimize p95-p99.9 latencies in environments with:
- Heavy-tailed workloads
- Noisy co-tenancy interference
- Straggler servers

## Algorithm Features

### 1. Two-Choice Sampling (Power of Two Choices)
- Randomly selects 2 candidate servers instead of checking all servers
- Significantly reduces the probability of selecting an overloaded server
- More efficient than round-robin or full scanning

### 2. Tail-Risk Scoring
Instead of using simple metrics like connection count or last response time, ALPHA1 calculates a composite tail-risk score:

```
Tail-Risk Score = EWMA(work_remaining) + β × interference_signal + γ × head_request_age
```

**Components:**
- **work_remaining**: Estimated CPU-ms/bytes left in the queue (based on active connections)
- **interference_signal**: Host metrics like steal time, run-queue length, cache miss rate (simulated from connection volatility)
- **head_request_age**: Time the first request in the queue has been waiting

### 3. SLO-Aware Conditional Hedging
- Hedging is only applied when predicted finish time exceeds SLO threshold
- Prevents traffic explosion while still reducing tail spikes
- Formula: `hedge if predicted_finish > SLO × threshold_multiplier`

### 4. Feedback Control
- Dynamically adjusts β and γ weights based on recent p99 performance
- If p99 > target: increase weights (more sensitive to interference/age)
- If p99 < target: decay weights (avoid over-correction)
- Prevents oscillation and stabilizes decisions over time

## Implementation Details

### Configuration Parameters
```python
slo_threshold_ms = 100              # Target SLO in milliseconds
hedge_threshold_multiplier = 1.5    # When to trigger hedging
beta = 0.3                          # Initial weight for interference
gamma = 0.4                         # Initial weight for queue age
ewma_alpha = 0.3                    # EWMA smoothing factor
```

### Key Methods

**`select_server(server_list)`**
- Main selection logic
- Implements two-choice sampling
- Computes tail-risk scores
- Returns server with lowest risk

**`_compute_tail_risk(server)`**
- Calculates composite tail-risk score
- Combines work queue, interference, and age metrics

**`_update_server_state(server)`**
- Updates EWMA of work queue
- Simulates interference from connection patterns
- Tracks head request age

**`_adjust_weights_feedback()`**
- Feedback control loop
- Adjusts β and γ based on p99 performance
- Runs every 100 requests

**`record_response_time(host, port, response_time)`**
- Records response times for p99 calculation
- Tracks both per-server and global metrics

**`should_hedge(server, estimated_service_time)`**
- Determines if request should be hedged
- Based on predicted finish time vs SLO

## Metrics Exposed

### Per-Server Metrics
- `work_queue_ewma`: Estimated work remaining
- `interference_signal`: Simulated interference level
- `head_request_age`: Age of oldest queued request
- `server_p99_ms`: Server-specific p99 latency

### Global Metrics
- `beta`: Current interference weight
- `gamma`: Current age weight
- `hedge_rate`: Percentage of requests hedged
- `total_requests`: Total requests processed
- `current_p99_ms`: Current p99 latency
- `target_p99_ms`: Target p99 (90% of SLO)
- `slo_threshold_ms`: Configured SLO threshold

## Usage

### Via Dashboard
1. Open http://localhost:8090
2. Select "ALPHA1 (Tail Latency)" from strategy dropdown
3. Click "Update"
4. Monitor tail-risk metrics in real-time

### Via API
```bash
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"alpha1"}'
```

### Via Config
```python
# config.py
config = {
    'strategy': 'alpha1',
    # ... other settings
}
```

## Testing ALPHA1

### Basic Test
```bash
# Send 100 requests and observe distribution
for i in {1..100}; do
  curl -s http://localhost:8080 | jq -r '.server'
done | sort | uniq -c
```

### Tail Latency Test
```bash
# Create slow server to test tail-risk avoidance
curl "http://localhost:8081/control?set_delay_ms=2000"

# Send requests - ALPHA1 should avoid the slow server
for i in {1..50}; do
  curl -s http://localhost:8080
done
```

### View Metrics
```bash
curl http://localhost:8090/api/algorithm-metrics | jq
```

## Comparison with Other Algorithms

| Feature | Round Robin | Least Connections | Response Time | ALPHA1 |
|---------|-------------|-------------------|---------------|--------|
| Tail Latency Optimization | ❌ | ❌ | ⚠️ | ✅ |
| Interference Detection | ❌ | ❌ | ❌ | ✅ |
| Queue Age Awareness | ❌ | ❌ | ❌ | ✅ |
| Adaptive Weights | ❌ | ❌ | ❌ | ✅ |
| SLO-Aware Hedging | ❌ | ❌ | ❌ | ✅ |
| Power of Two Choices | ❌ | ❌ | ❌ | ✅ |

## Best Use Cases

ALPHA1 is ideal for:
- **Latency-sensitive applications** with strict SLO requirements
- **Microservices** with variable processing times
- **Multi-tenant environments** with noisy neighbors
- **Systems with stragglers** or intermittent slowdowns
- **Heavy-tailed workloads** where p99/p99.9 matters more than average

## Files Modified

1. **load_balancer/strategies.py** - Added `ALPHA1Strategy` class
2. **load_balancer/load_balancer.py** - Registered ALPHA1 strategy
3. **web_interface/app.py** - Added ALPHA1 to valid strategies and metrics
4. **web_interface/templates/dashboard.html** - Added ALPHA1 to dropdown

## References

- Power of Two Choices: Mitzenmacher (1996)
- Tail Latency Control: Dean & Barroso (2013)
- C3 Hedging System: Vulimiri et al. (2015)
