
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

WORK_DIR = os.getenv("WORK_DIR", ".")

@app.get("/api/file")
def api_get_file():
    path = request.args.get("path","")
    if not path:
        return jsonify({"code": 400, "message": "Bad Request"}), 400

    work_dir_abs = os.path.abspath(WORK_DIR)
    safe_path_abs = os.path.abspath(os.path.join(work_dir_abs, path))

    if not safe_path_abs.startswith(work_dir_abs):
        return jsonify({"code": 403, "message": "Forbidden"}), 403

    if not os.path.exists(safe_path_abs) or not os.path.isfile(safe_path_abs):
        return jsonify({"code": 404, "message": "Not found"}), 404

    with open(safe_path_abs, "r", encoding="utf-8", errors="ignore") as f:
        return jsonify({"path": path, "content": f.read()})
