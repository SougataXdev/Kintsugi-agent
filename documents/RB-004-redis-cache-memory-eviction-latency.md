# RUNBOOK: RB-004 - Redis Cache Memory Eviction & Latency Degradation

- **Runbook ID:** RB-004
- **Severity Level:** Sev-2 (High) / Sev-1 (If Session Store or Rate Limiter Affected)
- **Service:** Distributed Cache & In-Memory Store (Redis / AWS ElastiCache)
- **Target Systems:** Redis Cluster, Redis Standalone, ElastiCache Replication Group
- **Applicable Environments:** Production, Staging
- **Owner:** Platform Data Services / CloudOps SRE
- **Last Verified:** 2026-09-02

---

## 1. Overview & Alert Symptoms

Redis memory consumption has reached `maxmemory` threshold, leading to aggressive key eviction, or CPU utilization is pegged at 100% on a single core due to blocking O(N) commands or key serialization overhead. This manifests as cache miss storms, increased latency across downstream databases, and dropped client connections (`OOM command not allowed when used memory > 'maxmemory'`).

### Common Alerts:
- `RedisEvictedKeysRateHigh`: Evictions > 5,000 keys/sec.
- `RedisMemoryFragmentationRatio`: Fragmentation ratio > 1.5 or < 0.9.
- `RedisEngineCPUUtilization`: Primary node CPU > 90%.
- `RedisBlockedClients`: Blocked clients count > 20.

---

## 2. Immediate Triage & Impact Assessment (First 5 Minutes)

1. **Check Redis Server Info and Memory Stats via CLI:**
   ```bash
   redis-cli -h <redis-host> -p 6379 -a "<auth-token>" info memory
   ```
   *Key Metrics:*
   - `used_memory_human`: Current allocated memory.
   - `maxmemory_human`: Configured memory cap.
   - `mem_fragmentation_ratio`: If > 1.5, memory fragmentation is wasting RAM; if < 1.0, Redis is swapping to disk.
   - `evicted_keys`: Cumulative count of keys deleted due to `maxmemory`.

2. **Check Connected Clients & Blocked Clients:**
   ```bash
   redis-cli -h <redis-host> -p 6379 -a "<auth-token>" info clients
   ```

3. **Check CPU Usage:**
   ```bash
   redis-cli -h <redis-host> -p 6379 -a "<auth-token>" info cpu
   ```

---

## 3. Diagnostic Procedures

### Step 1: Detect Blocking or Slow Redis Commands
Examine the slow query log to identify expensive operations (e.g. `KEYS *`, `SMEMBERS`, `HGETALL` on massive sets):
```bash
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" slowlog get 20
```

### Step 2: Scan for Huge Keys (Memory Pigs)
Run a non-blocking background bigkeys scan to identify large data structures:
```bash
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" --bigkeys
```

### Step 3: Check Active Eviction Policy
```bash
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" config get maxmemory-policy
```
- `noeviction`: Returns errors on writes when memory is full (causes application errors).
- `allkeys-lru` / `volatile-lru`: Evicts least recently used keys.
- `volatile-ttl`: Evicts keys with shortest time-to-live.

---

## 4. Immediate Mitigation & Remediation Steps

### Action 1: Kill Slow or Runaway Commands
If an engineer or automated script initiated a blocking command like `KEYS *`:
```bash
# Check running clients
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" client list | grep -E 'cmd=keys|cmd=hgetall'

# Terminate offending client connection
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" client kill <ip:port>
```

### Action 2: Trigger Active Memory Defragmentation
If `mem_fragmentation_ratio` > 1.5:
```bash
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" config set activedefrag yes
```

### Action 3: Temporarily Increase Maxmemory Limit (Or Scale ElastiCache Node Type)
If host instance has spare RAM:
```bash
# Temporarily raise maxmemory limit by 25%
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" config set maxmemory 12gb
```
For AWS ElastiCache:
```bash
# Trigger node type scale-up (e.g. cache.m6g.large to cache.m6g.xlarge)
aws elasticache modify-replication-group \
  --replication-group-id <replication-group-id> \
  --cache-node-type cache.m6g.xlarge \
  --apply-immediately
```

### Action 4: Flush Transient Keys / Cache Purge (Emergency Only)
*Caution:* Only flush non-persistent cache databases (never flush session/token DBs):
```bash
# Flush only the dedicated transient cache DB (e.g. DB 2)
redis-cli -h <redis-host> -p 6379 -a "<auth-token>" -n 2 flushdb async
```

---

## 5. Verification & Health Check

1. Confirm command latency drops below 2ms:
   ```bash
   redis-cli -h <redis-host> -p 6379 -a "<auth-token>" --latency -c
   ```
2. Verify application cache hit ratio returns to standard baseline (> 85%):
   ```bash
   redis-cli -h <redis-host> -p 6379 -a "<auth-token>" info stats | grep -E 'keyspace_hits|keyspace_misses'
   ```

---

## 6. Escalation Matrix

| Role | Contact Channel | Escalation Trigger |
|---|---|---|
| CloudOps Data Platform On-Call | Slack `#redis-ops` | Redis CPU 100% or node failover fails |
| Application Engineering On-Call | Slack `#app-cache-alerts` | Cache stampede causing backend DB overload |
| CloudOps Lead | PagerDuty Escalation | Data loss or cache cluster unavailability |
