# JupyterHub Hosting Cost — 10,000 Daily Active Users

> Realistic cost estimate based on UC Berkeley, mybinder.org,
> and JupyterHub capacity planning documentation.

---

## Key Assumption: Concurrency, Not Total Users

From JupyterHub's own docs:

> "You might have 10,000 users of your JupyterHub deployment, but only
> 100 of them running at any given time, and that 100 is the main
> number you need to use for your capacity planning."

For a **self-paced learning platform** with global users:

| Scenario | Concurrency | Concurrent Users |
|----------|-------------|-----------------|
| Normal (spread across timezones) | 10-15% | 1,000-1,500 |
| Peak (assignment deadlines, class hours) | 20-25% | 2,000-2,500 |
| Worst case (everyone at once, synchronous event) | 30-50% | 3,000-5,000 |

**Planning target: 1,500 steady, 2,500 peak.**

Idle culling at 20 minutes means each "slot" serves ~8-12 learners per day. A 1,500-slot cluster handles 10,000+ DAU comfortably.

---

## Per-User Resource Profile

From mybinder.org data: **90% of users consume <10% CPU and <200 MB RAM.**

For a learning platform (basic Python, SQL, no heavy ML):

| Resource | Guarantee (reserved) | Limit (max) |
|----------|---------------------|-------------|
| RAM | 512 MB | 1 GB |
| CPU | 0.1 vCPU | 0.5 vCPU |
| Disk | 2 GB (NFS home dir) | — |
| Terminal | ~10 MB additional | — |

The **guarantee** is what determines node packing. With 512 MB guarantee and ~28 GB usable per node (32 GB minus system overhead), each node fits ~54 user pods.

---

## Infrastructure Cost Breakdown (AWS)

### Fixed Costs (always running)

| Component | Spec | Monthly |
|-----------|------|---------|
| EKS control plane | $0.10/hr | $73 |
| Core nodes (hub, proxy, monitoring) | 2× m5.xlarge (4 vCPU, 16 GB) on-demand | $280 |
| **Fixed total** | | **$353** |

### User Compute (autoscaled, spot instances)

Using m5.2xlarge nodes (8 vCPU, 32 GB). Spot price ~$0.134/hr (65% off on-demand).

| Period | Nodes | Hours/Day | Days/Month | Monthly |
|--------|-------|-----------|------------|---------|
| Peak (1,500-2,500 users) | 28-47 | 4 hrs | 22 weekdays | ~$550 |
| Steady (1,000-1,500 users) | 19-28 | 10 hrs | 22 weekdays | ~$1,250 |
| Weekend (50% traffic) | 10-15 | 14 hrs | 8 days | ~$300 |
| Overnight (near zero) | 2-5 | 10 hrs | 30 days | ~$200 |
| On-demand fallback (10% buffer) | 3-5 | — | — | ~$400 |
| **Compute total** | | | | **~$2,700** |

### Storage

| Option | Size | Monthly |
|--------|------|---------|
| EFS with Intelligent Tiering | 20 TB (2 GB × 10K users) | ~$2,000 |
| Alternative: EBS gp3 volumes | 20 TB | ~$1,600 |

EFS is operationally simpler (shared filesystem, no reattach on pod restart). Most learner home dirs are cold storage (infrequently accessed), so Intelligent Tiering helps.

**Storage total: ~$2,000**

### Networking

| Component | Monthly |
|-----------|---------|
| Network Load Balancer | ~$48 |
| Data transfer (~2 TB egress) | ~$180 |
| **Network total** | **~$230** |

---

## AWS Total

| Component | Monthly |
|-----------|---------|
| Fixed (control plane + core nodes) | $353 |
| User compute (spot, autoscaled) | $2,700 |
| Storage (EFS) | $2,000 |
| Networking | $230 |
| **Infrastructure total** | **$5,283** |

---

## Cross-Cloud Comparison

All three major clouds land in the same range:

| Provider | Monthly Total | Per DAU |
|----------|-------------|---------|
| AWS (EKS) | ~$5,300 | $0.53 |
| GCP (GKE) | ~$5,500 | $0.55 |
| Azure (AKS) | ~$5,400 | $0.54 |

**Without spot instances or autoscaling:** 2.5-3× higher → $13,000-16,000/month.

---

## Managed Service Option: 2i2c

[2i2c](https://2i2c.org) manages JupyterHub deployments for research and education.

| Component | Monthly |
|-----------|---------|
| Operations fee (managed hub) | $1,500 |
| Cloud infrastructure (pass-through) | ~$5,300 |
| **Total** | **~$6,800** |

You avoid hiring/allocating a DevOps engineer (saves $5-10K/month in staff cost). They handle deployment, upgrades, monitoring, incident response, and provide Grafana dashboards for usage tracking.

---

## What Drives Cost Up

| Change | Impact |
|--------|--------|
| On-demand instead of spot | +$5,000/month (+95%) |
| No autoscaling (24/7 peak) | +$3,000/month (+57%) |
| 1 GB RAM guarantee (instead of 512 MB) | +$2,500/month (+47%) |
| GPU access for ML courses | +$5,000-20,000/month |
| 5 GB storage per user (instead of 2 GB) | +$3,000/month |

## What Drives Cost Down

| Change | Impact |
|--------|--------|
| Only 2,000 DAU need servers (rest use browser) | -60% → ~$2,100/month |
| Aggressive culling (10 min instead of 20) | -15-20% |
| Smaller RAM guarantee (256 MB) | -30% |
| Fewer total users with persistent storage | Storage scales linearly |

---

## Hybrid Cost Model (Option C)

If 80% of learners use the in-browser engine (free) and only 20% need server-side:

| Tier | Users | Monthly Infra |
|------|-------|--------------|
| Browser (Pyodide + sql.js) | 8,000 DAU | $0 |
| Server (JupyterHub) | 2,000 DAU | ~$1,500-2,500 |
| **Total** | 10,000 DAU | **~$1,500-2,500** |

This is the strongest argument for the hybrid approach.

---

## Comparison Table

| Metric | Browser Only | Full JupyterHub | Hybrid | 2i2c Managed |
|--------|-------------|----------------|--------|-------------|
| Monthly cost | $0 | ~$5,300 | ~$2,000 | ~$6,800 |
| Per DAU | $0 | $0.53 | $0.20 | $0.68 |
| Annual | $0 | ~$64,000 | ~$24,000 | ~$82,000 |
| DevOps needed | No | Yes (0.5-1 FTE) | Yes (0.25 FTE) | No |
| Terminal support | No | Yes | Partial | Yes |
| Offline capable | Yes | No | Partial | No |
| Scale ceiling | Client device | Cloud budget | Cloud budget | Cloud budget |

---

## Real-World References

**UC Berkeley DataHub** — 3,000+ students in Data 8, GKE, managed by 2i2c.

**mybinder.org** — Hundreds concurrent. 90% of users use <200 MB RAM. Node packing is very efficient for educational workloads.

**NASA SMCE** — AWS EKS, ephemeral hubs for events. Pay-per-use model.

**Key insight from all of these:** Educational workloads are extremely bursty and extremely light. Most learners are typing, not computing. The 512 MB guarantee with 2:1 oversubscription works because only ~10% of users are actively executing at any moment.

---

## Sources

- [JupyterHub Capacity Planning](https://jupyterhub.readthedocs.io/en/latest/explanation/capacity-planning.html)
- [Zero to JupyterHub — Cost Projection](https://z2jh.jupyter.org/en/latest/administrator/cost.html)
- [Zero to JupyterHub — Optimization](https://z2jh.jupyter.org/en/stable/administrator/optimization.html)
- [2i2c Cloud Cost Estimation](https://docs.2i2c.org/topic/cloud-costs/)
- [UC Berkeley → Filestore Migration](https://cloud.google.com/blog/products/storage-data-transfer/uc-berkeley-migrates-to-filestore-for-jupyterhub/)
- [Pangeo Cloud Costs](https://medium.com/pangeo/pangeo-cloud-costs-part1-f89842da411d)
- [AWS EKS Pricing](https://aws.amazon.com/eks/pricing/)
- [AWS Spot Pricing](https://aws.amazon.com/ec2/spot/pricing/)
