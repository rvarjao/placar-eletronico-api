import hmac
import os
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, request


deploy_bp = Blueprint("deploy", __name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@deploy_bp.post("/deploy")
def deploy():
    configured_token = os.environ.get("DEPLOY_TOKEN", "")
    received_token = request.headers.get("X-Deploy-Token", "")

    if not configured_token:
        return jsonify({"error": "DEPLOY_TOKEN não configurado"}), 503

    if not hmac.compare_digest(received_token, configured_token):
        return jsonify({"error": "Não autorizado"}), 401

    result = subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)

    if result.returncode != 0:
        return jsonify({"error": "Falha ao atualizar o repositório", "output": output}), 500

    return jsonify({"status": "updated", "output": output})
