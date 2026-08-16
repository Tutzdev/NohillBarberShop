from flask import Blueprint

from app.common.responses import success

blueprint = Blueprint("health", __name__)


@blueprint.get("/health")
def health():
    return success({"status": "ok"})
