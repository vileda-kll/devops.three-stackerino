import os
import socket
import psycopg
from flask import Flask, jsonify, request

app = Flask(__name__)

# Environment variables (with default values)
PORT   = int(os.getenv("PORT", 5500))      # e.g. "5500"
NUMBER = os.getenv("NUMBER", "0")          # e.g. "1" (useful to tell backends apart)

# WHERE is the database? (the backend's upstream)
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 5432))
DB_NAME     = os.getenv("DB_NAME", "stackerino")
DB_USER     = os.getenv("DB_USER", "stackerino")
DB_PASSWORD = os.getenv("DB_PASSWORD", "stackerino")


def connect_db():
    # The BACKEND server connects to the DATABASE server (service-to-service call)
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, connect_timeout=3,
    )


def db_error(err):
    print(f"Could not use the database at {DB_HOST}:{DB_PORT}: {err}")
    return jsonify({"error": "The database is not responding", "detail": str(err).strip()}), 503


# The backend speaks JSON (data), not HTML (pages).
@app.get("/api/messages")
def list_messages():
    try:
        with connect_db() as conn:
            rows = conn.execute(
                "SELECT id, author, text, created_at FROM messages ORDER BY id DESC LIMIT 20"
            ).fetchall()
    except psycopg.Error as err:
        return db_error(err)

    return jsonify({
        "backend_number": NUMBER,
        "backend_hostname": socket.gethostname(),
        "messages": [
            {"id": i, "author": a, "text": t, "created_at": c.strftime("%Y-%m-%d %H:%M:%S")}
            for (i, a, t, c) in rows
        ],
    })


@app.post("/api/messages")
def create_message():
    data = request.get_json(silent=True) or {}
    author = str(data.get("author", "")).strip()[:50]
    text = str(data.get("text", "")).strip()[:280]
    if not author or not text:
        return jsonify({"error": "The 'author' and 'text' fields are required"}), 400

    try:
        with connect_db() as conn:
            (new_id,) = conn.execute(
                "INSERT INTO messages (author, text) VALUES (%s, %s) RETURNING id", (author, text)
            ).fetchone()
    except psycopg.Error as err:
        return db_error(err)

    return jsonify({"id": new_id, "author": author, "text": text}), 201


# Health-check: is the backend alive? And can it talk to the database?
@app.get("/healthcheck")
def healthcheck():
    try:
        with connect_db() as conn:
            conn.execute("SELECT 1")
        return jsonify({"backend": "ok", "database": "ok"}), 200
    except psycopg.Error as err:
        return jsonify({"backend": "ok", "database": "error", "detail": str(err).strip()}), 503


@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        with connect_db() as conn:
            (count,) = conn.execute('SELECT COUNT(*) FROM messages;').fetchone()
        return jsonify({"total_messages": count})
    except psycopg.Error as err:
        return db_error(err)


if __name__ == "__main__":
    # 0.0.0.0 = listen on ALL network interfaces (needed for other machines to reach us)
    print(f"Backend {NUMBER} listening on http://0.0.0.0:{PORT}/api/messages")
    print(f"The backend will use the database at {DB_HOST}:{DB_PORT}/{DB_NAME} (user {DB_USER})")
    app.run(host="0.0.0.0", port=PORT)
