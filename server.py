"""BahiPro's local Python web server and JSON API."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, request, send_from_directory

from database import database_connection, get_workspace, initialize_database, save_workspace
from retail_assistant import answer, suggestions


PROJECT_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

WORKSPACE_ENDPOINTS = {"read_workspace", "write_workspace", "read_suggestions", "ask_assistant"}


@app.before_request
def prepare_workspace_database():
    if request.endpoint not in WORKSPACE_ENDPOINTS:
        return None
    raw_id = request.headers.get("X-BahiPro-Workspace", "")
    try:
        workspace_id = str(uuid.UUID(raw_id))
    except (AttributeError, TypeError, ValueError):
        return jsonify({"error": "This browser does not have a valid BahiPro workspace ID."}), 400
    try:
        initialize_database(workspace_id)
    except Exception:
        app.logger.exception("Could not initialize the BahiPro workspace database")
        return jsonify({"error": "The workspace database could not be opened."}), 500
    g.workspace_id = workspace_id
    return None


@app.get("/")
def home():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "BahiPro Python + SQLite", "version": 1})


@app.get("/api/workspace")
def read_workspace():
    workspace, updated_at = get_workspace(g.workspace_id)
    return jsonify({"workspace": workspace, "updatedAt": updated_at})


@app.put("/api/workspace")
def write_workspace():
    payload: dict[str, Any] | None = request.get_json(silent=True)
    if not isinstance(payload, dict) or "workspace" not in payload:
        return jsonify({"error": "Send a JSON object with a workspace field."}), 400
    try:
        updated_at = save_workspace(payload["workspace"], g.workspace_id)
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Could not save the BahiPro workspace")
        return jsonify({"error": "The workspace could not be saved to SQLite."}), 500
    return jsonify({"ok": True, "updatedAt": updated_at})


@app.get("/api/analytics/suggestions")
def read_suggestions():
    try:
        with database_connection(g.workspace_id) as connection:
            return jsonify({"suggestions": suggestions(connection)})
    except Exception:
        app.logger.exception("Could not build local retail suggestions")
        return jsonify({"error": "Could not calculate retail suggestions."}), 500


@app.post("/api/assistant")
def ask_assistant():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
        return jsonify({"error": "Enter a question about your store."}), 400
    question = payload["question"].strip()
    if not question:
        return jsonify({"error": "Enter a question about your store."}), 400
    if len(question) > 500:
        return jsonify({"error": "Keep the question under 500 characters."}), 400
    try:
        with database_connection(g.workspace_id) as connection:
            return jsonify({"answer": answer(connection, question)})
    except Exception:
        app.logger.exception("Could not answer the local retail question")
        return jsonify({"error": "Could not analyze the saved workspace."}), 500


@app.get("/analytics/<path:filename>")
def analytics_asset(filename: str):
    if filename not in {"export.js", "google-sheets.js"}:
        return jsonify({"error": "File not found."}), 404
    return send_from_directory(PROJECT_DIR / "analytics", filename)


@app.get("/assets/<path:filename>")
def image_asset(filename: str):
    return send_from_directory(PROJECT_DIR / "assets", filename)


@app.get("/<path:filename>")
def app_asset(filename: str):
    if filename not in {"app.js", "styles.css", "bahipro-logo.jpeg"}:
        return jsonify({"error": "File not found."}), 404
    return send_from_directory(PROJECT_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("BAHIPRO_PORT", "8000"))
    print(f"BahiPro is running at http://127.0.0.1:{port}")
    print("Local Python server; each browser workspace is stored in its own SQLite file under data/workspaces/")
    app.run(host="127.0.0.1", port=port, debug=False)
