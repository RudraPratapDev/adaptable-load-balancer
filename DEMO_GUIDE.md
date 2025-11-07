# Step-by-Step Demo Guide

## 🚀 Setup

1. **Start the system**:
   ```bash
   python start.py
   ```

2. **Open dashboard**: Go to `http://localhost:8090`

3. **Open testing tab**: Open `http://localhost:8080` in a new browser tab (keep this tab open for sending requests)

## 📋 Demo 1: Round Robin Algorithm

### Step 1: Select Round Robin
- In dashboard, select **"Round Robin"** from strategy dropdown
- Click **"Update"** button

### Step 2: Send Requests
- Go to your `http://localhost:8080` tab
- **Reload the page 10-15 times** (Ctrl+R or F5)
- Each reload sends a request and shows JSON response

### Step 3: Observe Distribution
- **What you'll see**: JSON responses showing different servers:
  ```json
  {"message": "Hello from Server-1", "server": "127.0.0.1:8081"}
  {"message": "Hello from Server-2", "server": "127.0.0.1:8082"}  
  {"message": "Hello from Server-3", "server": "127.0.0.1:8083"}
  ```
- **Pattern**: Requests go to servers in order: Server-1 → Server-2 → Server-3 → Server-1...
- **Dashboard**: Watch "Request distribution" bar show equal distribution across all servers

### Step 4: Test Server Failure
- **Stop one server**: In terminal running `start.py`, you'll see 3 backend server processes. Stop one with Ctrl+C
- **Send more requests**: Reload `http://localhost:8080` tab 10 times
- **What you'll see**: Only 2 servers responding, requests distributed equally between them
- **Dashboard**: Shows 2/3 healthy servers, failed server marked as "Unhealthy"

### Step 5: Test Server Recovery
- **Restart the stopped server**: The `start.py` will show the server restarting
- **Send more requests**: Reload the tab 10 times
- **What you'll see**: All 3 servers responding again, equal distribution restored

### Step 6: Test with Slow Server (Delay Feature)
- **Create slow server**: Go to `http://localhost:8080/?delay=3000` 
- **Reload this URL 5 times** (each request takes 3 seconds)
- **Send normal requests**: Go back to `http://localhost:8080` and reload 10 times
- **What you'll see**: 
  - Round Robin **still distributes equally** to all servers (including slow one)
  - **No adaptation** - algorithm doesn't care about response time
  - Slow requests still get routed to the delayed server
- **Key Point**: Round Robin is "blind" to server performance

---

## 📋 Demo 2: Health-Score-Based Selection

### Step 1: Select Health Score Algorithm
- In dashboard, select **"Health Score Based"** from dropdown
- Click **"Update"** button

### Step 2: Baseline Testing
- **Send requests**: Reload `http://localhost:8080` tab 15 times
- **What you'll see**: **Equal distribution** across all servers (all have same health score = 1.0)
- **Dashboard**: Shows "Health Score: 1.000" for all servers
- **Key Point**: When health scores are equal, algorithm uses round-robin for fair distribution

### Step 3: Create Server Failures
- **Stop one server** (Ctrl+C in terminal)
- **Wait 10 seconds** for health monitor to detect failure
- **Send more requests**: Reload tab 15 times

### Step 4: Observe Smart Routing
- **What you'll see**: 
  - Failed server stops responding
  - Healthy servers get all traffic
  - **Dashboard shows**: Failed server has "Health Score: 0.500" (due to failures)
- **Key difference from Round Robin**: When server comes back, it gets LESS traffic initially due to lower health score

### Step 5: Test Recovery Adaptation
- **Restart the failed server**
- **Send requests**: Reload tab 20 times slowly
- **What you'll see**: 
  - Server comes back online
  - **Initially gets fewer requests** (lower health score due to failure history)
  - **Gradually gets more traffic** as health score improves with successful requests
- **Dashboard**: Watch health score slowly increase from 0.500 back toward 1.000

### Step 6: Test with Slow Server Performance
- **Create slow server**: Go to `http://localhost:8080/?delay=2000`
- **Reload this URL 5 times** (creates 2-second delays)
- **Send normal requests**: Go back to `http://localhost:8080` and reload 15 times
- **What you'll see**:
  - Health Score algorithm **doesn't adapt to slow responses** (only cares about failures and connections)
  - Slow server still gets requests based on health score formula
  - **Key insight**: Health Score focuses on reliability, not performance
- **Dashboard**: Health scores remain similar, no performance-based adjustment

---

## 📋 Demo 3: Weighted Round Robin Algorithm

### Step 1: Select Weighted Round Robin
- In dashboard, select **"Weighted Round Robin"** from dropdown  
- Click **"Update"** button

### Step 2: Baseline Pattern
- **Send requests**: Reload `http://localhost:8080` tab 20 times
- **What you'll see**: Each server gets multiple consecutive requests before switching
- **Pattern**: 10 requests to Server-1, then 10 to Server-2, then 10 to Server-3, repeat
- **Dashboard**: Shows "Weight: 10" for all servers (0 failures = weight 10)

### Step 3: Create Failure History
- **Stop one server** for 30 seconds, then restart it
- **Wait for health monitor** to detect and recover the server
- **Send requests**: Reload tab 30 times

### Step 4: Observe Weight Adaptation  
- **What you'll see**: 
  - Server with failure history gets **fewer consecutive requests**
  - Pattern changes to: 10 requests to good servers, only 5 (or 1) to the previously failed server
- **Dashboard**: Shows different weights:
  - Good servers: "Weight: 10" 
  - Failed server: "Weight: 5" (1 failure) or "Weight: 1" (2+ failures)

### Step 5: Test Multiple Failures
- **Create more failures** by stopping/starting servers multiple times
- **Send requests**: Reload tab and observe
- **What you'll see**: Servers with more failures get progressively fewer requests (weight decreases to 1)

### Step 6: Test with Slow Server Performance
- **Create slow server**: Go to `http://localhost:8080/?delay=2500`
- **Reload this URL 4 times** (creates 2.5-second delays)
- **Send normal requests**: Go back to `http://localhost:8080` and reload 20 times
- **What you'll see**:
  - Weighted Round Robin **doesn't adapt to slow responses** (only cares about failure count)
  - Slow server still gets its full weight of consecutive requests
  - **Key insight**: This algorithm focuses on failure history, not response time performance
- **Dashboard**: Weights remain the same, no performance-based weight adjustment

---

## 📋 Demo 4: Response Time-Based Selection

### Step 1: Select Response Time Algorithm
- In dashboard, select **"Response Time Based"** from dropdown
- Click **"Update"** button

### Step 2: Initial Distribution (Building Response Time Data)
- **Send baseline requests**: Reload `http://localhost:8080` tab 15 times
- **What you'll see**: **Equal distribution** initially (algorithm builds response time data)
- **Dashboard**: Shows "Avg Response: 0ms" for all servers initially

### Step 3: Create Response Time Differences
- **Send slow requests**: 
  - Go to `http://localhost:8080/?delay=2000` (2 second delay)
  - Reload this 5 times to create slow response history for one server
- **Send normal requests**: Go back to `http://localhost:8080` and reload 10 times

### Step 4: Observe Performance Routing
- **What you'll see**: Most requests go to servers with faster response times
- **Dashboard**: Shows "Avg Response: XXXms" - servers with higher response times get less traffic

### Step 5: Test Dynamic Adaptation
- **Create different delays**:
  - `http://localhost:8080/?delay=1000` (reload 3 times)
  - `http://localhost:8080/?delay=3000` (reload 3 times)  
  - `http://localhost:8080/` (reload 10 times)
- **What you'll see**: Algorithm learns and routes most traffic to fastest servers
- **Dashboard**: Response times update in real-time, traffic shifts to fastest servers

### Step 6: Advanced Performance Testing
- **Create performance tiers**:
  - **Fast server**: `http://localhost:8080/` (reload 5 times - no delay)
  - **Medium server**: `http://localhost:8080/?delay=1500` (reload 5 times - 1.5s delay)  
  - **Slow server**: `http://localhost:8080/?delay=4000` (reload 5 times - 4s delay)
- **Test adaptation**: Go back to `http://localhost:8080` and reload 20 times
- **What you'll see**:
  - **Most requests go to fast server** (0ms average response time)
  - **Fewer requests to medium server** (1500ms average)
  - **Minimal requests to slow server** (4000ms average)
  - **Real-time adaptation**: Algorithm continuously learns and optimizes
- **Dashboard**: 
  - "Avg Response" shows different times for each server
  - Request distribution heavily favors fastest servers
  - **This is the ONLY algorithm that optimizes for performance**

---

## 🎯 Key Differences to Highlight

### How Each Algorithm Handles Slow Servers (Delay Testing)

**Round Robin**:
- ❌ **No adaptation to slow servers** - continues equal distribution
- ❌ **Performance blind** - doesn't care about response times
- ❌ **User experience suffers** - slow servers get same traffic as fast ones

**Health Score Based**:
- ❌ **No performance optimization** - only considers failures and connections
- ✅ **Failure awareness** - adapts to server crashes but not slowness
- ⚠️ **Limitation**: A slow but stable server still gets high health score

**Weighted Round Robin**:
- ❌ **No response time consideration** - only cares about failure count
- ✅ **Failure memory** - reduces traffic to servers that crash frequently
- ⚠️ **Limitation**: Slow servers get full weight if they don't fail

**Response Time Based**:
- ✅ **Performance optimization** - automatically routes to fastest servers
- ✅ **Real-time learning** - adapts to changing server performance
- ✅ **Best user experience** - minimizes response times
- ✅ **Dynamic adaptation** - continuously optimizes based on actual performance

### Algorithm Comparison Summary

| Feature | Round Robin | Health Score | Weighted RR | Response Time |
|---------|-------------|--------------|-------------|---------------|
| **Equal Distribution** | ✅ Always | ❌ Failure-aware | ❌ Weight-based | ❌ Performance-based |
| **Failure Memory** | ❌ None | ✅ Yes | ✅ Yes | ❌ No |
| **Performance Awareness** | ❌ None | ❌ None | ❌ None | ✅ Yes |
| **Slow Server Handling** | ❌ Ignores | ❌ Ignores | ❌ Ignores | ✅ Optimizes |
| **Recovery Behavior** | ✅ Immediate | 🔄 Gradual | 🔄 Gradual | ✅ Immediate |
| **Best Use Case** | Simple setups | Unreliable servers | Failure-prone env | Performance-critical |

## � DDelay Feature Testing Guide

### Understanding the Delay Parameter
- **URL Format**: `http://localhost:8080/?delay=MILLISECONDS`
- **Examples**:
  - `http://localhost:8080/?delay=1000` - 1 second delay
  - `http://localhost:8080/?delay=2500` - 2.5 second delay
  - `http://localhost:8080/?delay=5000` - 5 second delay

### Delay Testing Strategy for Each Algorithm

**Round Robin Delay Test**:
```
1. Go to http://localhost:8080/?delay=3000
2. Reload 5 times (creates slow server history)
3. Go to http://localhost:8080/ 
4. Reload 15 times
5. Result: Still equal distribution (algorithm ignores performance)
```

**Health Score Delay Test**:
```
1. Go to http://localhost:8080/?delay=2000
2. Reload 5 times 
3. Go to http://localhost:8080/
4. Reload 15 times
5. Result: No performance adaptation (only cares about failures)
```

**Weighted RR Delay Test**:
```
1. Go to http://localhost:8080/?delay=2500
2. Reload 4 times
3. Go to http://localhost:8080/
4. Reload 20 times  
5. Result: No performance consideration (only failure-based weights)
```

**Response Time Delay Test**:
```
1. Create performance tiers:
   - http://localhost:8080/?delay=500 (reload 3 times)
   - http://localhost:8080/?delay=2000 (reload 3 times)
   - http://localhost:8080/?delay=4000 (reload 3 times)
2. Go to http://localhost:8080/
3. Reload 20 times
4. Result: Traffic shifts to fastest servers automatically!
```

## 💡 Demo Tips

1. **Use dashboard side-by-side** with the request tab to see real-time metrics
2. **Reload slowly** (1-2 seconds between) to clearly see patterns
3. **Watch the "Request distribution" bar** to visualize traffic patterns
4. **Check server metrics** to see algorithm-specific values (health scores, weights, response times)
5. **Use load test buttons** in dashboard for rapid testing
6. **Create dramatic delays** (3000ms+) to clearly show algorithm differences
7. **Test multiple delay values** to create performance tiers
8. **Watch response time metrics** in dashboard during delay testing

## 🎬 Perfect Demo Flow

1. **Start with Round Robin** - show basic equal distribution
2. **Switch to Health Score** - demonstrate failure memory and smart recovery
3. **Switch to Weighted RR** - show automatic weight adaptation
4. **Switch to Response Time** - demonstrate performance-based routing
5. **Compare behaviors** - switch between algorithms with same failure scenarios

This clearly shows how the new algorithms are **smarter** and **more adaptive** than traditional Round Robin!