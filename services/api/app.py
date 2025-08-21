
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

    try:
        # isfile check is sufficient, as it returns false for non-existent paths
        if not os.path.isfile(safe_path_abs):
            return jsonify({"code": 404, "message": "Not found"}), 404

        with open(safe_path_abs, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return jsonify({"path": path, "content": content})
    except IOError as e:
        # This will catch FileNotFoundError and other I/O errors
        app.logger.error(f"Failed to read file at {safe_path_abs}: {e}")
        return jsonify({"code": 500, "message": "Failed to read file"}), 500
