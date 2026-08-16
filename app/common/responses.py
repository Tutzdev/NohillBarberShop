from typing import Any

from flask import Response, jsonify


def success(data: Any, status_code: int = 200) -> tuple[Response, int]:
    return jsonify({"data": data}), status_code


def no_content() -> tuple[str, int]:
    return "", 204
