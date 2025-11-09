# BETA1 Algorithm Implementation

## Overview

BETA1 (Bounded-Load Cache-Aware Rendezvous Hashing) is a load balancing algorithm designed to solve cache locality problems by providing strong key affinity while preventing hotspots and handling scaling events gracefully.

## Problem Statement

Traditional load balancers are blind to key affinity, leading to:
- **Cache thrashing**: Same keys routed to different servers
- **Cold cache misses**: Keys not found in server caches
- **Massive key reshuffle**: During scaling events, keys migrate unpredictably
- **Poor cache hit rates**: Reduced application performance

## Algorithm Features

### 1. Rendezvous (HRW) Hashing for Key Stickiness
- Each key is assigned to the most preferred server using Highest Random Weight (HRW) hashing
- **Stable**: Same key always maps to same server (unless topology changes)
- **Simple**: No complex data structures or coordination
- **Naturally balanced**: Hash function distributes keys evenly

**Formula:**
```
weight(key, server) = hash(key || server_id)
Preferred server = argmax(weight(key, server))
```

### 2. Bounded-Load Admission Control
Even if a server is the preferred target, BETA1 checks capacity constraints:

```
current_load ≤ capacity_factor × average_load
```

- Prevents hotspots from popular keys
- Provides bounded imbalance guarantees
- Falls back to next server in HRW ranking if overloaded
- Based on "Consistent Hashing with Bounded Loads" research

### 3. Warm-Up Mode for Scaling Events
When servers are added or removed, BETA1 implements gradual traffic shifting:

- **Warm-up period**: New servers get limited traffic initially (default: 60 seconds)
- **Quota-based**: New servers receive only `warmup_quota_factor × average_load` during warm-up
- **Gradual cutover**: Once warm-up completes, server receives full traffic
- **Protects cache hit rates**: Prevents cold cache performance degradation

### 4. Popularity-Aware Spill
BETA1 tracks recent keys on each server:

- **Recent key tracking**: Maintains set of recently seen keys per server
- **Cache warmth check**: Prefers servers that have seen the key recently
- **Improves cache hits**: Routes requests to servers with warm caches
- **Simple implementation**: Uses set-based tracking (can be upgraded to Bloom filter)

## Implementation Details

### Configuration Parameters
```python
capacity_factor = 1.25          # Max load = 1.25 × average_load
warmup_duration = 60            # Warm-up period in seconds
warmup_quota_factor = 0.3       # 30% of average load during warm-up
recent_key_limit = 1000         # Track last 1000 keys per server
```

### Key Methods

**`select_server(server_list)`**
- Main selection logic
- Implements HRW ranking and bounded-load checking
- Returns best available server

**`select_server_with_key(server_list, request_key)`**
- Enhanced selection with explicit request key
- Provides true cache affinity when request context is available
- Recommended for production use

**`_hrw_rank(key, server_list)`**
- Implements Rendezvous (Highest Random Weight) hashing
- Returns servers sorted by hash weight for given key
- Uses SHA-256 for hash computation

**`_is_overloaded(server, average_load)`**
- Checks bounded-load constraint
- Returns True if `current_load > capacity_factor × average_load`

**`_in_warmup_mode(server_key)`**
- Checks if server is in warm-up period
- Returns True if server is new and within warmup_duration

**`_warmup_quota_exceeded(server_key, average_load)`**
- Checks if warm-up server has exceeded its quota
- Prevents overwhelming new servers

**`_key_is_recent_on(key, server_key)`**
- Checks if key was recently seen on server
- Improves cache hit rate by routing to warm caches

**`_detect_scaling_events(server_list)`**
- Detects server additions/removals
- Initializes warm-up mode for new servers
- Cleans up state for removed servers

## Metrics Exposed

### Per-Server Metrics
- `total_requests`: Total requests handled by server
- `cached_keys_count`: Number of keys currently cached
- `is_warming_up`: Whether server is in warm-up mode
- `warmup_progress`: Percentage of warm-up completed (0-100%)
- `warmup_requests`: Requests handled during warm-up

### Global Metrics
- `capacity_factor`: Configured capacity multiplier
- `warmup_duration_sec`: Warm-up period duration
- `total_requests`: Total requests processed
- `cache_hit_rate`: Percentage of requests sent to preferred server
- `bounded_load_redirects`: Requests redirected due to overload
- `redirect_rate`: Percentage of redirected requests
- `warmup_redirects`: Requests redirected due to warm-up
- `warmup_redirect_rate`: Percentage of warm-up redirects
- `servers_in_warmup`: Count of servers currently warming up

## Usage

### Via Dashboard
1. Open http://localhost:8090
2. Select "BETA1 (Cache Affinity)" from strategy dropdown
3. Click "Update"
4. Monitor cache hit rates and warm-up progress

### Via API
```bash
curl -X POST http://localhost:8090/api/strategy \
  -H "Content-Type: application/json" \
  -d '{"strategy":"beta1"}'
```

### Via Config
```python
# config.py
config = {
    'strategy': 'beta1',
    # ... other settings
}
```

## Testing BETA1

### Basic Key Affinity Test
```bash
# Send requests with same "key" pattern
# BETA1 should route to same server for same key
for i in {1..20}; do
  curl -s http://localhost:8080 | jq -r '.server'
done | sort | uniq -c
```

### Bounded-Load Test
```bash
# Create load imbalance
# BETA1 should redirect to prevent overload
for i in {1..100}; do
  curl -s http://localhost:8080 &
done
wait

# Check metrics
curl http://localhost:8090/api/algorithm-metrics | jq '.beta1_global'
```

### Scaling Event Test
```bash
# 1. Start with 3 servers, send traffic
# 2. Add a 4th server (modify config and restart)
# 3. Observe warm-up mode and gradual traffic shift
# 4. Check warmup_progress in metrics
curl http://localhost:8090/api/algorithm-metrics | jq '.servers[] | {port, is_warming_up, warmup_progress}'
```

### Cache Hit Rate Test
```bash
# Send repeated requests
# Cache hit rate should increase as keys become "recent"
for round in {1..5}; do
  echo "Round $round:"
  for i in {1..20}; do
    curl -s http://localhost:8080 > /dev/null
  done
  curl -s http://localhost:8090/api/algorithm-metrics | jq '.beta1_global.cache_hit_rate'
  sleep 2
done
```

## Comparison with Other Algorithms

| Feature | Round Robin | Least Connections | Consistent Hash | BETA1 |
|---------|-------------|-------------------|-----------------|-------|
| Key Affinity | ❌ | ❌ | ✅ | ✅ |
| Bounded Load | ❌ | ⚠️ | ❌ | ✅ |
| Warm-Up Mode | ❌ | ❌ | ❌ | ✅ |
| Cache Awareness | ❌ | ❌ | ❌ | ✅ |
| Hotspot Prevention | ❌ | ⚠️ | ❌ | ✅ |
| Graceful Scaling | ❌ | ✅ | ⚠️ | ✅ |

**Legend:**
- ✅ Full support
- ⚠️ Partial support
- ❌ No support

## Best Use Cases

BETA1 is ideal for:
- **Caching applications** (Redis, Memcached proxies)
- **Session-based systems** (sticky sessions with load balancing)
- **Sharded databases** (consistent key-to-shard mapping)
- **Content delivery** (cache-aware routing)
- **Stateful services** (minimize state migration)
- **Microservices with local caches** (improve cache hit rates)

## Key Advantages

1. **High Cache Hit Rates**: Keys consistently route to same server
2. **Hotspot Prevention**: Bounded-load constraint prevents overload
3. **Graceful Scaling**: Warm-up mode protects performance during topology changes
4. **No Coordination**: Stateless algorithm, no distributed coordination needed
5. **Predictable Performance**: Bounded imbalance guarantees
6. **Simple Implementation**: No complex data structures

## Limitations

1. **Key Extraction**: Requires identifying request keys (not always available)
2. **Memory Overhead**: Tracks recent keys per server (configurable limit)
3. **Not Response-Time Aware**: Focuses on cache affinity, not latency
4. **Warm-Up Delay**: New servers take time to reach full capacity

## Advanced Configuration

### Tuning Capacity Factor
```python
# More aggressive load balancing (tighter bounds)
capacity_factor = 1.1  # Allow only 10% above average

# More lenient (better cache affinity)
capacity_factor = 1.5  # Allow 50% above average
```

### Tuning Warm-Up
```python
# Faster warm-up (for stable workloads)
warmup_duration = 30  # 30 seconds
warmup_quota_factor = 0.5  # 50% of traffic

# Slower warm-up (for cache-sensitive workloads)
warmup_duration = 120  # 2 minutes
warmup_quota_factor = 0.2  # 20% of traffic
```

### Tuning Key Tracking
```python
# More memory for better cache awareness
recent_key_limit = 5000  # Track 5000 keys

# Less memory for resource-constrained environments
recent_key_limit = 500  # Track 500 keys
```

## Files Modified

1. **load_balancer/strategies.py** - Added `BETA1Strategy` class
2. **load_balancer/load_balancer.py** - Registered BETA1 strategy
3. **web_interface/app.py** - Added BETA1 to valid strategies and metrics
4. **web_interface/templates/dashboard.html** - Added BETA1 to dropdown

## References

- Rendezvous Hashing: Thaler & Ravishankar (1998)
- Consistent Hashing with Bounded Loads: Mirrokni et al. (2018)
- Cache-Aware Load Balancing: Berger et al. (2017)
- Power of Two Choices: Mitzenmacher (1996)

## Future Enhancements

Possible improvements for production use:

1. **Bloom Filter**: Replace set-based key tracking with space-efficient Bloom filter
2. **Request Key Extraction**: Middleware to extract keys from HTTP headers/URLs
3. **Persistent State**: Save key-to-server mappings across restarts
4. **Dynamic Capacity**: Adjust capacity_factor based on server health
5. **Multi-Level Caching**: Support for L1/L2 cache hierarchies
6. **Key Popularity Tracking**: Weight decisions by key access frequency
