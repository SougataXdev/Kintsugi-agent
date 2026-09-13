# RUNBOOK: RB-001 - Kubernetes Pod CrashLoopBackOff & OOMKilled Triage

- **Runbook ID:** RB-001
- **Severity Level:** Sev-1 (Critical) / Sev-2 (High)
- **Service:** Kubernetes Workloads / Microservices
- **Target Systems:** EKS / GKE / Self-Hosted K8s Clusters
- **Applicable Environments:** Production, Staging
- **Owner:** CloudOps / SRE Platform Engineering
- **Last Verified:** 2026-09-10

---

## 1. Overview & Alert Symptoms

A pod enters `CrashLoopBackOff` when a container repeatedly terminates unexpectedly after starting. An `OOMKilled` (Exit Code 137) state occurs when the container exceeds its configured cgroup memory limit or node memory exhaustion forces the Linux OOM-killer to terminate the process.

### Common Alerts:
- `KubePodCrashLooping`: Pod has restarted > 5 times within 10 minutes.
- `KubeContainerOOMKilled`: Container killed due to memory exhaustion.
- `PodFailedState`: Replicas available < Desired replicas for deployment.

---

## 2. Immediate Triage & Impact Assessment (First 5 Minutes)

1. **Identify the affected namespace, deployment, and pods:**
   ```bash
   kubectl get pods -A | grep -E 'CrashLoopBackOff|OOMKilled|Error'
   ```

2. **Check the replica availability of the affected deployment:**
   ```bash
   kubectl get deployment <deployment-name> -n <namespace>
   ```
   *Impact:* If `AVAILABLE` is `0`, service is hard down. If partial, service is degraded.

3. **Inspect the termination reason and exit code:**
   ```bash
   kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'
   ```
   - **Exit Code 137:** Process terminated by SIGKILL (Usually OOMKilled).
   - **Exit Code 1:** Application internal fatal error / uncaught exception.
   - **Exit Code 143:** Graceful termination SIGTERM that timed out.
   - **Exit Code 126 / 127:** Container command cannot be invoked or binary not found.

---

## 3. Diagnostic Procedures

### Scenario A: Pod Terminated with OOMKilled (Exit Code 137)

1. **Verify memory limits and usage:**
   ```bash
   kubectl describe pod <pod-name> -n <namespace> | grep -A 5 -E 'Limits|Requests'
   ```
2. **Review historical memory usage before termination via metrics:**
   ```bash
   kubectl top pod <pod-name> -n <namespace> --containers
   ```
3. **Check node memory pressure:**
   ```bash
   kubectl describe node <node-name> | grep -E 'MemoryPressure|Allocatable'
   ```

### Scenario B: Pod in CrashLoopBackOff (Application Crashes)

1. **Inspect current container logs:**
   ```bash
   kubectl logs <pod-name> -n <namespace> --tail=100
   ```
2. **Inspect previous crashed container instance logs:**
   ```bash
   kubectl logs <pod-name> -n <namespace> --previous --tail=150
   ```
3. **Examine recent Kubernetes events for config or volume issues:**
   ```bash
   kubectl get events -n <namespace> --sort-by='.metadata.creationTimestamp' | tail -n 25
   ```
   *Common causes:* Missing ConfigMap, unmounted Secret, failed liveness/readiness probe, or database migration failure.

---

## 4. Immediate Mitigation & Remediation Steps

### Action 1: Temporary Vertical Memory Limit Bump (For OOMKilled)
If traffic spike or cache warm-up caused legitimate memory saturation:
```bash
# Patch container memory limits by 1.5x - 2x
kubectl set resources deployment <deployment-name> -n <namespace> \
  --limits=memory=2Gi \
  --requests=memory=1Gi
```

### Action 2: Roll Back a Faulty Deployment
If CrashLoopBackOff started immediately following a new release or bad configuration change:
```bash
# View rollout history
kubectl rollout history deployment/<deployment-name> -n <namespace>

# Undo the last rollout
kubectl rollout undo deployment/<deployment-name> -n <namespace>

# Watch status until healthy
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

### Action 3: Restart or Evict Stuck Pods
```bash
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

---

## 5. Verification & Health Check

1. Verify that all pods in the deployment reach `1/1 Running` status with zero restarts:
   ```bash
   kubectl get pods -n <namespace> -l app=<app-label> -w
   ```
2. Ensure endpoints are healthy and accepting network traffic:
   ```bash
   kubectl get endpoints <service-name> -n <namespace>
   ```

---

## 6. Escalation Matrix

| Role | Contact Channel | Escalation Trigger |
|---|---|---|
| Primary SRE On-Call | Slack `#cloudops-oncall` | Alert fired, unmitigated in 10 mins |
| Service Tech Lead | PagerDuty On-Call Schedule | Application stack trace or bad code release |
| Database Admin | Slack `#dba-oncall` | Pod crashes due to database connection timeout |
