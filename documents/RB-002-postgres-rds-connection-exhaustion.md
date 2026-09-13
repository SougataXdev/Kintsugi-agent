# RUNBOOK: RB-002 - PostgreSQL / AWS RDS Connection Exhaustion & High Latency

- **Runbook ID:** RB-002
- **Severity Level:** Sev-1 (Critical)
- **Service:** Relational Database Layer (PostgreSQL / AWS RDS Aurora)
- **Target Systems:** Primary DB Cluster, PgBouncer / RDS Proxy
- **Applicable Environments:** Production, Staging
- **Owner:** Database Operations / CloudOps SRE
- **Last Verified:** 2026-09-08

---

## 1. Overview & Alert Symptoms

PostgreSQL has reached or is approaching `max_connections`, or client applications are throwing connection pool timeouts (`FATAL: remaining connection slots are reserved for non-replication superuser connections` or `53300: too_many_connections`). High connection counts frequently lead to thread contention, elevated CPU utilization, and cascading query timeouts across dependent microservices.

### Common Alerts:
- `PostgresConnectionsExhausted`: Database connection usage > 85% of `max_connections`.
- `RDSProxyClientConnectionQueueDepth`: Connection queue time > 2000ms.
- `HighQueryLatency`: P99 query latency > 1500ms.

---

## 2. Immediate Triage & Impact Assessment (First 5 Minutes)

1. **Connect to PostgreSQL using the reserved DBA connection slot:**
   ```bash
   psql -h <db-host> -U db_admin -d postgres -c "SELECT count(*) FROM pg_stat_activity;"
   ```

2. **Check connection breakdown by database, user, and state:**
   ```sql
   SELECT datname, usename, state, count(*) 
   FROM pg_stat_activity 
   GROUP BY datname, usename, state 
   ORDER BY count(*) DESC;
   ```
   *Interpretation:*
   - If most connections are `idle in transaction`: Leaked application transactions or uncommitted blocks.
   - If most connections are `active`: Heavy query barrage, slow query locks, or runaway queries.
   - If most connections are `idle`: Application connection poolers configured with excessive `min_idle` or no idle timeout.

3. **Check current `max_connections` limit:**
   ```sql
   SHOW max_connections;
   ```

---

## 3. Diagnostic Procedures

### Step 1: Detect Long-Running Queries and Blocking Locks
```sql
SELECT 
    pid, 
    now() - query_start AS duration, 
    usename, 
    client_addr, 
    state, 
    wait_event_type, 
    wait_event, 
    query 
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY duration DESC 
LIMIT 10;
```

### Step 2: Detect Blocked Queries and Lock Contention
```sql
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

---

## 4. Immediate Mitigation & Remediation Steps

### Action 1: Terminate Runaway or Blocked Queries
Gracefully cancel queries running longer than 5 minutes:
```sql
-- Gracefully cancel statement execution (allows connection to remain open)
SELECT pg_cancel_backend(pid) 
FROM pg_stat_activity 
WHERE state != 'idle' 
  AND (now() - query_start) > interval '5 minutes';
```

If the process is hung or unresponsive to `pg_cancel_backend`:
```sql
-- Forcefully terminate backend connection
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state != 'idle' 
  AND (now() - query_start) > interval '10 minutes';
```

### Action 2: Terminate Stuck "Idle in Transaction" Connections
Stuck uncommitted transactions hold locks and prevent table autovacuum:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND (now() - state_change) > interval '2 minutes';
```

### Action 3: Throttle or Scale Connection Pooler (PgBouncer / RDS Proxy)
If connection storm is originating from scaled worker pods:
```bash
# Check PgBouncer active pool status
psql -h <pgbouncer-host> -p 6432 -U pgbouncer pgbouncer -c "SHOW POOLS;"
psql -h <pgbouncer-host> -p 6432 -U pgbouncer pgbouncer -c "SHOW CLIENTS;"

# Pause non-critical background ETL workers
kubectl scale deployment batch-data-pipeline -n workers --replicas=0
```

---

## 5. Verification & Health Check

1. Confirm connection counts have returned to safe operational thresholds (< 60% of max):
   ```sql
   SELECT count(*) * 100.0 / current_setting('max_connections')::int AS connection_utilization_pct 
   FROM pg_stat_activity;
   ```
2. Verify application latency metrics in APM (Datadog / Prometheus) have dropped back to normal baseline.

---

## 6. Escalation Matrix

| Role | Contact Channel | Escalation Trigger |
|---|---|---|
| Primary On-Call DBA | PagerDuty Database Tier 1 | Connection usage > 90% after kill scripts |
| Platform / Infrastructure Lead | Slack `#infra-alerts` | RDS CPU > 95% sustained for 10 minutes |
| Application Engineering On-Call | Slack `#app-support` | Faulty deployment leaking unclosed connections |
