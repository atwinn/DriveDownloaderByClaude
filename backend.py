"""Drive Downloader backend — drives rclone to download Google Drive files by link.

Exposes an Api class whose public methods are called from the UI (JS) through
pywebview. All long-running work happens in background threads; the UI polls
list_downloads() to refresh.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

REMOTE = "drivedl"            # rclone remote name we manage
SCOPE = "drive.readonly"      # read-only is enough for downloading

if sys.platform.startswith("win"):
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "DriveDownloader"
else:
    DATA_DIR = Path.home() / "Library" / "Application Support" / "DriveDownloader"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA_DIR / "jobs.json"

# On Windows, keep rclone subprocesses from flashing a console window.
NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0

# rclone "--stats-one-line" output, e.g. (the "Transferred:" label is dropped
# in one-line mode, only a log-level prefix remains):
#   "2026/06/15 10:50:56 NOTICE:  12.3 MiB / 100.0 MiB, 12%, 2.3 MiB/s, ETA 37s"
STATS_RE = re.compile(
    r"([\d.]+\s*[KMGTPE]?i?B)\s*/\s*([\d.]+\s*[KMGTPE]?i?B),\s*(\d+)%"
    r"(?:,\s*([\d.]+\s*[KMGTPE]?i?B/s))?(?:,\s*ETA\s*(\S+))?"
)

# Per-file completion line, e.g. "...INFO  : sub1/f1.bin: Copied (new)"
COPIED_RE = re.compile(r":\s+([^:]+):\s+Copied")


def find_rclone():
    # Prefer the copy bundled inside the app (PyInstaller sets sys._MEIPASS).
    base = getattr(sys, "_MEIPASS", None)
    if base:
        for n in ("rclone.exe", "rclone"):
            bundled = os.path.join(base, n)
            if os.path.exists(bundled):
                return bundled
    return shutil.which("rclone") or "/opt/homebrew/bin/rclone"


def parse_drive_id(link):
    """Return (id, kind) where kind is 'file' or 'folder'. kind=None if not parsed."""
    link = link.strip()
    if not link:
        return None, None
    # Bare ID (no slashes/spaces) — treat as file id
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", link):
        return link, "file"
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", link)
    if m:
        return m.group(1), "folder"
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", link)
    if m:
        return m.group(1), "file"
    m = re.search(r"/(?:document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)", link)
    if m:
        return m.group(1), "gdoc"
    m = re.search(r"[?&]id=([A-Za-z0-9_-]+)", link)
    if m:
        return m.group(1), "file"
    return None, None


class Api:
    def __init__(self):
        self.window = None
        self.rclone = find_rclone()
        self.jobs = {}            # id -> job dict
        self.procs = {}           # id -> Popen
        self.lock = threading.Lock()
        self.login_state = {"state": "idle", "message": ""}
        self.settings = {"default_dest": str(Path.home() / "Downloads"), "lang": "vi"}
        self._load()

    # ---------- persistence ----------
    def _load(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.settings.update(data.get("settings", {}))
                for j in data.get("jobs", []):
                    # threads don't survive restart: mark unfinished as interrupted
                    if j.get("status") in ("downloading", "queued"):
                        j["status"] = "interrupted"
                    self.jobs[j["id"]] = j
            except Exception:
                pass

    def _save(self):
        with self.lock:
            data = {
                "settings": self.settings,
                "jobs": list(self.jobs.values()),
            }
        STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ---------- auth ----------
    def auth_status(self):
        try:
            out = subprocess.run(
                [self.rclone, "listremotes"],
                capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
            ).stdout
            configured = f"{REMOTE}:" in out.splitlines()
        except Exception:
            configured = False
        return {"configured": configured, "remote": REMOTE}

    def start_login(self):
        if self.login_state["state"] == "running":
            return {"ok": True}
        self.login_state = {"state": "running", "message": ""}
        threading.Thread(target=self._login_worker, daemon=True).start()
        return {"ok": True}

    def _login_worker(self):
        try:
            # config create triggers the OAuth browser flow automatically.
            proc = subprocess.run(
                [self.rclone, "config", "create", REMOTE, "drive", "scope", SCOPE],
                capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW,
            )
            if proc.returncode == 0 and self.auth_status()["configured"]:
                self.login_state = {"state": "done", "message": ""}
            else:
                msg = (proc.stderr or proc.stdout or "").strip()
                self.login_state = {"state": "error", "message": msg[-500:]}
        except subprocess.TimeoutExpired:
            self.login_state = {"state": "error", "message": "timeout"}
        except Exception as e:
            self.login_state = {"state": "error", "message": str(e)}

    def login_status(self):
        return self.login_state

    def logout(self):
        try:
            subprocess.run([self.rclone, "config", "delete", REMOTE],
                           capture_output=True, text=True, timeout=10,
                           creationflags=NO_WINDOW)
        except Exception:
            pass
        return {"ok": True}

    # ---------- settings ----------
    def get_settings(self):
        return self.settings

    def set_default_dest(self, path):
        if path:
            self.settings["default_dest"] = path
            self._save()
        return self.settings

    def set_lang(self, lang):
        if lang in ("vi", "en"):
            self.settings["lang"] = lang
            self._save()
        return self.settings

    def pick_folder(self):
        import webview
        folder = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
        if folder is None:
            folder = webview.FOLDER_DIALOG
        result = self.window.create_file_dialog(folder)
        if result:
            return result[0] if isinstance(result, (list, tuple)) else result
        return None

    def open_folder(self, path):
        p = path or self.settings["default_dest"]
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", p])
            elif sys.platform.startswith("win"):
                os.startfile(p)  # noqa
            else:
                subprocess.Popen(["xdg-open", p])
        except Exception:
            pass
        return {"ok": True}

    # ---------- downloads ----------
    def add_download(self, link, dest=None):
        file_id, kind = parse_drive_id(link or "")
        if not file_id:
            return {"ok": False, "error_code": "bad_link"}
        if kind == "gdoc":
            return {"ok": False, "error_code": "gdoc"}
        dest = dest or self.settings.get("default_dest")
        if not dest or not os.path.isdir(dest):
            return {"ok": False, "error_code": "bad_dest"}

        jid = uuid.uuid4().hex[:8]
        job = {
            "id": jid, "link": link, "file_id": file_id, "kind": kind,
            "name": "", "dest": dest, "save_path": "",
            "folder_name": "",
            "transferred": "", "total": "", "percent": 0,
            "speed": "", "eta": "", "files_done": 0, "last_file": "", "status": "queued",
            "error": "", "added_at": time.time(), "finished_at": None,
        }
        with self.lock:
            self.jobs[jid] = job
        self._save()
        threading.Thread(target=self._download_worker, args=(jid,), daemon=True).start()
        return {"ok": True, "id": jid}

    def _set(self, jid, **kw):
        with self.lock:
            if jid in self.jobs:
                self.jobs[jid].update(kw)

    def _drive_folder_name(self, folder_id):
        """Fetch a Drive folder's real name from its ID via the Drive API,
        reusing the OAuth token rclone already stored. Returns None on failure."""
        # A cheap listing op makes rclone refresh+persist the access token first.
        try:
            subprocess.run(
                [self.rclone, "lsf", f"{REMOTE},root_folder_id={folder_id}:",
                 "--max-depth", "0"],
                capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW,
            )
        except Exception:
            pass
        try:
            dump = json.loads(subprocess.run(
                [self.rclone, "config", "dump"],
                capture_output=True, text=True, timeout=15,
                creationflags=NO_WINDOW).stdout)
            token = json.loads(dump[REMOTE]["token"])["access_token"]
            req = urllib.request.Request(
                f"https://www.googleapis.com/drive/v3/files/{folder_id}"
                f"?fields=name&supportsAllDrives=true",
                headers={"Authorization": "Bearer " + token})
            try:
                import ssl
                import certifi
                ctx = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                ctx = None
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                return (json.load(r).get("name") or "").strip() or None
        except Exception:
            return None

    @staticmethod
    def _safe_name(name):
        return re.sub(r'[/\\:*?"<>|]', "_", name).strip().rstrip(".") or "Drive_folder"

    @staticmethod
    def _unique_dir(base):
        if not os.path.exists(base):
            return base
        i = 2
        while os.path.exists(f"{base} ({i})"):
            i += 1
        return f"{base} ({i})"

    def _download_worker(self, jid):
        job = self.jobs.get(jid)
        if not job:
            return
        dest = job["dest"]
        file_id = job["file_id"]
        before = set(os.listdir(dest)) if os.path.isdir(dest) else set()

        is_folder = job["kind"] == "folder"
        folder_name = job.get("folder_name", "")
        if is_folder:
            if job.get("save_path"):                       # retry: reuse same folder
                target = job["save_path"]
            else:
                # folder_name stays "" while fetching → UI shows a localized
                # "getting folder name…" placeholder.
                folder_name = self._safe_name(
                    self._drive_folder_name(file_id) or f"Drive_{file_id[:8]}")
                target = self._unique_dir(os.path.join(dest, folder_name))
                self._set(jid, folder_name=folder_name, save_path=target)
            os.makedirs(target, exist_ok=True)
            cmd = [self.rclone, "copy", f"{REMOTE},root_folder_id={file_id}:", target]
        else:
            self._set(jid, save_path=dest)
            cmd = [self.rclone, "backend", "copyid", f"{REMOTE}:", file_id, dest + os.sep]
        cmd += [
            "--inplace", "-v",
            "--stats=1s", "--stats-one-line", "--stats-log-level", "NOTICE",
            "--retries", "5", "--low-level-retries", "20",
        ]

        self._set(jid, status="downloading", error="")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, creationflags=NO_WINDOW)
        except Exception as e:
            self._set(jid, status="error", error=str(e))
            self._save()
            return
        self.procs[jid] = proc

        # For single files, poll the dest dir to surface the real file name.
        stop = threading.Event()
        if not is_folder:
            threading.Thread(target=self._name_poller, args=(jid, dest, before, stop),
                             daemon=True).start()

        tail = []
        done = 0
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            tail.append(line)
            tail[:] = tail[-15:]
            m = STATS_RE.search(line)
            if m:
                transferred, total, pct, speed, eta = m.groups()
                speed = "" if not speed or speed.startswith("0 ") else speed
                eta = "" if eta in (None, "-", "0s") else eta
                self._set(jid, transferred=transferred, total=total,
                          percent=int(pct), speed=speed, eta=eta)
            c = COPIED_RE.search(line)
            if c:
                done += 1
                last = c.group(1).strip()
                self._set(jid, files_done=done, last_file=last)
        proc.wait()
        stop.set()
        self.procs.pop(jid, None)

        cur = self.jobs.get(jid, {})
        if cur.get("status") == "cancelled":
            self._save()
            return
        if proc.returncode == 0:
            self._set(jid, status="done", percent=100, speed="", eta="",
                      finished_at=time.time())
        else:
            err = "\n".join(tail[-6:]) or f"rclone thoát với mã {proc.returncode}"
            self._set(jid, status="error", error=err)
        self._save()

    def _name_poller(self, jid, dest, before, stop):
        while not stop.is_set():
            try:
                new = [f for f in os.listdir(dest) if f not in before]
                if new:
                    # pick the largest new entry as the active file
                    new.sort(key=lambda f: self._safe_size(os.path.join(dest, f)),
                             reverse=True)
                    self._set(jid, name=new[0].replace(".partial", ""))
            except Exception:
                pass
            time.sleep(0.8)

    @staticmethod
    def _safe_size(p):
        try:
            return os.path.getsize(p)
        except Exception:
            return 0

    def cancel_download(self, jid):
        self._set(jid, status="cancelled", speed="", eta="")
        proc = self.procs.get(jid)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self._save()
        return {"ok": True}

    def retry_download(self, jid):
        job = self.jobs.get(jid)
        if not job:
            return {"ok": False, "error": "Không tìm thấy."}
        self._set(jid, status="queued", error="", percent=0,
                  transferred="", total="", speed="", eta="", finished_at=None)
        threading.Thread(target=self._download_worker, args=(jid,), daemon=True).start()
        return {"ok": True}

    def remove_download(self, jid, delete_file=False):
        job = self.jobs.get(jid)
        if not job:
            return {"ok": True}
        if job.get("status") == "downloading":
            self.cancel_download(jid)
        if delete_file and job.get("name") and job["name"] != "Đang lấy thông tin…":
            try:
                os.remove(os.path.join(job["dest"], job["name"]))
            except Exception:
                pass
        with self.lock:
            self.jobs.pop(jid, None)
        self._save()
        return {"ok": True}

    def clear_finished(self):
        with self.lock:
            for jid in [j for j, v in self.jobs.items()
                        if v.get("status") in ("done", "cancelled", "error")]:
                self.jobs.pop(jid, None)
        self._save()
        return {"ok": True}

    def list_downloads(self):
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j: j["added_at"], reverse=True)
            return json.loads(json.dumps(jobs, ensure_ascii=False))
