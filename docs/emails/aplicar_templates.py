import argparse
import json
import sys
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

PROJECT = "valorpublico-b1e6d"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SERVICE_ACCOUNT = ROOT / "backend" / "serviceAccountKey.json"
TEMPLATES = HERE / "templates.json"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/identitytoolkit",
]


def session():
    cred = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=SCOPES
    )
    return AuthorizedSession(cred)


def config_url(project):
    return f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/config"


def get_config(client, project):
    response = client.get(config_url(project), timeout=60)
    if response.status_code >= 300:
        raise RuntimeError(f"GET config falhou: {response.status_code} {response.text[:500]}")
    return response.json()


def apply_template(client, project, field, dados):
    body = (HERE / dados["file"]).read_text(encoding="utf-8").strip()
    payload = {
        "notification": {
            "sendEmail": {
                field: {
                    "subject": dados["subject"],
                    "body": body,
                    "bodyFormat": "HTML",
                }
            }
        }
    }
    mask = ",".join(
        f"notification.sendEmail.{field}.{campo}"
        for campo in ("subject", "body", "bodyFormat")
    )
    response = client.patch(
        config_url(project), params={"updateMask": mask}, json=payload, timeout=60
    )
    if response.status_code >= 300:
        return False, response.status_code, response.text
    sender = dados.get("senderDisplayName")
    if sender:
        payload_sender = {
            "notification": {"sendEmail": {field: {"senderDisplayName": sender}}}
        }
        mask_sender = f"notification.sendEmail.{field}.senderDisplayName"
        sender_response = client.patch(
            config_url(project),
            params={"updateMask": mask_sender},
            json=payload_sender,
            timeout=60,
        )
        if sender_response.status_code >= 300:
            print(f"  aviso: senderDisplayName nao aplicado ({sender_response.status_code})")
        else:
            print(f"  senderDisplayName: {sender}")
    return True, response.status_code, response.text


def print_config(cfg):
    send = (cfg.get("notification") or {}).get("sendEmail") or {}
    for field in ("verifyEmailTemplate", "resetPasswordTemplate", "changeEmailTemplate"):
        item = send.get(field) or {}
        print(
            f"  {field}: {item.get('subject')!r} | "
            f"{item.get('bodyFormat')} | {len(item.get('body') or '')} bytes | "
            f"{item.get('senderDisplayName')!r}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--only", choices=["verifyEmailTemplate", "resetPasswordTemplate", "changeEmailTemplate"])
    args = parser.parse_args()

    mapping = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    if args.only:
        mapping = {args.only: mapping[args.only]}

    print(f"Projeto: {args.project}")
    print(f"Credencial: {SERVICE_ACCOUNT}")
    print(f"Templates: {', '.join(mapping)}")

    for field, dados in mapping.items():
        body = (HERE / dados["file"]).read_text(encoding="utf-8")
        print(f"- {field}: {dados['subject']} ({len(body)} bytes)")

    if args.dry_run:
        print("Dry-run: nenhuma alteracao enviada.")
        return 0

    client = session()
    if args.check:
        print("Config atual:")
        print_config(get_config(client, args.project))
        return 0

    for field, dados in mapping.items():
        ok, status, text = apply_template(client, args.project, field, dados)
        if not ok:
            print(f"FALHA em {field}: HTTP {status}")
            print(text[:1200])
            if "EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED" in text:
                print("O Firebase bloqueou a edicao via API neste projeto.")
                return 2
            return 1
        print(f"OK {field}")

    print("Config depois:")
    print_config(get_config(client, args.project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
