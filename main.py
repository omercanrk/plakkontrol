#!/usr/bin/env python3
import os, re, json, smtplib, ssl, sys, traceback
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

DATA_DIR = Path(__file__).parent
STATE_FILE = DATA_DIR / "state.json"

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def send_email(subject: str, body_html: str, body_text: str = None):
    smtp_host = os.getenv("SMTP_HOST","smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT","587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_addr   = os.getenv("ALERT_TO")

    if not (smtp_user and smtp_pass and to_addr):
        print("[WARN] Email not configured; skipping email send.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    if not body_text:
        body_text = re.sub(r"<[^>]+>","", body_html)

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())]()_
