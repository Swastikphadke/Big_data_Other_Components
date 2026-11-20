"""Shared BigQuery client for Activity 5, authenticated with the user's gcloud login
(short-lived access token from `gcloud auth print-access-token`; no key files stored)."""
import os
import subprocess

from google.cloud import bigquery
from google.oauth2.credentials import Credentials

PROJECT, DATASET, LOCATION = "bigdatasla", "weblogs", "asia-south1"
TABLE = f"{PROJECT}.{DATASET}.access_logs"
GCLOUD = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")


def client():
    tok = subprocess.run([GCLOUD, "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
    return bigquery.Client(project=PROJECT, credentials=Credentials(tok), location=LOCATION)
