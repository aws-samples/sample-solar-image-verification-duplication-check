#!/usr/bin/env python3
"""NMDC BoQ cost compute — DC (ap-south-1) + DR (ap-south-2), AWS-native mapping.

Produces:
  1. nmdc-rate-card-filled-2026-04-28.csv   — rate card with AWS unit prices
  2. nmdc-dc-boq-priced-2026-04-28.csv       — DC VMs + services, unit/monthly/annual
  3. nmdc-dr-boq-priced-2026-04-28.csv       — DR VMs + services, unit/monthly/annual
  4. nmdc-summary-2026-04-28.csv             — combined monthly/annual summary
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
P = json.loads((HERE / "nmdc_prices.json").read_text())
OD = P["ec2_ondemand_hourly"]
HRS = 730

def pick_instance(vcpu: int, ram: int, os_type: str = "linux"):
    """Map BoQ vCPU/RAM/OS to nearest m6i/r6i SKU."""
    ratio = ram / vcpu if vcpu > 0 else 0
    # m6i is 1:4 ratio (vCPU:RAM), r6i is 1:8
    family = "r6i" if ratio > 5 else "m6i"
    # size by vCPU (m6i sizes: xlarge=4, 2xlarge=8, 4xlarge=16, 8xlarge=32, 16xlarge=64)
    if vcpu <= 4:
        size = "xlarge" if family == "m6i" else "2xlarge"
    elif vcpu <= 8:
        size = "2xlarge"
    elif vcpu <= 16:
        size = "4xlarge"
    elif vcpu <= 32:
        size = "8xlarge"
    else:
        size = "16xlarge"
    # bump size if RAM exceeds instance RAM
    ram_map = {
        ("m6i","xlarge"):16,("m6i","2xlarge"):32,("m6i","4xlarge"):64,
        ("m6i","8xlarge"):128,("m6i","16xlarge"):256,
        ("r6i","2xlarge"):64,("r6i","4xlarge"):128,("r6i","8xlarge"):256,
        ("r6i","16xlarge"):512,
    }
    while (family, size) in ram_map and ram_map[(family,size)] < ram:
        order = ["xlarge","2xlarge","4xlarge","8xlarge","16xlarge"]
        i = order.index(size)
        if i < len(order)-1: size = order[i+1]
        else:
            family = "r6i"
            size = "16xlarge"
            break
    instance = f"{family}.{size}"
    key = f"{instance}_{os_type}"
    price = OD.get(key, OD.get(f"{instance}_linux", 0))
    return instance, price

# ----- DC VM inventory (44 VMs) -----
DC_VMS = [
    (1,  "QMS-1",   20, 20,  64,   500),
    (2,  "QMS-2",   20, 20,  64,   500),
    (3,  "QMS-3",   20, 20,  128, 1524),
    (4,  "QMS-4",   20, 20,  64,  5096),
    (5,  "QMS-5",   20, 20,  52,  2113),
    (6,  "QMS-6",   20, 20,  64,   500),
    (7,  "QMS-7",   20, 20,  64,  2048),
    (8,  "QMS-8",   20, 20,  64,   500),
    (9,  "QMS-9",   20, 20,  128, 2560),
    (10, "QMS-10",  20, 20,  64,  5120),
    (11, "ESG-1",   16, 16,  32,   500),
    (12, "ESG-2",   16, 16,  64,  1024),
    (13, "ESG-3",   16, 16,  128, 2048),
    (14, "ESG-4",    8,  8,  16,   500),
    (15, "NMDCHOVDNET01", 8,  8, 16, 200),
    (16, "NMDCHOVDNET02", 8,  8, 16, 200),
    (17, "NMDCHOVDNET03", 8,  8, 16, 200),
    (18, "NMDCHOVDNET04", 8,  8, 16, 200),
    (19, "NMDCHOVDNET05", 8,  8, 16, 200),
    (20, "NMDCHOVDNET06", 8,  8, 16, 200),
    (21, "NMDCHOVDNET07", 8,  8, 16, 200),
    (22, "NMDCHOVDNET08", 8,  8, 16, 200),
    (23, "NMDCHOVDNET09", 8,  8, 16, 200),
    (24, "NMDCHOVPRIMAVERA",       8,  8, 16, 200),
    (25, "NMDCHOVPRIMAVERA-TEST",  8,  8, 16, 200),
    (26, "NMDCHOVAD203",           8,  8, 16, 200),
    (27, "NMDCHOVAFRS",            8,  8, 16, 350),
    (28, "NMDCHOVAVITA",           8,  8, 16, 200),
    (29, "NMDCHOVCFEMS",           8,  8, 16, 200),
    (30, "NMDCHOVASSISTMGMT",      8,  8, 32, 200),
    (31, "NMDCHOVFTS",             8,  8, 16, 200),
    (32, "NMDCHOPB06",            24, 24, 128, 2000),
    (33, "NMDCHOPB07",            24, 24, 128, 2000),
    (34, "NMDCHOAPP1",             8,  8, 16, 300),
    (35, "NMDCHOAPP2",             8,  8, 16, 300),
    (36, "NMDCHOAPP3",             8,  8, 16, 300),
    (37, "NMDCHOFLM1",            16, 16, 84, 1000),
    (38, "NMDCHOFLM2",            16, 16, 84, 1000),
    (39, "HMS-1",                 14, 14, 64,  500),
    (40, "HMS-2",                 14, 14, 64,  500),
    (41, "DPMU-1",                 8,  8, 32, 1350),
    (42, "DPMU-2",                16, 16, 64, 1350),
    (43, "DPMU-3",                 8,  8, 32, 1350),
    (44, "DPMU-4",                16, 16, 64, 1350),
]
# (id, name, dur_months, vcpu, ram, storage_gb). We'll use Linux as default OS for VMs.

DR_VMS = [
    (1,  "QMS-11",                 20, 20,  64,   500),
    (2,  "QMS-12",                 20, 20,  64,  2048),
    (3,  "QMS-13",                 20, 20,  64,   500),
    (4,  "QMS-9",                  20, 20,  128, 2560),
    (5,  "QMS-10",                 20, 20,  64,  5120),
    (6,  "ESG-3",                  16, 16,  128, 2048),
    (7,  "ESG-4",                   8,  8,  16,   500),
    (8,  "NMDCHOVPRIMAVERA",        8,  8,  16,   200),
    (9,  "NMDCHOVPRIMAVERA-TEST",   8,  8,  16,   200),
    (10, "NMDCHOVAD203",            8,  8,  16,   200),
    (11, "NMDCHOVAFRS",             8,  8,  16,   350),
    (12, "NMDCHOVAVITA",            8,  8,  16,   200),
    (13, "NMDCHOVCFEMS",            8,  8,  16,   200),
    (14, "NMDCHOVASSISTMGMT",       8,  8,  32,   200),
    (15, "NMDCHOVFTS",              8,  8,  16,   200),
    (16, "NMDCHOPB06",             24, 24,  128, 2000),
    (17, "NMDCHOPB07",             24, 24,  128, 2000),
    (18, "NMDCHOAPP1",              8,  8,  16,   300),
]

GP3 = P["ebs_gp3_per_gb_month"]
BKP = P["backup_per_gb_month"]
EIP_H = P["elastic_ip_unattached_hourly"]

def vm_rows(vms, label):
    rows = []
    for (sn, name, dur, v, r, s) in vms:
        inst, hr_price = pick_instance(v, r, "linux")
        compute_mo = hr_price * HRS
        storage_mo = s * GP3
        total_mo = compute_mo + storage_mo
        rows.append({
            "category": f"{label}: Compute+Storage",
            "sno": sn,
            "item": name,
            "config": f"{v} vCPU / {r} GB RAM / {s} GB / Linux",
            "aws_mapping": f"EC2 {inst} (Linux) + EBS gp3 {s} GB",
            "qty": 1,
            "unit": "per VM / month",
            "unit_price_usd": round(total_mo, 2),
            "monthly_usd": round(total_mo, 2),
            "annual_usd": round(total_mo * 12, 2),
            "duration_months": dur,
            "contract_total_usd": round(total_mo * dur, 2),
        })
    return rows

def services_dc():
    # Backup Services
    backup_vms = 44
    backup_gb = 66112.5
    backup_vm_cost = 0.0  # AWS Backup priced by GB, per-VM tracking included
    backup_storage_cost = backup_gb * BKP
    # Public IPs
    eips = 14
    eip_cost = eips * EIP_H * HRS
    # Connectivity: Direct Connect 1Gbps x 2 redundant for P2P (500 Mbps HO), and S2S VPN for internet+SAP
    dx_1g = 2 * P["_managed_services_ap_south_1"]["direct_connect_1gbps_per_hour"] * HRS
    vpn_internet = 2 * P["_managed_services_ap_south_1"]["site_to_site_vpn_per_hour"] * HRS
    # Security — AWS-native mapping
    waf_cost = (P["_managed_services_ap_south_1"]["waf_acl_per_month"] +
                10 * P["_managed_services_ap_south_1"]["waf_rule_per_month"] +
                50 * P["_managed_services_ap_south_1"]["waf_per_million_requests"])
    nfw_cost = (2 * P["_managed_services_ap_south_1"]["network_firewall_endpoint_per_hour"] * HRS +
                1024 * P["_managed_services_ap_south_1"]["network_firewall_per_gb_processed"])
    # Managed services — AWS-native
    ssm_cost = 0.0  # Systems Manager patch free
    inspector_cost = 44 * P["_managed_services_ap_south_1"]["inspector_per_resource_month"]
    cw_logs_cost = 100 * P["_managed_services_ap_south_1"]["cloudwatch_logs_per_gb"]  # 100 GB logs/mo
    guardduty_cost = (30 * P["_managed_services_ap_south_1"]["guardduty_cloudtrail_events_per_million"] +
                      100 * P["_managed_services_ap_south_1"]["guardduty_vpc_flow_per_gb"])
    sec_hub_cost = P["_managed_services_ap_south_1"]["securityhub_per_account_month"]
    # Software licenses — SUSE already counted if any VMs SUSE; Oracle 19C = BYOL
    # RHEL Large add-on (2 VMs): ~$0.06/hr × 730 × 2 = $87.60/mo
    rhel_cost = 2 * 0.06 * HRS
    # MS SQL Std (if used): Not in BoQ — skip
    # Software "Server OS Lics" (CentOS/Ubuntu/Oracle Linux Community) = FREE
    # Antivirus (Bitdefender) / PAM / MFA — Marketplace ISVs, quote-based
    items = [
        ("DC: Backup",     "Veeam Backup VMs (Veeam license)",          44,     "Per VM",  "QUOTE (Veeam ISV via Marketplace)", "QUOTE", "QUOTE", None),
        ("DC: Backup",     "AWS Backup warm storage",                   backup_gb, "GB-month", BKP, backup_storage_cost, backup_storage_cost*12, f"AWS Backup, {backup_gb:.0f} GB × ${BKP}/GB"),
        ("DC: Network",    "Elastic IP v4 (unattached rate)",           eips,   "IP",      EIP_H*HRS, eip_cost, eip_cost*12, f"{eips} EIPs × $0.005/hr × 730hr"),
        ("DC: Connectivity","Direct Connect 1 Gbps port (P2P HO)",      2,      "Port",    P["_managed_services_ap_south_1"]["direct_connect_1gbps_per_hour"]*HRS, dx_1g, dx_1g*12, "2 ports, redundant, 500Mbps VIF carved"),
        ("DC: Connectivity","Site-to-Site VPN (Internet+SAP)",          2,      "VPN",     P["_managed_services_ap_south_1"]["site_to_site_vpn_per_hour"]*HRS, vpn_internet, vpn_internet*12, "2 VPN tunnels × $0.05/hr × 730hr"),
        ("DC: Software",   "SUSE Linux 5+ vCore markup (5 VMs)",        5,      "Per VM",  "see VM row", "included", "included", "SUSE license included in EC2 SUSE pricing"),
        ("DC: Software",   "RHEL Large vCore >4 markup",                2,      "Per VM",  43.8,   rhel_cost, rhel_cost*12, "~$0.06/hr × 730hr × 2 VMs"),
        ("DC: Software",   "Oracle 19C DB Licenses (BYOL)",             3,      "Per VM",  "BYOL", "BYOL", "BYOL", "Oracle 19C = BYOL, NMDC retains license"),
        ("DC: Software",   "Bitdefender Antivirus (Marketplace ISV)",   44,     "Per VM",  "QUOTE", "QUOTE", "QUOTE", "Marketplace ISV — quote-based"),
        ("DC: Managed",    "Systems Manager (Patch/OS Mgmt)",           44,     "Per VM",  0.0,    0.0,    0.0,   "SSM is free"),
        ("DC: Managed",    "Amazon Inspector (vuln scan)",              44,     "Resource", P["_managed_services_ap_south_1"]["inspector_per_resource_month"], inspector_cost, inspector_cost*12, "44 VMs × $1.45/mo"),
        ("DC: Managed",    "CloudWatch Logs + Metrics (Infra Monitor)", 100,    "GB logs", P["_managed_services_ap_south_1"]["cloudwatch_logs_per_gb"], cw_logs_cost, cw_logs_cost*12, "100 GB/mo ingested"),
        ("DC: Security",   "GuardDuty (SOC equivalent)",                1,      "Account", guardduty_cost, guardduty_cost, guardduty_cost*12, "CloudTrail 30M events + 100 GB VPC flow"),
        ("DC: Security",   "Security Hub",                              1,      "Account", sec_hub_cost, sec_hub_cost, sec_hub_cost*12, "Aggregated findings/compliance"),
        ("DC: Security",   "AWS WAF (Web ACL + 10 rules + 50M req)",    1,      "Instance", waf_cost, waf_cost, waf_cost*12, "1 ACL × 10 rules × 50M req"),
        ("DC: Security",   "AWS Network Firewall (2 endpoints + 1TB)",  1,      "Instance", nfw_cost, nfw_cost, nfw_cost*12, "2 endpoints × 730hr + 1TB processed"),
        ("DC: Security",   "PAM/PIM/MFA host security (Marketplace)",   1,      "Platform", "QUOTE", "QUOTE", "QUOTE", "CyberArk/BeyondTrust via Marketplace"),
        ("DC: Security",   "MFA base (Cognito)",                        100,    "MAU",     0.0055, 0.55, 6.6, "100 admin users × $0.0055/MAU"),
        ("DC: VAPT",       "Inspector on-demand scan (5 batches of 10)", 1,     "Service", "included", "included", "included", "Covered by Inspector line above"),
        ("DC: MSP",        "Onsite Project Manager (MSP scope)",        1,      "Person",  "QUOTE", "QUOTE", "QUOTE", "MSP scope, not AWS"),
        ("DC: One-Time",   "Commissioning & Deployment (MSP scope)",    1,      "Service", "QUOTE", "QUOTE", "QUOTE", "MSP scope, not AWS"),
    ]
    rows = []
    for (cat, item, qty, unit, up, mo, yr, note) in items:
        rows.append({
            "category": cat, "sno": "", "item": item, "config": "",
            "aws_mapping": "",
            "qty": qty, "unit": unit,
            "unit_price_usd": up,
            "monthly_usd": mo,
            "annual_usd": yr,
            "duration_months": "",
            "contract_total_usd": "",
            "notes": note or "",
        })
    return rows

def services_dr():
    # Cross-region replication egress: assume 10% of DC storage changes/mo × $0.086/GB
    dc_storage_total = sum(s for (_,_,_,_,_,s) in DC_VMS)
    xregion_egress_gb = dc_storage_total * 0.10  # 10% change rate
    xregion_cost = xregion_egress_gb * P["interregion_transfer_per_gb"]
    # DR has no backup license/storage — BoQ shows blank. Skipped.
    # Software: SUSE 3 VMs (included), Oracle 19C BYOL (1 VM), Antivirus 0
    # Managed services on DR = 0 per BoQ (cold DR)
    # Network services on DR = Firewall 1 + WAF 1, VAPT 2 batches
    waf_cost_dr = (P["_managed_services_ap_south_1"]["waf_acl_per_month"] +
                   10 * P["_managed_services_ap_south_1"]["waf_rule_per_month"] +
                   25 * P["_managed_services_ap_south_1"]["waf_per_million_requests"])
    nfw_cost_dr = (2 * P["_managed_services_ap_south_1"]["network_firewall_endpoint_per_hour"] * HRS +
                   512 * P["_managed_services_ap_south_1"]["network_firewall_per_gb_processed"])
    dx_dr = 2 * P["_managed_services_ap_south_1"]["direct_connect_1gbps_per_hour"] * HRS  # P2P 300Mbps HO + 100Mbps SAP
    vpn_dr = 2 * P["_managed_services_ap_south_1"]["site_to_site_vpn_per_hour"] * HRS
    inspector_dr = 18 * P["_managed_services_ap_south_1"]["inspector_per_resource_month"]
    items = [
        ("DR: Replication", "Cross-region data transfer (10% change/mo)", xregion_egress_gb, "GB",   P["interregion_transfer_per_gb"], xregion_cost, xregion_cost*12, f"{xregion_egress_gb:.0f} GB × $0.086/GB (ap-south-1 → ap-south-2)"),
        ("DR: Network",     "Elastic IP v4",                              0,      "IP", 0.0, 0.0, 0.0, "BoQ qty = 0"),
        ("DR: Software",    "SUSE 5+ vCore (3 VMs)",                      3,      "Per VM", "included", "included", "included", "SUSE license in EC2 SUSE rate"),
        ("DR: Software",    "Oracle 19C DB BYOL",                         1,      "Per VM", "BYOL", "BYOL", "BYOL", "NMDC retains license"),
        ("DR: Managed",     "OS/Infra Monitoring (BoQ qty=0 — cold DR)",  0,      "Per VM", 0.0, 0.0, 0.0, "No active monitoring on cold DR"),
        ("DR: Managed",     "Network Managed Services",                   1,      "Nos",    "QUOTE", "QUOTE", "QUOTE", "MSP scope"),
        ("DR: VAPT",        "Inspector scans (2 batches of 10)",          18,     "Resource", P["_managed_services_ap_south_1"]["inspector_per_resource_month"], inspector_dr, inspector_dr*12, "18 DR VMs × $1.45/mo"),
        ("DR: Security",    "Dedicated Firewall (AWS Network Firewall)",  1,      "Instance", nfw_cost_dr, nfw_cost_dr, nfw_cost_dr*12, "2 endpoints × 730hr + 512 GB"),
        ("DR: Security",    "WAF & Managed Services",                     1,      "Instance", waf_cost_dr, waf_cost_dr, waf_cost_dr*12, "1 ACL × 10 rules × 25M req"),
        ("DR: Connectivity","Direct Connect 1 Gbps (P2P HO/SAP)",         2,      "Port", P["_managed_services_ap_south_1"]["direct_connect_1gbps_per_hour"]*HRS, dx_dr, dx_dr*12, "Redundant DX to HO/SAP"),
        ("DR: Connectivity","Site-to-Site VPN (Internet 50 Mbps)",        2,      "VPN", P["_managed_services_ap_south_1"]["site_to_site_vpn_per_hour"]*HRS, vpn_dr, vpn_dr*12, "2 VPN tunnels"),
        ("DR: One-Time",    "Commissioning & Deployment (MSP)",           1,      "Service", "QUOTE", "QUOTE", "QUOTE", "MSP scope"),
    ]
    rows = []
    for (cat, item, qty, unit, up, mo, yr, note) in items:
        rows.append({
            "category": cat, "sno": "", "item": item, "config": "",
            "aws_mapping": "",
            "qty": qty, "unit": unit,
            "unit_price_usd": up,
            "monthly_usd": mo,
            "annual_usd": yr,
            "duration_months": "",
            "contract_total_usd": "",
            "notes": note,
        })
    return rows

def write_priced_boq(rows, path, title):
    with Path(path).open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([title])
        w.writerow(["Region", "DC=ap-south-1 (Mumbai Multi-AZ)  |  DR=ap-south-2 (Hyderabad)"])
        w.writerow(["Pricing Date", "2026-04-28"])
        w.writerow(["Currency", "USD"])
        w.writerow([])
        w.writerow(["Category","SNO","Item / VM Name","Config","AWS Mapping","Qty","Unit","Unit Price (USD)","Monthly (USD)","Annual (USD)","Duration (mo)","Contract Total (USD)","Notes"])
        total_mo = 0.0
        total_yr = 0.0
        for r in rows:
            w.writerow([r.get("category",""), r.get("sno",""), r.get("item",""), r.get("config",""), r.get("aws_mapping",""), r.get("qty",""), r.get("unit",""),
                        r.get("unit_price_usd",""), r.get("monthly_usd",""), r.get("annual_usd",""), r.get("duration_months",""), r.get("contract_total_usd",""), r.get("notes","")])
            try:
                total_mo += float(r.get("monthly_usd",0) or 0)
                total_yr += float(r.get("annual_usd",0) or 0)
            except (ValueError, TypeError):
                pass
        w.writerow([])
        w.writerow(["","","","","","","TOTAL (priced items only; QUOTE/BYOL excluded)","", f"{total_mo:.2f}", f"{total_yr:.2f}", "", "", ""])
    return total_mo, total_yr

# ----- Rate card filled -----
def write_rate_card():
    # Rate card values — per-vCPU/per-GB/per-VM derived from AWS
    # Use m6i.2xlarge as reference: 8vCPU/32GB/Linux=$0.404/hr → $294.92/mo → $36.87/vCPU/mo
    m6i_lin_hr = OD["m6i.2xlarge_linux"]
    m6i_win_hr = OD["m6i.2xlarge_windows"]
    m6i_suse_hr = OD["m6i.2xlarge_suse"]
    m6i_rhel_hr = OD["m6i.2xlarge_rhel"]
    per_vcpu_linux = (m6i_lin_hr * HRS) / 8  # split even across vCPU only; RAM free-ish on m-series
    per_vcpu_windows = (m6i_win_hr * HRS) / 8
    # Take 70% of compute price as vCPU contribution, 30% as RAM contribution
    lin_compute_mo = m6i_lin_hr * HRS
    per_vcpu_lin = (lin_compute_mo * 0.70) / 8
    per_gb_ram_lin = (lin_compute_mo * 0.30) / 32
    win_compute_mo = m6i_win_hr * HRS
    per_vcpu_win = (win_compute_mo * 0.70) / 8
    # SUSE per 5+ core
    suse_markup_hr = OD["m6i.4xlarge_suse"] - OD["m6i.4xlarge_linux"]  # SUSE licence delta
    suse_per_5core_mo = suse_markup_hr * HRS
    # RHEL per VM: markup ~$0.06/hr
    rhel_per_vm_mo = 0.06 * HRS
    # GPU L4 24GB — g6.xlarge linux = $0.9664/hr; base linux compute = m6i.xlarge 0.202 → GPU-only portion ≈ 0.76/hr
    gpu_l4_hr = OD["g6.xlarge_linux"] - OD["m6i.xlarge_linux"]  # approx GPU-only
    per_gpu_mo = gpu_l4_hr * HRS
    # Storage
    storage_per_gb_mo = GP3
    # Backup
    backup_per_vm_mo = 0.0   # no Veeam license on AWS native; use AWS Backup by GB
    backup_per_gb_mo = BKP
    # OS Linux = free; OS SUSE = compute markup; RHEL = markup; Oracle Linux = BYOL/free
    # DB
    mysql_per_vm_mo = 0.0  # self-managed on EC2 via community — free
    oracle_std_per_vm = "BYOL"
    mssql_std_per_2core = P["db_licensing_approx_monthly"]["mssql_std_per_2_core_hour_approx"] * HRS
    mongodb_per_vm_mo = 0.0  # Community Edition free
    # Managed services — AWS-native per VM approximations
    antivirus_per_vm = "QUOTE"  # Marketplace ISV
    ips_per_ip = P["_managed_services_ap_south_1"]["network_firewall_endpoint_per_hour"] * HRS / 30  # amortized
    vapt_per_10vms_mo = 10 * P["_managed_services_ap_south_1"]["inspector_per_resource_month"]
    os_mgmt_per_vm = 0.0  # SSM free
    db_mgmt_per_vm = "QUOTE"  # MSP scope
    backup_mgmt_per_vm = 0.0  # AWS Backup orchestration included
    infra_mon_per_vm = P["_managed_services_ap_south_1"]["cloudwatch_per_metric_month"] * 10  # 10 metrics/VM
    soc_per_vm = P["_managed_services_ap_south_1"]["guardduty_vpc_flow_per_gb"] * 2  # ~2GB/VM/mo
    # Build rows per NMDC rate-card format
    items = [
        ("vCPU - for Windows",                     "Per vCPU",       round(per_vcpu_win, 2),        "EC2 m6i.2xlarge Windows derived; incl Windows license"),
        ("vCPU - for Linux",                       "Per vCPU",       round(per_vcpu_lin, 2),        "EC2 m6i.2xlarge Linux; OS free"),
        ("GPU (NVIDIA L4 24GB)",                   "Per GPU",        round(per_gpu_mo, 2),          "EC2 g6.xlarge (L4 24GB); GPU-only delta from base"),
        ("RAM",                                    "Per GB",         round(per_gb_ram_lin, 2),      "Derived from m6i.2xlarge: 30% of compute / 32 GB"),
        ("Storage",                                "Per GB",         round(storage_per_gb_mo, 4),   "EBS gp3, ap-south-1, 3000 IOPS/125 MBps included"),
        ("Backup License",                         "Per VM",         backup_per_vm_mo,              "AWS Backup: no per-VM license; priced per GB"),
        ("Backup Storage",                         "Per GB",         round(backup_per_gb_mo, 4),    "AWS Backup warm tier"),
        ("OS Linux",                               "Per VM",         0.0,                           "Amazon Linux / Ubuntu / CentOS = FREE on EC2"),
        ("OS SUSE",                                "Per 5+ Cores",   round(suse_per_5core_mo, 2),   "SUSE license markup via EC2 SUSE rate"),
        ("PostgreSQL / MySQL",                     "Per VM",         mysql_per_vm_mo,               "Self-managed community edition on EC2 = FREE"),
        ("RHEL Licenses",                          "Per VM",         round(rhel_per_vm_mo, 2),      "RHEL markup ~$0.06/hr × 730hr on EC2"),
        ("Oracle Enterprise Linux OS",             "Per VM",         "BYOL",                        "Oracle Enterprise Linux — BYOL; no AWS list price"),
        ("Oracle 19C Standard up to 16 Core",      "Per VM",         "BYOL",                        "Oracle 19C — BYOL via Oracle license contract"),
        ("MS SQL (per 2 core, Standard)",          "Per 2 Core",     round(mssql_std_per_2core, 2), "SQL Server Std license-included on EC2"),
        ("MongoDB",                                "Per VM",         mongodb_per_vm_mo,             "MongoDB Community Edition = FREE; Atlas via Marketplace for Enterprise"),
        ("Antivirus",                              "Per VM",         antivirus_per_vm,              "Bitdefender/CrowdStrike via AWS Marketplace (ISV)"),
        ("IPS",                                    "No (per endpoint)", round(P["_managed_services_ap_south_1"]["network_firewall_endpoint_per_hour"]*HRS, 2), "AWS Network Firewall endpoint ~$288.35/mo"),
        ("VAPT for 10 IPs",                        "Per 10 VMs",     round(vapt_per_10vms_mo, 2),   "Amazon Inspector: 10 resources × $1.45"),
        ("OS Mgmt",                                "Per VM",         os_mgmt_per_vm,                "AWS Systems Manager patch/config = FREE"),
        ("DB Mgmt",                                "Per VM",         db_mgmt_per_vm,                "RDS Performance Insights free; self-managed DB = MSP scope"),
        ("Backup Mgmt",                            "Per VM",         backup_mgmt_per_vm,            "AWS Backup orchestration = FREE"),
        ("Infra Monitoring",                       "Per VM",         round(infra_mon_per_vm, 2),    "CloudWatch: ~10 custom metrics × $0.30"),
        ("SOC as a Service",                       "Per VM",         round(soc_per_vm, 2),          "GuardDuty + Security Hub for VPC flow analysis"),
    ]
    path = Path("nmdc-rate-card-filled-2026-04-28.csv")
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["NMDC AWS-Native Rate Card (unit prices in USD)"])
        w.writerow(["Region", "ap-south-1 (Mumbai)"])
        w.writerow(["Pricing Date", "2026-04-28"])
        w.writerow(["Notes", "Use these unit prices × BoQ quantity to derive monthly cost. Bidder applies margin/markup on these."])
        w.writerow([])
        w.writerow(["Service Description", "UOM", "Unit Price (MRC, USD)", "Remarks"])
        for (svc, uom, up, rem) in items:
            w.writerow([svc, uom, up, rem])
    return path, items

# ----- Main -----
if __name__ == "__main__":
    dc_vm_rows = vm_rows(DC_VMS, "DC")
    dc_svc_rows = services_dc()
    dc_all = dc_vm_rows + dc_svc_rows
    dc_mo, dc_yr = write_priced_boq(dc_all, "nmdc-dc-boq-priced-2026-04-28.csv", "NMDC — DC BoQ (Priced, AWS ap-south-1)")

    dr_vm_rows = vm_rows(DR_VMS, "DR")
    dr_svc_rows = services_dr()
    dr_all = dr_vm_rows + dr_svc_rows
    dr_mo, dr_yr = write_priced_boq(dr_all, "nmdc-dr-boq-priced-2026-04-28.csv", "NMDC — DR BoQ (Priced, AWS ap-south-2)")

    rc_path, rc_items = write_rate_card()

    # Summary
    summ = Path("nmdc-summary-2026-04-28.csv")
    with summ.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["NMDC AWS Cost Summary — DC + DR"])
        w.writerow(["Region", "DC=ap-south-1 (Mumbai Multi-AZ)  |  DR=ap-south-2 (Hyderabad)"])
        w.writerow(["Pricing Date", "2026-04-28"])
        w.writerow([])
        w.writerow(["Segment", "Monthly (USD)", "Annual (USD)"])
        w.writerow(["DC Total (ap-south-1)",  f"{dc_mo:.2f}", f"{dc_yr:.2f}"])
        w.writerow(["DR Total (ap-south-2)",  f"{dr_mo:.2f}", f"{dr_yr:.2f}"])
        w.writerow(["GRAND TOTAL",            f"{dc_mo+dr_mo:.2f}", f"{dc_yr+dr_yr:.2f}"])
        w.writerow([])
        w.writerow(["Excluded (quote-based)"])
        w.writerow(["- Veeam backup license, Bitdefender AV, PAM/PIM platforms (Marketplace ISVs)"])
        w.writerow(["- Oracle 19C / Oracle Enterprise Linux (BYOL by NMDC)"])
        w.writerow(["- Onsite PM, Commissioning & Deployment (MSP scope)"])
        w.writerow(["- DB Mgmt, Network Managed Services (MSP scope)"])

    print(f"\n{'='*70}")
    print(f"NMDC AWS Cost Estimate  |  DC ap-south-1  |  DR ap-south-2  |  USD")
    print(f"{'='*70}")
    print(f"DC Monthly:  ${dc_mo:>12,.2f}     DC Annual: ${dc_yr:>14,.2f}")
    print(f"DR Monthly:  ${dr_mo:>12,.2f}     DR Annual: ${dr_yr:>14,.2f}")
    print(f"GRAND TOTAL: ${dc_mo+dr_mo:>12,.2f}     Annual:   ${dc_yr+dr_yr:>14,.2f}")
    print(f"\nFiles written:")
    print(f"  {rc_path}")
    print(f"  nmdc-dc-boq-priced-2026-04-28.csv")
    print(f"  nmdc-dr-boq-priced-2026-04-28.csv")
    print(f"  nmdc-summary-2026-04-28.csv")
