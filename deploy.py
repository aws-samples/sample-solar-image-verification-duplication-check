#!/usr/bin/env python3
"""End-to-end deploy for the MNRE Solar Panel Verification Portal.

Wraps the existing AWS CDK app so the whole stack (Lambdas, Step Functions,
API Gateway, DynamoDB, S3, CloudFront + frontend) deploys with one command.

Flow:
  1. npm install in cdk/ and frontend/
  2. cdk bootstrap (idempotent)
  3. build frontend (placeholder, so the first cdk deploy has assets)
  4. cdk deploy  -> capture ApiUrl output
  5. write frontend/.env with VITE_API_URL
  6. rebuild frontend + cdk deploy again (CloudFront now serves API-wired build)

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

ROOT = os.path.dirname(os.path.abspath(__file__))
CDK_DIR = os.path.join(ROOT, "cdk")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
REGION = "ap-south-1"
STACK_NAME = "MnreSolarPanelPocStack"


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


def build_frontend():
    run(["npm", "run", "build"], FRONTEND_DIR)


def cdk_deploy():
    run(["npx", "cdk", "deploy", "--require-approval", "never", "--outputs-file", "outputs.json"], CDK_DIR)
    with open(os.path.join(CDK_DIR, "outputs.json")) as f:
        outputs = json.load(f)
    return outputs.get(STACK_NAME, {})


def write_env(api_url):
    env_path = os.path.join(FRONTEND_DIR, ".env")
    with open(env_path, "w") as f:
        f.write(f"VITE_API_URL={api_url}\n")
    print(f"\nWrote {os.path.relpath(env_path, ROOT)} with VITE_API_URL={api_url}")


def deploy(skip_install):
    if not skip_install:
        npm_install()
    bootstrap()

    # First deploy: build placeholder frontend so BucketDeployment has assets,
    # then provision the stack and read the API URL.
    build_frontend()
    outputs = cdk_deploy()
    api_url = outputs.get("ApiUrl")
    if not api_url:
        print("ApiUrl not found in stack outputs", file=sys.stderr)
        sys.exit(1)

    # Second deploy: rebuild frontend against the real API URL and re-upload.
    write_env(api_url)
    build_frontend()
    outputs = cdk_deploy()

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
