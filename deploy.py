#!/usr/bin/env python3
"""End-to-end deploy for the MNRE Solar Panel Verification Portal.

Wraps the AWS CDK app so the whole stack (VPC, RDS PostgreSQL + pgvector,
Lambdas, Step Functions, API Gateway, S3, Amplify frontend hosting) deploys
with one command.

Flow:
  1. npm install in cdk/ and frontend/
  2. cdk bootstrap (idempotent)
  3. cdk deploy  -> capture ApiUrl + AmplifyAppId outputs
  4. write frontend/.env with VITE_API_URL, build the frontend
  5. zip frontend/dist and publish it to Amplify (start-deployment)

Usage:
    python3 deploy.py                 # full deploy
    python3 deploy.py --skip-install  # skip npm install (deps already present)
    python3 deploy.py --destroy       # tear everything down

Requirements: Node.js 18+, Python 3.12, AWS CLI configured, AWS CDK CLI.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
CDK_DIR = os.path.join(ROOT, "cdk")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
FRONTEND_SRC_DIR = os.path.join(FRONTEND_DIR, "src")
VITE_ENV_TYPES = os.path.join(FRONTEND_SRC_DIR, "vite-env.d.ts")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
REGION = "ap-south-1"
STACK_NAME = "SolarPortalStack"
AMPLIFY_BRANCH = "main"


def run(cmd, cwd, capture=False):
    print(f"\n\033[1;34m$ {' '.join(cmd)}\033[0m  (in {os.path.relpath(cwd, ROOT)})")
    if capture:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        return result.stdout
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return None


def npm_install():
    run(["npm", "install"], CDK_DIR)
    run(["npm", "install"], FRONTEND_DIR)


def bootstrap():
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")
    if not account:
        account = run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            ROOT, capture=True,
        ).strip()
    run(["npx", "cdk", "bootstrap", f"aws://{account}/{REGION}"], CDK_DIR)


def ensure_vite_env_types():
    """Write frontend/src/vite-env.d.ts if missing.

    Vite's client types augment ImportMeta with `env` (for VITE_* vars) and
    declare ambient modules for CSS/asset imports. Without this reference the
    TypeScript build fails on `import.meta.env.VITE_API_URL` and `import './App.css'`.
    Idempotent: only writes the file if it doesn't already exist.
    """
    if os.path.exists(VITE_ENV_TYPES):
        return
    os.makedirs(FRONTEND_SRC_DIR, exist_ok=True)
    with open(VITE_ENV_TYPES, "w") as f:
        f.write('/// <reference types="vite/client" />\n')
    print(f"Wrote {os.path.relpath(VITE_ENV_TYPES, ROOT)} (Vite client type reference)")


def build_frontend():
    ensure_vite_env_types()
    run(["npm", "run", "build"], FRONTEND_DIR)


def cdk_deploy(context=None):
    cmd = ["npx", "cdk", "deploy", "--require-approval", "never", "--outputs-file", "outputs.json"]
    for key, val in (context or {}).items():
        cmd += ["-c", f"{key}={val}"]
    run(cmd, CDK_DIR)
    with open(os.path.join(CDK_DIR, "outputs.json")) as f:
        outputs = json.load(f)
    return outputs.get(STACK_NAME, {})


def write_env(api_url):
    env_path = os.path.join(FRONTEND_DIR, ".env")
    with open(env_path, "w") as f:
        f.write(f"VITE_API_URL={api_url}\n")
    print(f"\nWrote {os.path.relpath(env_path, ROOT)} with VITE_API_URL={api_url}")


def zip_dist() -> str:
    zip_path = os.path.join(FRONTEND_DIR, "dist.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _dirs, files in os.walk(DIST_DIR):
            for name in files:
                full = os.path.join(dirpath, name)
                zf.write(full, os.path.relpath(full, DIST_DIR))
    return zip_path


def amplify_publish(app_id: str):
    """Zip frontend/dist and publish it to the Amplify branch (manual deploy)."""
    zip_path = zip_dist()

    create_out = run([
        "aws", "amplify", "create-deployment",
        "--app-id", app_id, "--branch-name", AMPLIFY_BRANCH,
        "--region", REGION, "--output", "json",
    ], ROOT, capture=True)
    dep = json.loads(create_out)
    job_id, upload_url = dep["jobId"], dep["zipUploadUrl"]

    run(["curl", "-sS", "-X", "PUT", "-H", "Content-Type: application/zip",
         "--data-binary", f"@{zip_path}", upload_url], ROOT)

    run([
        "aws", "amplify", "start-deployment",
        "--app-id", app_id, "--branch-name", AMPLIFY_BRANCH,
        "--job-id", job_id, "--region", REGION,
    ], ROOT, capture=True)

    # Poll until the deployment job finishes
    for _ in range(30):
        status_out = run([
            "aws", "amplify", "get-job",
            "--app-id", app_id, "--branch-name", AMPLIFY_BRANCH,
            "--job-id", job_id, "--region", REGION, "--output", "json",
        ], ROOT, capture=True)
        status = json.loads(status_out)["job"]["summary"]["status"]
        print(f"  Amplify deployment: {status}")
        if status == "SUCCEED":
            os.remove(zip_path)
            return
        if status in ("FAILED", "CANCELLED"):
            print(f"Amplify deployment {status}", file=sys.stderr)
            sys.exit(1)
        time.sleep(5)
    print("Amplify deployment timed out", file=sys.stderr)
    sys.exit(1)


def deploy(skip_install, context=None):
    if not skip_install:
        npm_install()
    bootstrap()

    # Deploy the stack, then build the frontend against the real API URL and
    # publish it to Amplify.
    outputs = cdk_deploy(context)
    api_url = outputs.get("ApiUrl")
    app_id = outputs.get("AmplifyAppId")
    if not api_url or not app_id:
        print("ApiUrl / AmplifyAppId not found in stack outputs", file=sys.stderr)
        sys.exit(1)

    write_env(api_url)
    build_frontend()
    amplify_publish(app_id)

    print("\n\033[1;32mDeployment complete.\033[0m")
    for key, val in outputs.items():
        print(f"  {key}: {val}")


def destroy():
    run(["npx", "cdk", "destroy", "--force"], CDK_DIR)
    print("\n\033[1;32mStack destroyed.\033[0m")


def main():
    parser = argparse.ArgumentParser(description="Deploy the MNRE Solar Panel Verification Portal")
    parser.add_argument("--skip-install", action="store_true", help="skip npm install")
    parser.add_argument("--destroy", action="store_true", help="tear down the stack")
    args = parser.parse_args()

    if args.destroy:
        destroy()
    else:
        deploy(args.skip_install)


if __name__ == "__main__":
    main()
