import json
import os

import boto3
import psycopg

_secrets = boto3.client('secretsmanager')
_conn = None
_creds = None


def _load_credentials() -> dict:
    global _creds
    if _creds is not None:
        return _creds
    secret_arn = os.environ['DB_SECRET_ARN']
    raw = _secrets.get_secret_value(SecretId=secret_arn)['SecretString']
    _creds = json.loads(raw)
    return _creds


def get_connection() -> psycopg.Connection:
    """Return a cached psycopg connection, reconnecting if the previous one closed.

    Connection is reused across warm Lambda invocations. The RDS host/port/dbname
    come from environment variables; the username/password come from the Secrets
    Manager secret referenced by DB_SECRET_ARN.
    """
    global _conn
    if _conn is not None and not _conn.closed:
        return _conn

    creds = _load_credentials()
    _conn = psycopg.connect(
        host=os.environ['DB_HOST'],
        port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ['DB_NAME'],
        user=creds['username'],
        password=creds['password'],
        connect_timeout=10,
        autocommit=True,
    )
    return _conn
