"""Backend REST API - Sistem Polling / Voting Kampus.

Hanya memakai pustaka standar Python (tanpa framework).
Data suara disimpan di file JSON pada folder DATA_DIR. Di Docker, folder ini
adalah Named Volume (polling-db-data) sehingga data tetap ada walau container dihapus.

Endpoint:
  GET    /health            -> cek aplikasi hidup
  GET    /votes             -> perolehan suara A vs B + daftar catatan suara
  POST   /votes             -> kirim suara, body JSON: {"option": "A"} atau {"option": "B"}
  DELETE /votes?index=X     -> hapus satu catatan suara berdasarkan nomor urut (mulai 0)
"""
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DATA_DIR = os.environ.get("DATA_DIR", "/var/lib/backend_data")
DATA_FILE = os.path.join(DATA_DIR, "votes.json")
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "5000"))
VALID_OPTIONS = ("A", "B")
MAX_BODY_BYTES = 10_000

# Mencegah dua permintaan menulis file pada saat yang sama.
lock = threading.Lock()


def load_votes():
    """Baca daftar suara dari file JSON. File belum ada atau rusak -> daftar kosong."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_votes(votes):
    """Tulis ke file sementara dulu, lalu ganti file asli (aman bila proses terhenti)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(votes, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)


def summary(votes):
    """Susun ringkasan: total, perolehan per opsi, dan seluruh catatan."""
    results = {option: 0 for option in VALID_OPTIONS}
    for vote in votes:
        if vote.get("option") in results:
            results[vote["option"]] += 1
    return {"total": len(votes), "results": results, "votes": votes}


class Handler(BaseHTTPRequestHandler):
    server_version = "PollingAPI/1.0"

    # ---------- utilitas ----------
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._send(status, {"error": message})

    def _route(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        return path, parse_qs(parsed.query)

    def _guard(self, handler):
        """Tangkap error tak terduga supaya server tidak pernah crash."""
        try:
            handler()
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc!r}", flush=True)
            try:
                self._error(500, "Terjadi kesalahan internal pada server")
            except Exception:  # koneksi sudah putus
                pass

    # ---------- GET ----------
    def do_GET(self):
        self._guard(self._get)

    def _get(self):
        path, _ = self._route()
        if path == "/health":
            return self._send(200, {"status": "ok"})
        if path == "/votes":
            with lock:
                votes = load_votes()
            return self._send(200, summary(votes))
        return self._error(404, "Endpoint tidak ditemukan")

    # ---------- POST ----------
    def do_POST(self):
        self._guard(self._post)

    def _post(self):
        path, _ = self._route()
        if path != "/votes":
            return self._error(404, "Endpoint tidak ditemukan")

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._error(400, "Header Content-Length tidak valid")
        if length <= 0:
            return self._error(400, "Body kosong. Kirim JSON: {\"option\": \"A\"} atau {\"option\": \"B\"}")
        if length > MAX_BODY_BYTES:
            return self._error(413, "Body terlalu besar")

        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error(400, "Body bukan JSON yang valid")
        if not isinstance(data, dict):
            return self._error(400, "Body harus berupa objek JSON")

        option = data.get("option")
        if not isinstance(option, str) or option.strip().upper() not in VALID_OPTIONS:
            return self._error(400, "Field 'option' wajib diisi dengan 'A' atau 'B'")
        option = option.strip().upper()

        record = {"option": option, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with lock:
            votes = load_votes()
            votes.append(record)
            save_votes(votes)
        payload = summary(votes)
        payload["message"] = "Suara tersimpan"
        payload["vote"] = record
        return self._send(201, payload)

    # ---------- DELETE ----------
    def do_DELETE(self):
        self._guard(self._delete)

    def _delete(self):
        path, query = self._route()
        if path != "/votes":
            return self._error(404, "Endpoint tidak ditemukan")

        values = query.get("index")
        if not values:
            return self._error(400, "Parameter 'index' wajib diisi, contoh: /votes?index=0")
        try:
            index = int(values[0])
        except ValueError:
            return self._error(400, "Parameter 'index' harus berupa angka bulat")
        if index < 0:
            return self._error(400, "Parameter 'index' tidak boleh negatif")

        with lock:
            votes = load_votes()
            if index >= len(votes):
                return self._error(404, f"Catatan suara dengan index {index} tidak ditemukan")
            removed = votes.pop(index)
            save_votes(votes)
        payload = summary(votes)
        payload["message"] = "Catatan suara dihapus"
        payload["deleted"] = removed
        return self._send(200, payload)

    # ---------- metode lain tidak didukung ----------
    def do_PUT(self):
        self._error(405, "Metode tidak didukung")

    def do_PATCH(self):
        self._error(405, "Metode tidak didukung")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Polling API berjalan di port {PORT}, data di {DATA_FILE}", flush=True)
    server.serve_forever()
