#!/usr/bin/env python3
import os, re, json, smtplib, ssl, sys, traceback
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
        server.sendmail(smtp_user, [to_addr], msg.as_string())

def parse_price(text, regex):
    if not text:
        return None
    m = re.search(regex, text.replace("\xa0"," "))
    if not m:
        return None
    raw = m.group(1).replace(".","").replace(",",".")
    try:
        return float(raw)
    except Exception:
        return None

def fetch_static(url, headers, timeout):
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def check_once(job, request_timeout):
    url = job["url"]
    headers = job.get("headers") or {}
    html = fetch_static(url, headers, request_timeout)
    soup = BeautifulSoup(html, "html.parser")

    # stok metni oku
    stock_text = ""
    stock_number = None
    if job.get("in_stock_selector"):
        node = soup.select_one(job["in_stock_selector"])
        if node:
            stock_text = node.get_text(" ", strip=True)
            if job.get("stock_number_regex"):
                m = re.search(job["stock_number_regex"], stock_text)
                if m:
                    stock_number = int(m.group(1))

    # fiyat oku
    price = None
    if job.get("price_selector"):
        node = soup.select_one(job["price_selector"])
        if node:
            price_text = node.get_text(" ", strip=True)
            price = parse_price(price_text, job.get("price_regex", r"([0-9]+[.,]?[0-9]*)"))

    return {
        "stock_text": stock_text,
        "stock_number": stock_number,
        "price": price,
    }

def main():
    cfg_path = DATA_DIR / "config.json"
    if not cfg_path.exists():
        print("config.json not found. Copy config.example.json to config.json and edit it.")
        sys.exit(2)

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    request_timeout = int(cfg.get("request_timeout_sec", 25))

    state = load_state()
    messages = []

    for job in cfg.get("checks", []):
        name = job.get("name") or job.get("url")
        print(f"Checking: {name}")

        try:
            result = check_once(job, request_timeout)
            stock_number = result["stock_number"]
            price = result["price"]
            messages.append(f"[{name}] stock_text='{result['stock_text']}' stock_number={stock_number} price={price}")

            thresholds = job.get("alert_stock_thresholds") or []
            prev_alerts = state.get("alerts", {})

            if stock_number is not None and stock_number in thresholds:
                if str(stock_number) not in prev_alerts.get(name, []):
                    # Mail gönder
                    send_email(
                        subject=f"STOCK ALERT: {name} → {stock_number} kaldı!",
                        body_html=f"<p>{name} stok bilgisi:</p><p><b>{result['stock_text']}</b></p>",
                        body_text=f"{name} → {result['stock_text']}"
                    )
                    print(f"ALERT sent for {stock_number}")

                    # state.json içine kaydet
                    prev_alerts.setdefault(name, []).append(str(stock_number))
                    state["alerts"] = prev_alerts

        except Exception as e:
            tb = traceback.format_exc()
            messages.append(f"[{name}] ERROR: {e}\n{tb}")

    print("\n".join(messages))
    save_state(state)

if __name__ == "__main__":
    main()
