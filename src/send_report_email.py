from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from dotenv import load_dotenv

from accountant import archive_report, build_report, load_config, now_vn, report_email_to

load_dotenv()


def send_resend(to_addr, subject, body):
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        return False
    from_addr = os.environ.get('RESEND_FROM') or 'Daily Accountant <accountant@resend.dev>'
    payload = json.dumps({
        'from': from_addr,
        'to': [to_addr],
        'subject': subject,
        'text': body,
    }).encode('utf-8')
    request = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise SystemExit(f'Resend failed: {exc.code} {detail}') from exc
    return True


def send_smtp(to_addr, subject, body):
    host = os.environ.get('SMTP_HOST')
    user = os.environ.get('SMTP_USER')
    password = os.environ.get('SMTP_PASSWORD')
    if not host or not user or not password:
        return False
    port = int(os.environ.get('SMTP_PORT') or 587)
    from_addr = os.environ.get('SMTP_FROM') or user
    message = EmailMessage()
    message['From'] = from_addr
    message['To'] = to_addr
    message['Subject'] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls(context=context)
        smtp.login(user, password)
        smtp.send_message(message)
    return True


def main():
    config = load_config()
    when = now_vn(config['timezone'])
    body = build_report(config, when)
    path = archive_report(body, when)
    print(body)
    print(f'Archived {path}')
    to_addr = report_email_to(config)
    if not to_addr:
        raise SystemExit('Set REPORT_EMAIL_TO or report_email_to in data/accountant_config.yaml')
    subject = f'Daily accountant {when.date().isoformat()}'
    if send_resend(to_addr, subject, body):
        print(f'Sent via Resend to {to_addr}')
        return
    if send_smtp(to_addr, subject, body):
        print(f'Sent via SMTP to {to_addr}')
        return
    raise SystemExit(
        'Mail credentials missing. Set RESEND_API_KEY (and optional RESEND_FROM) '
        'or SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and optional SMTP_FROM.'
    )


if __name__ == '__main__':
    main()
