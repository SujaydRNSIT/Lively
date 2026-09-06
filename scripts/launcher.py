import os
import sys
import time
import re
import signal
import subprocess
import threading
import webbrowser
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
ENV_FILE = ROOT_DIR / ".env"
BACKEND_ENV_FILE = ROOT_DIR / "backend" / ".env"
CLOUDFLARED_EXE = ROOT_DIR / "cloudflared.exe"
PYTHON_EXE = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = ROOT_DIR / "venv" / "Scripts" / "python.exe"

# ANSI color helpers
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

processes = []


def kill_proc_tree(pid: int):
    """Force kill a process and all its children on Windows."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def clean_and_free_ports(*ports):
    """Find and terminate any stale processes holding Lively's ports, cloudflared, or spawned worker sub-processes."""
    killed_pids = set()
    my_pid = os.getpid()

    # 1. Terminate any lingering cloudflared processes from previous sessions
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "cloudflared.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass

    # 2. Check PowerShell TCP connections
    for port in ports:
        try:
            cmd = f'Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess'
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid > 0 and pid != my_pid and pid not in killed_pids:
                        print(f"[*] Freeing port {port} (terminating stale process PID {pid})...")
                        kill_proc_tree(pid)
                        killed_pids.add(pid)
        except Exception:
            pass

    # 3. Check netstat for any listeners missed by Get-NetTCPConnection
    try:
        ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
        for line in ns.stdout.splitlines():
            line_s = line.strip()
            for port in ports:
                if f":{port}" in line_s and "LISTENING" in line_s:
                    parts = line_s.split()
                    if parts and parts[-1].isdigit():
                        pid = int(parts[-1])
                        if pid > 0 and pid != my_pid and pid not in killed_pids:
                            print(f"[*] Freeing port {port} via netstat (terminating PID {pid})...")
                            kill_proc_tree(pid)
                            killed_pids.add(pid)
    except Exception:
        pass

    # 4. Terminate orphaned Python multiprocessing worker processes (spawned by uvicorn reload)
    try:
        cmd = 'Get-CimInstance Win32_Process -Filter "Name like \'python%\' and CommandLine like \'%multiprocessing.spawn%\'" | Select-Object -ExpandProperty ProcessId'
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                pid = int(line)
                if pid > 0 and pid != my_pid and pid not in killed_pids:
                    print(f"[*] Terminating orphaned uvicorn worker process (PID {pid})...")
                    kill_proc_tree(pid)
                    killed_pids.add(pid)
    except Exception:
        pass

    if killed_pids:
        time.sleep(0.5)



def update_env_file(tunnel_url: str):
    """Update BACKEND_PUBLIC_URL in .env and backend/.env"""
    if not ENV_FILE.exists():
        example = ROOT_DIR / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, ENV_FILE)

    content = ""
    if ENV_FILE.exists():
        content = ENV_FILE.read_text(encoding="utf-8")

    pattern = r"^(BACKEND_PUBLIC_URL\s*=\s*).*$"
    if re.search(pattern, content, flags=re.MULTILINE):
        new_content = re.sub(pattern, f"BACKEND_PUBLIC_URL={tunnel_url}", content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\nBACKEND_PUBLIC_URL={tunnel_url}\n"

    ENV_FILE.write_text(new_content, encoding="utf-8")
    BACKEND_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKEND_ENV_FILE.write_text(new_content, encoding="utf-8")


def start_tunnel():
    """Start cloudflared and extract the public tunnel URL."""
    if not CLOUDFLARED_EXE.exists():
        print(f"{RED}[ERROR] cloudflared.exe not found in {ROOT_DIR}!{RESET}")
        print("Please run install.bat or download cloudflared.exe to the project root.")
        sys.exit(1)

    print(f"[*] Starting Cloudflare tunnel to http://localhost:8000 ...")
    proc = subprocess.Popen(
        [str(CLOUDFLARED_EXE), "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(proc)

    tunnel_url = None
    start_time = time.time()
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output lines until we find the public URL or time out (25 seconds)
    while time.time() - start_time < 25:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                break

    if not tunnel_url:
        print(f"{RED}[ERROR] Could not extract trycloudflare URL from cloudflared!{RESET}")
        kill_proc_tree(proc.pid)
        sys.exit(1)

    return proc, tunnel_url


def log_forwarder(stream, prefix, color):
    """Forward stream lines with a colored prefix."""
    try:
        for line in iter(stream.readline, ""):
            line_str = line.strip()
            if line_str:
                print(f"{color}[{prefix}]{RESET} {line_str}")
    except Exception:
        pass


def cleanup(signum=None, frame=None):
    """Stop all child processes cleanly."""
    print(f"\n{YELLOW}[*] Shutting down Lively services...{RESET}")
    for p in processes:
        if p and p.poll() is None:
            kill_proc_tree(p.pid)
    print(f"{GREEN}[OK] All services stopped cleanly.{RESET}")
    sys.exit(0)


def main():
    separate_windows = "--windows" in sys.argv or "--separate" in sys.argv or "-w" in sys.argv

    # Set up signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(f"{BOLD}{CYAN}============================================================{RESET}")
    print(f"{BOLD}{CYAN}                 LIVELY - SYSTEM LAUNCHER                   {RESET}")
    print(f"{BOLD}{CYAN}============================================================{RESET}")

    # 1. Automatically clear past port usages
    print("[*] Automatically clearing any past port usages (ports 8000 & 5173)...")
    clean_and_free_ports(8000, 5173)

    # 2. Start tunnel & get public URL
    tunnel_proc, tunnel_url = start_tunnel()
    print(f"{GREEN}[OK] Public Tunnel URL established: {BOLD}{tunnel_url}{RESET}")

    # 3. Update .env files
    update_env_file(tunnel_url)
    print(f"{GREEN}[OK] Updated BACKEND_PUBLIC_URL in .env and backend/.env{RESET}")

    # Check python executable
    py_exec = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable

    if separate_windows:
        print(f"\n{CYAN}[*] Spawning separate console windows...{RESET}")
        # Start Backend in new window
        backend_cmd = f'start "Lively Backend (Port 8000)" "{py_exec}" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload'
        subprocess.run(["cmd.exe", "/c", backend_cmd], cwd=str(ROOT_DIR), check=False)

        # Start Frontend in new window
        frontend_cmd = 'start "Lively Frontend (Port 5173)" cmd /k npm run dev'
        subprocess.run(["cmd.exe", "/c", frontend_cmd], cwd=str(FRONTEND_DIR), check=False)
    else:
        # Start Backend
        print("[*] Starting backend uvicorn server on http://localhost:8000 ...")
        backend_proc = subprocess.Popen(
            [py_exec, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        processes.append(backend_proc)
        threading.Thread(target=log_forwarder, args=(backend_proc.stdout, "BACKEND", GREEN), daemon=True).start()

        # Start Frontend
        print("[*] Starting frontend Vite server on http://localhost:5173 ...")
        frontend_proc = subprocess.Popen(
            ["npm.cmd", "run", "dev"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        processes.append(frontend_proc)
        threading.Thread(target=log_forwarder, args=(frontend_proc.stdout, "FRONTEND", CYAN), daemon=True).start()

        # Stream remaining tunnel logs quietly in background
        threading.Thread(target=log_forwarder, args=(tunnel_proc.stdout, "TUNNEL", YELLOW), daemon=True).start()

    time.sleep(2.5)

    print(f"\n{BOLD}{GREEN}============================================================{RESET}")
    print(f"{BOLD}{GREEN}              LIVELY VOICE AI SYSTEM IS READY!              {RESET}")
    print(f"{BOLD}{GREEN}============================================================{RESET}")
    print(f"  {BOLD}Frontend Cockpit:{RESET}  {CYAN}http://localhost:5173{RESET}")
    print(f"  {BOLD}Backend API:{RESET}       {GREEN}http://localhost:8000{RESET}")
    print(f"  {BOLD}Public Tunnel:{RESET}     {YELLOW}{tunnel_url}{RESET}")
    print(f"  {BOLD}Agent LLM Proxy:{RESET}   {YELLOW}{tunnel_url}/v1/chat/completions{RESET}")
    print(f"{BOLD}{GREEN}============================================================{RESET}")
    print(f"{YELLOW}Press Ctrl+C anytime to stop all services.{RESET}\n")

    # Open browser
    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    # Wait for processes
    try:
        while True:
            time.sleep(1)
            # Check if any main process crashed unexpectedly
            for p in processes:
                if p.poll() is not None and p.poll() != 0:
                    print(f"\n{RED}[!] A service stopped unexpectedly (exit code {p.poll()}).{RESET}")
                    cleanup()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
