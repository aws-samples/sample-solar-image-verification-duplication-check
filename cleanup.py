#!/usr/bin/env python3
"""Tear down the MNRE Solar Panel Verification Portal.

Destroys every AWS resource created by the CDK stack (Lambdas, Step Functions,
API Gateway, DynamoDB tables, S3 buckets, CloudFront distribution). The stack's
S3 buckets use autoDeleteObjects and DynamoDB tables use RemovalPolicy.DESTROY,
so their contents are removed automatically during the destroy.

Usage:
    python3 cleanup.py                 # destroy the stack (asks for confirmation)
    python3 cleanup.py --yes           # destroy without the interactive prompt
    python3 cleanup.py --keep-local    # keep local artifacts (.env, outputs.json)

Requirements: Node.js 18+, AWS CLI configured, AWS CDK CLI.
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CDK_DIR = os.path.join(ROOT, "cdk")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
REGION = "ap-south-1"
STACK_NAME = "SolarPortalStack"

# Local files produced by deploy.py that are safe to remove on cleanup.
LOCAL_ARTIFACTS = [
    os.path.join(CDK_DIR, "outputs.json"),
    os.path.join(FRONTEND_DIR, ".env"),
]


def run(cmd, cwd):
    # Security note: argument-list subprocess (no shell), static commands only.
    # Operator-run teardown tooling; no external input reaches these calls.
    print(f"\n\033[1;34m$ {' '.join(cmd)}\033[0m  (in {os.path.relpath(cwd, ROOT)})")
    result = subprocess.run(cmd, cwd=cwd)  # nosec B603
    if result.returncode != 0:
        sys.exit(result.returncode)


def confirm():
    print(
        f"\nThis will DESTROY the CloudFormation stack '{STACK_NAME}' in {REGION} "
        "and delete all its resources:\n"
        "  - Lambda functions and the shared layer\n"
        "  - Step Functions state machine\n"
        "  - API Gateway REST API\n"
        "  - DynamoDB Submissions and Embeddings tables (all data)\n"
        "  - S3 image and frontend buckets (all objects)\n"
        "  - CloudFront distribution\n"
        "\nThis action cannot be undone."
    )
    answer = input("\nType 'destroy' to continue: ").strip().lower()
    if answer != "destroy":
        print("Aborted. Nothing was deleted.")
        sys.exit(0)


def destroy_stack():
    run(["npx", "cdk", "destroy", "--force"], CDK_DIR)


def remove_local_artifacts():
    for path in LOCAL_ARTIFACTS:
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed local artifact: {os.path.relpath(path, ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="Tear down the MNRE Solar Panel Verification Portal")
    parser.add_argument("--yes", action="store_true", help="skip the interactive confirmation prompt")
    parser.add_argument("--keep-local", action="store_true", help="do not delete local .env / outputs.json")
    args = parser.parse_args()

    if not args.yes:
        confirm()

    destroy_stack()

    if not args.keep_local:
        remove_local_artifacts()

    print("\n\033[1;32mCleanup complete. All stack resources have been destroyed.\033[0m")


if __name__ == "__main__":
    main()
