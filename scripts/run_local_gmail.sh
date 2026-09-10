#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -x .venv/bin/flask ]]; then
  echo "Le venv est absent. Lance d'abord : python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

read -r -s -p "Mot de passe d'application Gmail : " T24_SMTP_PASSWORD
echo
if [[ -z "$T24_SMTP_PASSWORD" ]]; then
  echo "Mot de passe Gmail manquant." >&2
  exit 1
fi

export T24_MAIL_MODE="gmail"
export T24_SMTP_HOST="smtp.gmail.com"
export T24_SMTP_PORT="587"
export T24_SMTP_USER="cedzt24@gmail.com"
export T24_SMTP_PASSWORD
export T24_MAIL_FROM="Cedz Are Shooting <cedzt24@gmail.com>"

exec .venv/bin/flask --app app run --debug
