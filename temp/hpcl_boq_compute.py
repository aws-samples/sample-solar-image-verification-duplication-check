#!/usr/bin/env python3
"""
HPCL BoQ — AWS cost estimate for Y1 (30% ramp) monthly.

Walks every BoQ line item, applies Y1 quantity × unit price,
emits markdown summary + detailed CSV to disk.

Usage:
    uv run temp/hpcl_boq_compute.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
PRICES = json.loads((HERE / "hpcl_boq_prices.json").read_text())

HRS = 730  # hours per month

# -----------------------------------------------------------------------------
# BoQ line items: (id, category, service, config, qty_y1, unit_price, monthly_cost, notes)
# Y1 quantities are taken from the "Y1 (30%)" column of BoQ-HPCL.xlsx.
# For "Per Hour" items, Y1 = count of instance-hours for the month (count × 730
# or count × stated hours). For monthly unit items, Y1 = count of units.
# -----------------------------------------------------------------------------

items = []

def add(idx, category, service, config, qty_y1, unit, unit_price, monthly_cost, notes=""):
    items.append({
        "id": idx,
        "category": category,
        "service": service,
        "config": config,
        "qty_y1": qty_y1,
        "unit": unit,
        "unit_price_usd": round(unit_price, 6),
        "monthly_cost_usd": round(monthly_cost, 2),
        "annual_cost_usd": round(monthly_cost * 12, 2),
        "notes": notes,
    })

OD = PRICES["ec2_ondemand_hourly"]
RI1 = PRICES["ec2_ri_1yr_noupfront_hourly"]
RI3 = PRICES["ec2_ri_3yr_noupfront_hourly"]
STG = PRICES["storage_monthly_per_gb"]
RDS = PRICES["rds_ondemand_hourly_ap_south_1"]
SVL = PRICES["serverless_ap_south_1"]
NET = PRICES["networking_ap_south_1"]
ANL = PRICES["analytics_ap_south_1"]
SEC = PRICES["security_ap_south_1"]
DEV = PRICES["devops_ap_south_1"]

# ==== 1. COMPUTE & CONTAINERS - ON DEMAND =====================================
# Y1 hours per row = count_y1 × hours_per_vm_per_month (from BoQ Qty/Month col)

# Rows 1-3: Linux VM On-Demand 4/8/16 vCPU, Y1 count=180/120/60, hours=730
add(1,  "1. Compute On-Demand", "EC2 m6i.xlarge Linux OD",   "4 vCPU, 8GB RAM Linux",    180*730, "hour", OD["m6i.xlarge_linux"],  180*730*OD["m6i.xlarge_linux"])
add(2,  "1. Compute On-Demand", "EC2 m6i.2xlarge Linux OD",  "8 vCPU, 16GB RAM Linux",   120*730, "hour", OD["m6i.2xlarge_linux"], 120*730*OD["m6i.2xlarge_linux"])
add(3,  "1. Compute On-Demand", "EC2 m6i.4xlarge Linux OD",  "16 vCPU, 32GB RAM Linux",  60*500,  "hour", OD["m6i.4xlarge_linux"], 60*500*OD["m6i.4xlarge_linux"], "500 hrs/mo per BoQ Qty col")

# Rows 4-6: RHEL VM OD
add(4,  "1. Compute On-Demand", "EC2 m6i.xlarge RHEL OD",    "4 vCPU, 8GB RAM RHEL",     60*500,  "hour", OD["m6i.xlarge_rhel"],  60*500*OD["m6i.xlarge_rhel"], "500 hrs/mo")
add(5,  "1. Compute On-Demand", "EC2 m6i.2xlarge RHEL OD",   "8 vCPU, 16GB RAM RHEL",    30*500,  "hour", OD["m6i.2xlarge_rhel"], 30*500*OD["m6i.2xlarge_rhel"], "500 hrs/mo")
add(6,  "1. Compute On-Demand", "EC2 m6i.4xlarge RHEL OD",   "16 vCPU, 32GB RAM RHEL",   30*500,  "hour", OD["m6i.4xlarge_rhel"], 30*500*OD["m6i.4xlarge_rhel"], "500 hrs/mo")

# Rows 7-9: Windows Server OD
add(7,  "1. Compute On-Demand", "EC2 m6i.xlarge Windows OD", "4 vCPU, 8GB RAM Win",      60*500,  "hour", OD["m6i.xlarge_windows"],  60*500*OD["m6i.xlarge_windows"], "500 hrs/mo")
add(8,  "1. Compute On-Demand", "EC2 m6i.2xlarge Windows OD","8 vCPU, 16GB RAM Win",     30*500,  "hour", OD["m6i.2xlarge_windows"], 30*500*OD["m6i.2xlarge_windows"], "500 hrs/mo")
add(9,  "1. Compute On-Demand", "EC2 m6i.4xlarge Windows OD","16 vCPU, 32GB RAM Win",    30*500,  "hour", OD["m6i.4xlarge_windows"], 30*500*OD["m6i.4xlarge_windows"], "500 hrs/mo")

# Rows 10-15: Memory-heavy OD (r6i family) and burst VMs
# Row 10: 8 vCPU 32GB Linux OD = m6i.2xlarge (32GB), 30 count x 400 hrs
add(10, "1. Compute On-Demand", "EC2 m6i.2xlarge Linux OD (burst)", "8 vCPU, 32GB Linux", 30*400,  "hour", OD["m6i.2xlarge_linux"], 30*400*OD["m6i.2xlarge_linux"], "400 hrs/mo per BoQ note")
# Row 11: 8 vCPU 64GB Linux = r6i.2xlarge, 30 x 400
add(11, "1. Compute On-Demand", "EC2 r6i.2xlarge Linux OD", "8 vCPU, 64GB Linux",         30*400,  "hour", OD["r6i.2xlarge_linux"], 30*400*OD["r6i.2xlarge_linux"], "400 hrs/mo")
# Row 12: 16 vCPU 128GB Linux = r6i.4xlarge, 30 x 400
add(12, "1. Compute On-Demand", "EC2 r6i.4xlarge Linux OD", "16 vCPU, 128GB Linux",       30*400,  "hour", OD["r6i.4xlarge_linux"], 30*400*OD["r6i.4xlarge_linux"], "400 hrs/mo")
# Row 13: 8 vCPU 32GB Windows = m6i.2xlarge win, 30 x 400
add(13, "1. Compute On-Demand", "EC2 m6i.2xlarge Win OD", "8 vCPU, 32GB Windows",         30*400,  "hour", OD["m6i.2xlarge_windows"], 30*400*OD["m6i.2xlarge_windows"], "400 hrs/mo")
# Row 14: 16 vCPU 64GB RHEL = m6i.4xlarge rhel, 6 x 730
add(14, "1. Compute On-Demand", "EC2 m6i.4xlarge RHEL OD", "16 vCPU, 64GB RHEL",          6*730,   "hour", OD["m6i.4xlarge_rhel"], 6*730*OD["m6i.4xlarge_rhel"])
# Row 15: 16 vCPU 32GB Windows = m6i.4xlarge win, 30 x 500
add(15, "1. Compute On-Demand", "EC2 m6i.4xlarge Win OD", "16 vCPU, 32GB Windows",        30*500,  "hour", OD["m6i.4xlarge_windows"], 30*500*OD["m6i.4xlarge_windows"], "500 hrs/mo")

# Rows 16-19: GPU VMs
# 16: 32 vCPU 128GB RHEL + 1 GPU >24GB -> g5.12xlarge (48v 192GB 4xA10G 96GB) nearest, or g5.4xlarge×1 GPU fits 24GB. 32v/128GB suggests g5.12xlarge best. 12 x 200
add(16, "1. Compute On-Demand", "EC2 g5.12xlarge RHEL OD (GPU)", "32 vCPU, 128GB RHEL, 1x GPU >24GB (A10G 96GB)", 12*200, "hour", OD["g5.12xlarge_rhel"], 12*200*OD["g5.12xlarge_rhel"], "200 hrs/mo; g5.12xlarge = 4x A10G 24GB each, 96GB total — closest match")
# 17: 32 vCPU 128GB + 1 GPU >40GB -> p4d closest (96v/1152GB 8xA100 40GB); scale down via g5 not available. 6 x 200
add(17, "1. Compute On-Demand", "EC2 p4d.24xlarge RHEL OD (GPU 40GB)", "GPU 40GB+ RHEL (p4d closest)", 6*200, "hour", OD["p4d.24xlarge_rhel"], 6*200*OD["p4d.24xlarge_rhel"], "200 hrs/mo; p4d.24xlarge = 8x A100 40GB; over-provisions CPU/RAM but only 40GB+ GPU option")
# 18: 96 vCPU 1000GB + 1 GPU >24GB -> g5.48xlarge (192v/768GB 8xA10G) closest; 6 x 200
add(18, "1. Compute On-Demand", "EC2 g5.48xlarge RHEL OD (GPU)", "96v/1000GB RHEL, GPU >24GB", 6*200, "hour", OD["g5.48xlarge_rhel"], 6*200*OD["g5.48xlarge_rhel"], "200 hrs/mo; g5.48xlarge closest match")
# 19: 96 vCPU 1000GB + 1 GPU >40GB -> p4d.24xlarge; 6 x 200
add(19, "1. Compute On-Demand", "EC2 p4d.24xlarge RHEL OD (GPU 40GB)", "96v/1000GB RHEL, GPU >40GB", 6*200, "hour", OD["p4d.24xlarge_rhel"], 6*200*OD["p4d.24xlarge_rhel"], "200 hrs/mo; p4d.24xlarge = 96 vCPU 1152GB 8x A100 40GB")

# Row 20: Bastion/Session Manager 5GB outbound, 60 units × 1 month
add(20, "1. Compute On-Demand", "Systems Manager Session Manager + Data Transfer", "Bastion 5GB outbound per session", 60, "month", 0.80, 60*0.80, "5GB egress @ $0.1093 + AWS Session Manager (free, but data transfer billed)")

# Row 21: ECR 100GB, 600 units × 1
add(21, "1. Compute On-Demand", "Amazon ECR", "100 GB container registry storage", 600*100, "GB-month", SVL["ecr_per_gb_month"], 600*100*SVL["ecr_per_gb_month"], "600 registries × 100GB each = 60,000 GB-month; realistic ECR storage likely lower in practice")

# Row 22: Lambda 2M invocations, 1GB / 5000ms avg, 30 units
# Cost per fn per month: 2M req × $0.20/M = $0.40 + 2M × 5s × 1GB × $0.00001667 = $0.40 + $166.67 = $167.07
lambda_req_cost = 30 * 2_000_000 / 1_000_000 * SVL["lambda_per_million_requests"]
lambda_gb_sec = 30 * 2_000_000 * 5 * 1 * SVL["lambda_per_gb_second"]
add(22, "1. Compute On-Demand", "AWS Lambda", "30 functions × 2M inv × 1GB × 5000ms", 30, "function", 167.07, lambda_req_cost + lambda_gb_sec)

# Row 23: Fargate 10000 vCPU-hr @ 2vCPU, 4GB, 180 units × 400 hrs each × 2 vCPU = vCPU-hours
# BoQ: 180 tasks × 400 hrs. vCPU-hr = 180 × 400 × 2 = 144000, GB-hr = 180 × 400 × 4 = 288000
far_vcpu_cost = 180 * 400 * 2 * SVL["fargate_per_vcpu_hour"]
far_gb_cost = 180 * 400 * 4 * SVL["fargate_per_gb_hour"]
add(23, "1. Compute On-Demand", "AWS Fargate", "180 tasks × 400 hrs × 2vCPU/4GB", 180*400, "task-hour", round((far_vcpu_cost+far_gb_cost)/(180*400), 4), far_vcpu_cost + far_gb_cost)

# Row 24: EKS clusters, 24 units × 1
add(24, "1. Compute On-Demand", "Amazon EKS", "Managed Kubernetes control plane", 24, "cluster-month", SVL["eks_cluster_per_hour"]*730, 24 * SVL["eks_cluster_per_hour"] * 730)

# ==== 2. COMPUTE - RESERVED ===================================================
# Rows 25-27: Linux 1yr RI - 8/16/32 vCPU
add(25, "2. Compute Reserved", "EC2 m6i.2xlarge Linux 1yr-NU", "8 vCPU, 16GB Linux", 60*730, "hour", RI1["m6i.2xlarge_linux"], 60*730*RI1["m6i.2xlarge_linux"])
add(26, "2. Compute Reserved", "EC2 m6i.4xlarge Linux 1yr-NU", "16 vCPU, 32GB Linux", 30*730, "hour", RI1["m6i.4xlarge_linux"], 30*730*RI1["m6i.4xlarge_linux"])
add(27, "2. Compute Reserved", "EC2 m6i.8xlarge Linux 1yr-NU", "32 vCPU, 64GB Linux (128GB rounded)", 12*730, "hour", RI1["m6i.8xlarge_linux"], 12*730*RI1["m6i.8xlarge_linux"])

# Rows 28-30: RHEL 1yr RI
add(28, "2. Compute Reserved", "EC2 m6i.2xlarge RHEL 1yr-NU", "8 vCPU, 16GB RHEL",  60*730, "hour", RI1["m6i.2xlarge_rhel"], 60*730*RI1["m6i.2xlarge_rhel"])
add(29, "2. Compute Reserved", "EC2 m6i.4xlarge RHEL 1yr-NU", "16 vCPU, 32GB RHEL", 30*730, "hour", RI1["m6i.4xlarge_rhel"], 30*730*RI1["m6i.4xlarge_rhel"])
add(30, "2. Compute Reserved", "EC2 m6i.8xlarge RHEL 1yr-NU", "32 vCPU, 64GB RHEL", 12*730, "hour", RI1["m6i.8xlarge_rhel"], 12*730*RI1["m6i.8xlarge_rhel"])

# Rows 31-33: Windows 1yr RI
add(31, "2. Compute Reserved", "EC2 m6i.2xlarge Win 1yr-NU",  "8 vCPU, 16GB Win",  60*730, "hour", RI1["m6i.2xlarge_windows"], 60*730*RI1["m6i.2xlarge_windows"])
add(32, "2. Compute Reserved", "EC2 m6i.4xlarge Win 1yr-NU",  "16 vCPU, 32GB Win", 30*730, "hour", RI1["m6i.4xlarge_windows"], 30*730*RI1["m6i.4xlarge_windows"])
add(33, "2. Compute Reserved", "EC2 m6i.8xlarge Win 1yr-NU",  "32 vCPU, 64GB Win", 12*730, "hour", RI1["m6i.8xlarge_windows"], 12*730*RI1["m6i.8xlarge_windows"])

# Rows 34-37: Larger memory 1yr RI
# 34: 8 vCPU 32GB Linux (1yr) = m6i.2xlarge
add(34, "2. Compute Reserved", "EC2 m6i.2xlarge Linux 1yr-NU", "8 vCPU, 32GB Linux 1yr", 30*730, "hour", RI1["m6i.2xlarge_linux"], 30*730*RI1["m6i.2xlarge_linux"])
# 35: 16 vCPU 64GB windows = m6i.4xlarge win
add(35, "2. Compute Reserved", "EC2 m6i.4xlarge Win 1yr-NU", "16 vCPU, 64GB Win 1yr", 30*730, "hour", RI1["m6i.4xlarge_windows"], 30*730*RI1["m6i.4xlarge_windows"])
# 36: 32 vCPU 128GB windows = m6i.8xlarge win
add(36, "2. Compute Reserved", "EC2 m6i.8xlarge Win 1yr-NU", "32 vCPU, 128GB Win 1yr", 30*730, "hour", RI1["m6i.8xlarge_windows"], 30*730*RI1["m6i.8xlarge_windows"])
# 37: 32 vCPU 128GB RHEL = m6i.8xlarge rhel
add(37, "2. Compute Reserved", "EC2 m6i.8xlarge RHEL 1yr-NU", "32 vCPU, 128GB RHEL 1yr", 30*730, "hour", RI1["m6i.8xlarge_rhel"], 30*730*RI1["m6i.8xlarge_rhel"])

# Rows 38-40: 3yr RI (but Y1 = first year of 3yr term, same monthly rate)
# 38: 8 vCPU 64GB Linux 3yr = r6i.2xlarge linux 3yr
add(38, "2. Compute Reserved", "EC2 r6i.2xlarge Linux 3yr-NU", "8 vCPU, 64GB Linux 3yr", 30*730, "hour", RI3["r6i.2xlarge_linux"], 30*730*RI3["r6i.2xlarge_linux"])
# 39: 16 vCPU 128GB Linux 3yr = r6i.4xlarge linux 3yr
add(39, "2. Compute Reserved", "EC2 r6i.4xlarge Linux 3yr-NU", "16 vCPU, 128GB Linux 3yr", 30*730, "hour", RI3["r6i.4xlarge_linux"], 30*730*RI3["r6i.4xlarge_linux"])
# 40: 32 vCPU 256GB Windows 3yr = r6i.8xlarge win 3yr
add(40, "2. Compute Reserved", "EC2 r6i.8xlarge Win 3yr-NU", "32 vCPU, 256GB Win 3yr", 30*730, "hour", RI3["r6i.8xlarge_windows"], 30*730*RI3["r6i.8xlarge_windows"])

# Rows 41-43: Linux 3yr RI
add(41, "2. Compute Reserved", "EC2 m6i.2xlarge Linux 3yr-NU", "8 vCPU, 16GB Linux 3yr",  60*730, "hour", RI3["m6i.2xlarge_linux"], 60*730*RI3["m6i.2xlarge_linux"])
add(42, "2. Compute Reserved", "EC2 m6i.4xlarge Linux 3yr-NU", "16 vCPU, 32GB Linux 3yr", 30*730, "hour", RI3["m6i.4xlarge_linux"], 30*730*RI3["m6i.4xlarge_linux"])
add(43, "2. Compute Reserved", "EC2 m6i.8xlarge Linux 3yr-NU", "32 vCPU, 64GB Linux 3yr", 12*730, "hour", RI3["m6i.8xlarge_linux"], 12*730*RI3["m6i.8xlarge_linux"])

# Rows 44-46: RHEL 3yr RI
add(44, "2. Compute Reserved", "EC2 m6i.2xlarge RHEL 3yr-NU", "8 vCPU, 16GB RHEL 3yr",  60*730, "hour", RI3["m6i.2xlarge_rhel"], 60*730*RI3["m6i.2xlarge_rhel"])
add(45, "2. Compute Reserved", "EC2 m6i.4xlarge RHEL 3yr-NU", "16 vCPU, 32GB RHEL 3yr", 30*730, "hour", RI3["m6i.4xlarge_rhel"], 30*730*RI3["m6i.4xlarge_rhel"])
add(46, "2. Compute Reserved", "EC2 m6i.8xlarge RHEL 3yr-NU", "32 vCPU, 64GB RHEL 3yr", 12*730, "hour", RI3["m6i.8xlarge_rhel"], 12*730*RI3["m6i.8xlarge_rhel"])

# Rows 47-49: Windows 3yr RI
add(47, "2. Compute Reserved", "EC2 m6i.2xlarge Win 3yr-NU",  "8 vCPU, 16GB Win 3yr",  60*730, "hour", RI3["m6i.2xlarge_windows"], 60*730*RI3["m6i.2xlarge_windows"])
add(48, "2. Compute Reserved", "EC2 m6i.4xlarge Win 3yr-NU",  "16 vCPU, 32GB Win 3yr", 30*730, "hour", RI3["m6i.4xlarge_windows"], 30*730*RI3["m6i.4xlarge_windows"])
add(49, "2. Compute Reserved", "EC2 m6i.8xlarge Win 3yr-NU",  "32 vCPU, 64GB Win 3yr", 12*730, "hour", RI3["m6i.8xlarge_windows"], 12*730*RI3["m6i.8xlarge_windows"])

# ==== 3. STORAGE & DATA PROTECTION ============================================
# Row 50: gp3 ≥500 IOPS, Y1 = 90 × 1024 = 92160 GB-month  (but BoQ says 30TB total across envs; Y1 = 30% × 1024 × 90/15)
# BoQ Qty/Month shows "15 × 1024 = 15360" for total contract; Y1 row = 90 TB-equivalent units (column × 1024 GB)
# Use Y1 × 1024 GB
add(50, "3. Storage", "EBS gp3 500 IOPS", "SSD baseline 500 IOPS, 125 MB/s", 90*1024, "GB-month", STG["ebs_gp3"], 90*1024*STG["ebs_gp3"])
add(51, "3. Storage", "EBS gp3 3000 IOPS", "SSD baseline 3000 IOPS, 125 MB/s", 150*1024, "GB-month", STG["ebs_gp3"], 150*1024*STG["ebs_gp3"])
add(52, "3. Storage", "EBS io2 5000 IOPS", "SSD 5000 IOPS premium", 60*1024, "GB-month", STG["ebs_io2"], 60*1024*STG["ebs_io2"])
# Row 53: S3 Hot Tier
add(53, "3. Storage", "S3 Standard (HOT)", "Hot-tier object storage, versioning + object-lock", 60*1024, "GB-month", STG["s3_standard"], 60*1024*STG["s3_standard"])
# Row 54: S3 Standard-IA (COOL)
add(54, "3. Storage", "S3 Standard-IA (COOL)", "Infrequent-access tier", 72*1024, "GB-month", STG["s3_standard_ia"], 72*1024*STG["s3_standard_ia"])
# Row 55: S3 Glacier Deep Archive
add(55, "3. Storage", "S3 Glacier Deep Archive", "Long-term archive, 15hr retrieve", 96*1024, "GB-month", STG["s3_glacier_deep_archive"], 96*1024*STG["s3_glacier_deep_archive"])
# Row 56: EFS
add(56, "3. Storage", "Amazon EFS", "Managed NFS/SMB shared file", 60*1024, "GB-month", STG["efs_standard"], 60*1024*STG["efs_standard"])
# Row 57: AWS Backup
add(57, "3. Storage", "AWS Backup", "Managed backup with WORM", 60*1024, "GB-month", STG["backup_warm"], 60*1024*STG["backup_warm"])
# Row 58: EBS Snapshots
add(58, "3. Storage", "EBS Snapshots", "Point-in-time volume snapshots", 30*1024, "GB-month", STG["ebs_snapshot"], 30*1024*STG["ebs_snapshot"])

# ==== 4. DATABASE & CACHING ===================================================
# Row 59a: Aurora PostgreSQL r6g.8xlarge x2 (Prod+UAT) 32v/128G, 24 count Y1 × 730 hrs
add(59, "4. Database", "Aurora PostgreSQL db.r6g.8xlarge", "32vCPU/128GB, Multi-AZ, 200GB 3000 IOPS", 24*730, "hour", RDS["aurora_postgres_r6g_8xlarge"], 24*730*RDS["aurora_postgres_r6g_8xlarge"])
# Row 59b: smaller variant - r6g.4xlarge 16v/64GB, 12 x 730
add(59.1, "4. Database", "Aurora PostgreSQL db.r6g.4xlarge", "16vCPU/64GB, Multi-AZ, 200GB", 12*730, "hour", RDS["aurora_postgres_r6g_4xlarge"], 12*730*RDS["aurora_postgres_r6g_4xlarge"])
# Row 59c: Aurora storage ~500 GB/cluster × (2+4=6 clusters) = 3000 GB
add(59.2, "4. Database", "Aurora PostgreSQL Storage", "500 GB × 6 clusters", 3000, "GB-month", RDS["aurora_storage_per_gb_month"], 3000*RDS["aurora_storage_per_gb_month"])
# Row 60: RDS MySQL r6i.8xlarge Multi-AZ, 24 count × 730
add(60, "4. Database", "RDS MySQL db.r6i.8xlarge Multi-AZ", "32vCPU/128GB, 200GB, 3000 IOPS", 24*730, "hour", RDS["rds_mysql_r6i_8xlarge_multiaz"], 24*730*RDS["rds_mysql_r6i_8xlarge_multiaz"])
add(60.1,"4. Database", "RDS MySQL db.r6i.4xlarge Multi-AZ", "16vCPU/64GB, 200GB", 24*730, "hour", RDS["rds_mysql_r6i_4xlarge_multiaz"], 24*730*RDS["rds_mysql_r6i_4xlarge_multiaz"])
add(60.2,"4. Database", "RDS MySQL Storage gp3", "200GB × 6 instances", 1200, "GB-month", RDS["rds_storage_gp3_per_gb_month"], 1200*RDS["rds_storage_gp3_per_gb_month"])
# Row 61: RDS SQL Server EE Multi-AZ
add(61, "4. Database", "RDS SQL Server EE db.r6i.4xlarge Multi-AZ", "16vCPU/64GB, 200GB", 24*730, "hour", RDS["rds_sqlserver_ee_r6i_4xlarge_multiaz"], 24*730*RDS["rds_sqlserver_ee_r6i_4xlarge_multiaz"])
add(61.1,"4. Database", "RDS SQL Server EE db.r6i.8xlarge Multi-AZ", "32vCPU/128GB, 200GB", 12*730, "hour", RDS["rds_sqlserver_ee_r6i_8xlarge_multiaz"], 12*730*RDS["rds_sqlserver_ee_r6i_8xlarge_multiaz"])
# Row 62: DynamoDB on-demand, 1M write + 10M read, 100GB + 500GB storage. Take Y1 count = 6 + 12 = 18
# 6M writes + 60M reads + 100GB + 12M write + 120M read + 500GB = 18M writes + 180M reads + 600GB
ddb_w = 18 * RDS["dynamodb_ondemand_write_per_million"]
ddb_r = 180 * RDS["dynamodb_ondemand_read_per_million"]
ddb_s = 600 * RDS["dynamodb_storage_per_gb"]
add(62, "4. Database", "DynamoDB On-Demand", "18M write + 180M read + 600GB storage", 1, "bundle", ddb_w+ddb_r+ddb_s, ddb_w+ddb_r+ddb_s)
# Row 63: Timestream (serverless) 500GB/mo, 18 node-months. We price as memory store GB-hr approx.
# 500GB × 730 hr = 365000 GB-hr × $0.045 = $16425/month for Y1 3 nodes = rough
add(63, "4. Database", "Timestream", "3 nodes, 500 GB/mo telemetry", 500*730, "GB-hour", RDS["timestream_memory_per_gb_hour"], 500*730*RDS["timestream_memory_per_gb_hour"])
# Row 64: ElastiCache Redis 120GB cache - need ~5 cache.r7g.xlarge nodes (26GB each)
# 720 unit Y1 means 6 nodes; r7g.xlarge × 730 hr × 6 nodes = 6*730 = 4380 hr
add(64, "4. Database", "ElastiCache Redis cache.r7g.xlarge", "6 nodes × 26GB clustered Redis", 6*730, "node-hour", RDS["elasticache_r7g_xlarge_hourly"], 6*730*RDS["elasticache_r7g_xlarge_hourly"])

# ==== 5. DATA PLATFORM & ANALYTICS ============================================
# Row 65: QuickSight Developer (Author) license, 120 users Y1
add(65, "5. Analytics", "QuickSight Authors", "Developer licenses", 120, "user-month", ANL["quicksight_author_per_user"], 120*ANL["quicksight_author_per_user"])
# Row 66: Bundled Unified Data Platform — marked as OR with #67-71; treat as quote-based
add(66, "5. Analytics", "Databricks Unity Platform (Marketplace)", "Bundled option — 32v/128GB capacity", 0, "quote", 0, 0, "Quote-based Marketplace ISV — not priced")
# Row 67: EMR 5 nodes × 240 hrs, r6g.8xlarge (32v/128GB)
add(67, "5. Analytics", "EMR r6g.8xlarge", "5 nodes × 240 hrs", 30*240, "node-hour", ANL["emr_r6g_8xlarge_per_hour"], 30*240*ANL["emr_r6g_8xlarge_per_hour"], "Includes EMR service fee")
# Row 68: Kinesis on-demand 13 MB/s. 13MB/s × 86400 × 30 = 33.7TB/month = 33700 GB
# Y1: 3000 × 1 × 12 = 36000 GB/month equivalent
add(68, "5. Analytics", "Kinesis Data Streams On-Demand", "500 GB/month × 60 units Y1 = 30,000 GB", 3000, "GB-ingested", ANL["kinesis_ondemand_per_gb_ingested"], 3000*ANL["kinesis_ondemand_per_gb_ingested"])
# Row 69: Glue 200 DPU-hours/mo, Y1=1200
add(69, "5. Analytics", "AWS Glue ETL", "200 DPU-hours × 6 Y1", 1200, "DPU-hour", ANL["glue_dpu_hour"], 1200*ANL["glue_dpu_hour"])
# Row 70a: BI Developer (65 above) AND Row 70 has Developer+Viewer split
# 70 Developer: 60 users (already Y1)
add(70, "5. Analytics", "QuickSight Authors (Row 70)", "60 Developer licenses", 60, "user-month", ANL["quicksight_author_per_user"], 60*ANL["quicksight_author_per_user"])
# 70 Viewer: 27000 users Y1 at $0.30/session capped ~$5/user
# QuickSight Reader pay-per-session: cap $5/user. Assume 4500 users × $5 cap
add(70.1,"5. Analytics", "QuickSight Readers (pay-session)", "4,500 Reader licenses (capped)", 4500, "user-month", 5.00, 4500*5.00, "Pay-per-session capped at $5/user/mo")
# Row 71: Redshift Serverless 1 DW × 730 hrs @ 8 RPU baseline = 8 × 730 = 5840 RPU-hr
add(71, "5. Analytics", "Redshift Serverless", "1 DW cluster equiv, 8 RPU baseline × 730 hrs", 12*730, "RPU-hour", ANL["redshift_serverless_rpu_hour"], 12*730*ANL["redshift_serverless_rpu_hour"], "Y1 count 12 × 730 hrs")

# ==== 6. DATA GOVERNANCE ======================================================
# Row 72a: Lake Formation (FREE)
add(72, "6. Data Governance", "AWS Lake Formation", "500 governed assets", 3000, "asset-month", 0.00, 0.00, "Lake Formation data catalog is FREE")
# Row 72b: Glue Data Quality - 1000 rules/day × 30 days × 180 Y1 units? 180000 rule-evaluations Y1
# BoQ Y1 = 180000 rule-evals / month. Price: Glue DQ = $0.44/DPU-hr; rough map 1000 evals ≈ 1 DPU-hr
# So 180000 evals = 180 DPU-hrs × $0.44
add(72.1,"6. Data Governance", "Glue Data Quality", "180,000 rule evaluations/mo", 180, "DPU-hour", ANL["glue_data_quality_dpu_hour"], 180*ANL["glue_data_quality_dpu_hour"])
# Row 73: Macie 1TB scanned
add(73, "6. Data Governance", "Amazon Macie", "1 TB PII scan/month", 6*1024, "GB-month", 1.00, 6*1024*1.00, "Macie ~$1/GB tiered — uses first-tier price")

# ==== 7. AI / ML / GenAI ======================================================
# Row 74: SageMaker Studio ml.m5.4xlarge 16v/64GB, 30 users Y1 × 730 hr
add(74, "7. AI/ML/GenAI", "SageMaker Studio Notebooks", "ml.m5.4xlarge × 30 users", 30*730, "instance-hour", SVL["sagemaker_notebook_ml_m5_4xlarge"], 30*730*SVL["sagemaker_notebook_ml_m5_4xlarge"])
# Row 75: Feature Store 200GB Y1 = 1200 GB-month
add(75, "7. AI/ML/GenAI", "SageMaker Feature Store", "200GB × 6 groups", 1200, "GB-month", 0.51, 1200*0.51)
# Row 76: Model Registry 100GB (S3-backed free service)
add(76, "7. AI/ML/GenAI", "SageMaker Model Registry", "100GB S3-backed storage", 600*100, "GB-month", STG["s3_standard"], 600*100*STG["s3_standard"], "Registry itself free, pay S3 storage")
# Row 77: Training ml.m5.4xlarge × 6 nodes × 730 hr, Y1 = 36 Y1 units
add(77, "7. AI/ML/GenAI", "SageMaker Training", "ml.m5.4xlarge × 36 instance-hours × 730", 36*730, "instance-hour", SVL["sagemaker_training_ml_m5_4xlarge"], 36*730*SVL["sagemaker_training_ml_m5_4xlarge"])
# Row 78: Real-time inference endpoint ml.m5.4xlarge × 2 endpoint × 730 hr Y1=12
add(78, "7. AI/ML/GenAI", "SageMaker Real-time Inference", "ml.m5.4xlarge endpoints", 12*730, "instance-hour", SVL["sagemaker_inference_ml_m5_4xlarge"], 12*730*SVL["sagemaker_inference_ml_m5_4xlarge"])
# Row 79: Model Monitor ml.m5.2xlarge × 2 nodes × 730 hr Y1=12
add(79, "7. AI/ML/GenAI", "SageMaker Model Monitor", "ml.m5.2xlarge × 12 instance-hours × 730", 12*730, "instance-hour", SVL["sagemaker_ml_m5_2xlarge_hourly"], 12*730*SVL["sagemaker_ml_m5_2xlarge_hourly"])
# Row 80: Bedrock Nova Pro 20M tokens/mo. Y1 = 150 unit at 1M tokens = 150M tokens; 60% input/40% output assumption
# Actually 150 × 1M = 150M, blended. Use 90M input + 60M output
bed_in = 90 * 1_000_000 / 1000 * SVL["bedrock_nova_pro_input_per_1k"]
bed_out = 60 * 1_000_000 / 1000 * SVL["bedrock_nova_pro_output_per_1k"]
add(80, "7. AI/ML/GenAI", "Bedrock Nova Pro (LLM)", "150M tokens/mo blended (90M in + 60M out)", 150, "M-tokens", round((bed_in+bed_out)/150,4), bed_in+bed_out)
# Row 81: OpenSearch Serverless vectors - 2 OCU indexing + 2 OCU search = 4 OCU × 730 hr
add(81, "7. AI/ML/GenAI", "OpenSearch Serverless (Vectors)", "4 OCU (2 ingest + 2 search) × 730 hr", 4*730, "OCU-hour", ANL["opensearch_ocu_per_hour"], 4*730*ANL["opensearch_ocu_per_hour"])
# Row 82: Titan embeddings 50GB corpus ≈ 25M tokens + query embeddings. 300 Y1 × 1M = 300M tokens
add(82, "7. AI/ML/GenAI", "Bedrock Titan Embeddings", "300M tokens/mo (50GB corpus + queries)", 300, "M-tokens", round(SVL["bedrock_titan_embed_v2_per_1k"]*1000, 6), 300 * 1_000_000 / 1000 * SVL["bedrock_titan_embed_v2_per_1k"])
# Row 83: Bedrock Agents 500 sessions/mo × 150 Y1 units. Bedrock Agents free, pay model tokens - already counted in #80
add(83, "7. AI/ML/GenAI", "Bedrock Agents", "500 sessions × 150 units — agents free, tokens in #80", 1800, "session", 0.00, 0.00, "Agents themselves free, underlying tokens priced in Row 80")
# Row 84: AgentCore Runtime 1 vCPU + 1GB × 100 hr
AI = PRICES["ai_services_ap_south_1"]
ac_v = 1 * 100 * AI["agentcore_runtime_vcpu_hour"]
ac_g = 1 * 100 * AI["agentcore_runtime_gb_hour"]
add(84, "7. AI/ML/GenAI", "Bedrock AgentCore Runtime", "1 vCPU + 1GB × 100 hr/mo", 100, "runtime-hour", round((ac_v+ac_g)/100, 4), ac_v+ac_g)
# Row 85: Textract 1M pages × 60 units Y1
add(85, "7. AI/ML/GenAI", "Amazon Textract", "60M pages/mo (detect-text)", 60_000_000, "page", SVL["textract_detect_per_page"], 60_000_000*SVL["textract_detect_per_page"])
# Row 86: Transcribe 1000 audio hrs × 60 units = 60000 hours = 3,600,000 minutes
add(86, "7. AI/ML/GenAI", "Amazon Transcribe", "60,000 audio hours/mo", 3_600_000, "minute", SVL["transcribe_per_minute"], 3_600_000*SVL["transcribe_per_minute"])
# Row 87: Translate 200M chars × 60 Y1 = 12,000M = 12,000 million char
add(87, "7. AI/ML/GenAI", "Amazon Translate", "12,000 M characters/mo", 12_000, "M-char", SVL["translate_per_million_chars"], 12_000*SVL["translate_per_million_chars"])
# Row 88: Amazon Location Service - 30k vehicles, 6000 Y1 × 1000 API req = 6M req/mo
add(88, "7. AI/ML/GenAI", "Amazon Location Service", "6M API requests (maps+tracking+geofence)", 6, "M-requests", 34.0, 6*34.0, "Blended rate across maps/tracking/geofence; tiered pricing")

# ==== 8. IoT & EDGE ===========================================================
# Row 89: IoT Core 60 units × 1M msg/mo = 60M messages. Price: 5KB × $1 per M msg
add(89, "8. IoT & Edge", "AWS IoT Core", "60M messages/mo, 5KB each", 60, "M-messages", 1.00, 60*1.00, "5KB/msg counted as 5 msgs each for IoT Core billing")
# Row 90: Edge Platform 25000 controllers - quote-based
add(90, "8. IoT & Edge", "IoT Edge Platform (Greengrass + 3P)", "25,000 controllers", 0, "quote", 0, 0, "Quote-based — Greengrass + partner ISV, not priced via calculator")

# ==== 9. SECURITY =============================================================
# Row 90 (dup): Shield Standard - FREE
add(90.1,"9. Security", "Shield Standard", "60 protected endpoints (always free)", 720, "endpoint-month", 0.00, 0.00, "Shield Standard is FREE")
# Row 91: Network Firewall 2 instances × 730 hr + 1TB data
nf_endpoint = 2 * 730 * SEC.get("privatelink_endpoint_per_hour", 0.013) * 30  # use NF endpoint
# Use actual Network Firewall pricing
nf_end_cost = 2 * 730 * 0.395  # $0.395/endpoint/hour
nf_data_cost = 1024 * 0.065    # $0.065/GB
add(91, "9. Security", "AWS Network Firewall", "2 endpoints × 730 hr + 1TB processed", 24*730, "endpoint-hour", 0.395, nf_end_cost + nf_data_cost)
# Row 92: WAF 2 instances × $5 + 10 rules × $1 + 50M req × $0.60/M
waf_acl = 24 * SEC["waf_web_acl_per_month"]
waf_rule = 24 * 10 * SEC["waf_rule_per_month"]
waf_req = 50 * 24 * SEC["waf_per_million_requests"]
add(92, "9. Security", "AWS WAF", "24 WAF instances, 10 rules each, 50M req/instance", 24, "WebACL", (waf_acl+waf_rule+waf_req)/24, waf_acl+waf_rule+waf_req)
# Row 93: Inspector 300 resources
add(93, "9. Security", "Amazon Inspector + GuardDuty", "300 resources scanned", 300, "resource-month", SEC["inspector_per_resource_month"], 300*SEC["inspector_per_resource_month"])
# Row 94: KMS 600 keys
add(94, "9. Security", "AWS KMS", "600 encryption keys", 600, "key-month", SEC["kms_key_per_month"], 600*SEC["kms_key_per_month"])
# Row 95: CloudHSM 12 instance-hours × 730 hr × 2 HA
add(95, "9. Security", "CloudHSM", "12 HSM instances × 730 hr (HA cluster)", 12*730, "hsm-hour", SEC["cloudhsm_per_hour"], 12*730*SEC["cloudhsm_per_hour"])
# Row 96: Security Hub / SIEM 2 GB logs/day × 30 Y1 = 60 GB-month × $0.75/GB ingest
add(96, "9. Security", "Security Hub + GuardDuty Logs", "12 GB/day × 30 days = 360 GB/mo", 12*30, "GB-day", 0.75, 12*30*0.75, "GuardDuty + Security Hub blended")

# ==== 10. NETWORKING ==========================================================
# Row 97: VPCs FREE (just accounting)
add(97, "10. Networking", "Amazon VPC", "30 VPCs", 30, "vpc-month", 0.00, 0.00, "VPC itself free")
# Row 98: NAT Gateway - 3000 Y1 units means 3000 GB processed and hours
# Actually: 500 GB/mo × 60 count? BoQ Y1=3000 GB. Plus NAT GW hourly for ~3 per AZ
nat_hours = 3 * 730 * NET["nat_gateway_per_hour"]
nat_data = 3000 * NET["nat_gateway_per_gb"]
add(98, "10. Networking", "NAT Gateway", "3 NATs × 730 hr + 3000 GB processed", 3000, "GB+hour", round((nat_hours+nat_data)/3000,4), nat_hours+nat_data)
# Row 99: Route 53 - 60 Y1 × 1M queries = 60M, 10 zones
r53_zones = 10 * NET["route53_hosted_zone_per_month"]
r53_q = 60 * NET["route53_queries_per_million"]
add(99, "10. Networking", "Route 53", "10 hosted zones + 60M queries", 60, "M-queries", round((r53_zones+r53_q)/60,4), r53_zones+r53_q)
# Row 100: ACM - FREE
add(100,"10. Networking", "ACM Certificates", "50 certs auto-renew", 300, "cert-month", 0.00, 0.00, "ACM free when used with ALB/CF/API GW")
# Row 101: PrivateLink 300 Y1 × $0.013/hr × 730
pl_cost = 300 * 730 * NET["vpc_endpoint_per_hour"]
add(101,"10. Networking", "PrivateLink Endpoints", "300 endpoint-months", 300*730, "endpoint-hour", NET["vpc_endpoint_per_hour"], pl_cost)
# Row 102: Direct Connect 200Mbps 2 ports × 730 hr. Y1 = 14 → 2 ports
add(102,"10. Networking", "Direct Connect 200Mbps", "2 ports × 730 hrs", 2*730, "port-hour", NET["direct_connect_200mbps_per_hour"], 2*730*NET["direct_connect_200mbps_per_hour"])
# Row 103: Direct Connect 1Gbps (Y1 not stated but included in 103 sub-row). Assume 0 Y1; covered at Y3+
add(103,"10. Networking", "Direct Connect 1Gbps", "Y1=0 ports (ramp Y3+)", 0, "port-hour", NET["direct_connect_1gbps_per_hour"], 0, "Y1 = 0 per BoQ; ramps in Y3+")
# Row 103b S2S VPN: 7 Y1 × 730 hrs
add(103.1,"10. Networking", "Site-to-Site VPN", "7 VPN connections × 730 hrs", 7*730, "vpn-hour", NET["s2s_vpn_per_hour"], 7*730*NET["s2s_vpn_per_hour"])
# Row 104: API Gateway 5M × 60 Y1 = 300M / month
add(104,"10. Networking", "API Gateway (HTTP/REST)", "300M API calls/mo", 300, "M-calls", NET["api_gw_rest_per_million"], 300*NET["api_gw_rest_per_million"])
# Row 105: Elastic IPs 360 Y1 (but only charged when unused) - assume 50% unused
add(105,"10. Networking", "Elastic IP (static public)", "360 IPs × 730 hr (50% unused assumption)", 180*730, "ip-hour", NET["elastic_ip_unused_per_hour"], 180*730*NET["elastic_ip_unused_per_hour"], "EIP free when attached; charged $0.005/hr unused")
# Row 106: ALB 30 Y1 instances × 730 hr + LCU
alb_cost_h = 30 * 730 * NET["alb_per_hour"]
alb_cost_lcu = 30 * 730 * 5 * NET["alb_lcu_hour"]  # assume 5 LCU avg
add(106,"10. Networking", "Application Load Balancer", "30 ALBs × 730 hrs × 5 LCU", 30*730, "alb-hour", round((alb_cost_h+alb_cost_lcu)/(30*730),4), alb_cost_h+alb_cost_lcu)
# Row 107: NLB 10 Y1
nlb_h = 10 * 730 * NET["nlb_per_hour"]
nlb_lcu = 10 * 730 * 3 * NET["nlb_nlcu_hour"]
add(107,"10. Networking", "Network Load Balancer", "10 NLBs × 730 hrs × 3 NLCU", 10*730, "nlb-hour", round((nlb_h+nlb_lcu)/(10*730),4), nlb_h+nlb_lcu)
# Row 108: Data Transfer Out 60 Y1 × 1 TB = 60TB
add(108,"10. Networking", "Data Transfer Out", "60 TB/mo egress", 60*1024, "GB", NET["data_transfer_out_per_gb"], 60*1024*NET["data_transfer_out_per_gb"])
# Row 109: CloudFront 60 Y1 × 1 TB = 60 TB/mo
add(109,"10. Networking", "CloudFront", "60 TB/mo India edge", 60*1024, "GB", NET["cloudfront_per_gb_india_asia"], 60*1024*NET["cloudfront_per_gb_india_asia"])
# Row 110: Inter-region DT 30 Y1 × 1 TB = 30 TB
add(110,"10. Networking", "Inter-Region Data Transfer", "30 TB/mo between regions", 30*1024, "GB", NET["interregion_transfer_per_gb"], 30*1024*NET["interregion_transfer_per_gb"])

# ==== 11. APPLICATION & DEVELOPER SERVICES ====================================
# Row 111: CloudWatch 500 GB logs × 6 units = 3000 GB
cw_ingest = 3000 * DEV["cloudwatch_logs_ingest_per_gb"]
cw_storage = 3000 * DEV["cloudwatch_logs_storage_per_gb"]
add(111,"11. DevOps", "CloudWatch Logs + X-Ray", "3,000 GB ingest + storage", 3000, "GB", round((cw_ingest+cw_storage)/3000,4), cw_ingest+cw_storage)
# Row 116: Multi-AZ HA - included in services - zero cost
add(116,"11. DevOps", "Multi-AZ HA", "Included with Prod services", 0, "included", 0, 0, "Baseline — all production Multi-AZ, no line item")
# Row 112: SQS/SNS 180 Y1 × 1M = 180M messages/month
sqs_cost = 180 * DEV["sqs_per_million"]
sns_cost = 90 * DEV["sns_per_million"]
add(112,"11. DevOps", "SQS + SNS", "180M SQS msgs + 90M SNS publishes", 180, "M-msgs", round((sqs_cost+sns_cost)/180,4), sqs_cost+sns_cost)
# Row 113: SES 4 Y1 × 1M = 4M emails
add(113,"11. DevOps", "SES", "4M emails/mo", 4000, "K-emails", DEV["ses_per_1000"], 4000*DEV["ses_per_1000"])
# Row 114: CI/CD 60 Y1 pipelines
cp_cost = 60 * 10 * 60 * DEV["codepipeline_v2_per_action_minute"]  # 60 pipelines × 10 actions × 60 min
cb_cost = 60 * 120 * DEV["codebuild_small_per_minute"]
add(114,"11. DevOps", "CodePipeline + CodeBuild", "60 pipelines, CI/CD", 60, "pipeline", round((cp_cost+cb_cost)/60,4), cp_cost+cb_cost)
# Row 115: Step Functions + MWAA. 7 Y1 workflows × 30000 transitions
sf_cost = 7 * 30000 / 1000 * DEV["step_functions_per_1000_transitions"]
mwaa_cost = 1 * 730 * DEV["mwaa_mw1_small_per_hour"]
add(115,"11. DevOps", "Step Functions + MWAA", "7 workflows + 1 MWAA env", 7*30000, "transition", 0.000025, sf_cost+mwaa_cost)
# Row 116 (dup 2): Amazon Q Developer 150 Y1 users × $19
add(116.1,"11. DevOps", "Amazon Q Developer", "900 developer licenses (150 Y1)", 900, "user-month", DEV["q_developer_per_user"], 900*DEV["q_developer_per_user"])
# Row 117: Cognito 1.8M MAU Y1 → capped at 500K per review comment
cog_mau = min(1_800_000, 500_000)
add(117,"11. DevOps", "Amazon Cognito", "500K MAU (capped per reviewer)", cog_mau, "MAU", DEV["cognito_mau_tier"], cog_mau * DEV["cognito_mau_tier"], "Capped at 500K MAU per reviewer note")
# Row 119: Amazon Q Apps 50 Y1 users × $20
add(119,"11. DevOps", "Amazon Q Apps + Marketplace Low-Code", "50 developer users Y1", 50, "user-month", DEV["q_apps_per_user"], 50*DEV["q_apps_per_user"])
# Row 120: Amplify Hosting + Cognito for external portal, 15000 Y1 × 100 users = 1.5M MAU
add(120,"11. DevOps", "Amplify Hosting + Cognito (External Portal)", "1.5M authenticated external users", 1_500_000, "MAU", DEV["cognito_mau_tier"], 1_500_000*DEV["cognito_mau_tier"], "Consumption-based auth pricing")
# Row 121: Business Process (Q Apps or Amplify) - treat as Q Apps 30 users × $20
add(121,"11. DevOps", "Business Process Automation", "30 low-code users Y1", 30, "user-month", DEV["q_apps_per_user"], 30*DEV["q_apps_per_user"])
# Row 122: AWS Enterprise Support - 3% of AWS spend or min $15K/mo
# Compute total so far, then add 3%
# We'll compute and attach later
add(122,"11. DevOps", "AWS Enterprise Support", "3% of AWS monthly spend or $15k min", 1, "support-month", 0, 0, "Computed as 3% of total AWS spend below")
# Rows 123-125: Pro Services / Training / Future capacity - quote-based
add(123,"11. DevOps", "AWS Professional Services", "50 mandays Y1", 0, "quote", 0, 0, "Quote-based, not in calculator")
add(124,"11. DevOps", "AWS Training", "20 mandays Y1", 0, "quote", 0, 0, "Quote-based")
add(125,"11. DevOps", "Future Workload Capacity", "Placeholder", 0, "reserve", 0, 0, "Reserve, not priced")

# ==== 12. CSP MARKETPLACE ISV =================================================
for idx, isv in [(126,"Databricks Unity Platform"),(127,"Denodo Data Virtualization"),(128,"Snowflake Data Cloud"),(129,"Marketing Automation (Braze/CleverTap/MoEngage)")]:
    add(idx, "12. Marketplace ISV", isv, "Quote-based via AWS Marketplace", 0, "quote", 0, 0, "Priced separately by ISV, procurable via AWS Marketplace for EDP burn-down")

# -----------------------------------------------------------------------------
# Enterprise Support computation (3% of subtotal)
# -----------------------------------------------------------------------------
subtotal = sum(i["monthly_cost_usd"] for i in items if i["id"] != 122)
ent_support = max(15000.0, round(subtotal * 0.03, 2))
for i in items:
    if i["id"] == 122:
        i["monthly_cost_usd"] = ent_support
        i["annual_cost_usd"] = round(ent_support * 12, 2)
        i["unit_price_usd"] = ent_support
        i["notes"] = f"3% of ${subtotal:,.2f} monthly AWS spend, floor $15K/mo"

# -----------------------------------------------------------------------------
# Write outputs
# -----------------------------------------------------------------------------
grand_total = sum(i["monthly_cost_usd"] for i in items)
grand_annual = sum(i["annual_cost_usd"] for i in items)

# Write CSV
csv_path = Path("aws-cost-estimate-hpcl-boq-2026-04-26.csv")
with csv_path.open("w", newline="") as f:
    w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    w.writerow([f"# AWS Cost Estimate for HPCL BoQ | Region: ap-south-1 (Mumbai) | Baseline: Y1 (30% ramp) | Currency: USD | Date: 2026-04-26"])
    w.writerow([])
    w.writerow(["#", "Category", "Service", "Configuration", "Qty Y1", "Unit", "Unit Price (USD)", "Monthly Cost (USD)", "Annual Cost Y1 (USD)", "Notes"])

    # Line items
    current_cat = None
    cat_sub = 0.0
    cat_sub_annual = 0.0
    for i in items:
        if current_cat and i["category"] != current_cat:
            w.writerow(["", current_cat, "SUBTOTAL", "", "", "", "", f"{cat_sub:.2f}", f"{cat_sub_annual:.2f}", ""])
            w.writerow([])
            cat_sub = 0.0
            cat_sub_annual = 0.0
        current_cat = i["category"]
        w.writerow([i["id"], i["category"], i["service"], i["config"], i["qty_y1"], i["unit"], f"{i['unit_price_usd']:.4f}", f"{i['monthly_cost_usd']:.2f}", f"{i['annual_cost_usd']:.2f}", i["notes"]])
        cat_sub += i["monthly_cost_usd"]
        cat_sub_annual += i["annual_cost_usd"]
    # Last subtotal
    w.writerow(["", current_cat, "SUBTOTAL", "", "", "", "", f"{cat_sub:.2f}", f"{cat_sub_annual:.2f}", ""])
    w.writerow([])
    w.writerow(["", "TOTAL", "ALL SERVICES", "", "", "", "", f"{grand_total:.2f}", f"{grand_annual:.2f}", ""])

# Write summary per category
cat_summary = {}
for i in items:
    cat_summary.setdefault(i["category"], {"mo":0, "yr":0})
    cat_summary[i["category"]]["mo"] += i["monthly_cost_usd"]
    cat_summary[i["category"]]["yr"] += i["annual_cost_usd"]

print(f"\n{'='*70}")
print(f"HPCL BoQ — AWS Cost Estimate (Y1 @ 30% ramp) | ap-south-1 | USD")
print(f"{'='*70}\n")
print(f"{'Category':<35} {'Monthly':>14} {'Annual (Y1)':>18}")
print("-" * 70)
for cat, vals in cat_summary.items():
    print(f"{cat:<35} ${vals['mo']:>12,.2f} ${vals['yr']:>16,.2f}")
print("-" * 70)
print(f"{'GRAND TOTAL':<35} ${grand_total:>12,.2f} ${grand_annual:>16,.2f}")
print(f"\nLine items written: {len(items)}")
print(f"CSV: {csv_path.resolve()}")
