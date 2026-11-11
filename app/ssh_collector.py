import io
import re
import time
from datetime import datetime
import paramiko
from app.config import settings

COLLECTOR_SCRIPT = r"""export LC_ALL=C
echo "---SECTION_OS---"
if [ -f /etc/os-release ]; then
    cat /etc/os-release
elif [ -f /etc/redhat-release ]; then
    cat /etc/redhat-release
elif [ -f /etc/issue ]; then
    head -n 1 /etc/issue
fi

echo "---SECTION_HOST---"
hostname 2>/dev/null

echo "---SECTION_UPTIME---"
cat /proc/uptime 2>/dev/null

echo "---SECTION_LOAD---"
cat /proc/loadavg 2>/dev/null

echo "---SECTION_CPUINFO---"
nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo "1"
grep -m 1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2- || echo "Generic CPU"

echo "---SECTION_MEM---"
cat /proc/meminfo 2>/dev/null

echo "---SECTION_DISK---"
df -k -P 2>/dev/null || df -k 2>/dev/null

echo "---SECTION_NET---"
cat /proc/net/dev 2>/dev/null

echo "---SECTION_PROCS---"
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu 2>/dev/null | head -n 15 || ps -eo pid,user,%cpu,%mem,comm 2>/dev/null | head -n 15 || ps aux 2>/dev/null | head -n 15

echo "---SECTION_CPUSTAT1---"
grep '^cpu ' /proc/stat 2>/dev/null
sleep 0.5
echo "---SECTION_CPUSTAT2---"
grep '^cpu ' /proc/stat 2>/dev/null
"""

def _load_private_key(key_str: str, passphrase: str | None = None) -> paramiko.PKey:
    """Load private key supporting RSA, Ed25519, ECDSA, DSS."""
    key_file = io.StringIO(key_str.strip())
    errors = []
    for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
        key_file.seek(0)
        try:
            return key_cls.from_private_key(key_file, password=passphrase)
        except Exception as e:
            errors.append(f"{key_cls.__name__}: {e}")
    raise ValueError(f"Unable to parse private key. Tried RSA, Ed25519, ECDSA: {'; '.join(errors)}")

def create_ssh_client(
    host: str,
    port: int,
    username: str,
    auth_type: str,
    password: str | None = None,
    private_key: str | None = None,
    passphrase: str | None = None,
    timeout: int = 10
) -> paramiko.SSHClient:
    """Create and connect an SSH client with automatic host key adding."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": host,
        "port": port,
        "username": username,
        "timeout": timeout,
        "banner_timeout": timeout,
        "auth_timeout": timeout,
        "look_for_keys": False,
        "allow_agent": False,
    }

    if auth_type == "key" and private_key:
        pkey = _load_private_key(private_key, passphrase)
        connect_kwargs["pkey"] = pkey
    elif password:
        connect_kwargs["password"] = password
    else:
        raise ValueError("No valid password or private key provided for SSH connection.")

    client.connect(**connect_kwargs)
    return client

def test_ssh_connection(
    host: str,
    port: int,
    username: str,
    auth_type: str,
    password: str | None = None,
    private_key: str | None = None,
    passphrase: str | None = None,
    timeout: int = 8
) -> dict:
    """Test SSH connection to target host and retrieve basic OS info."""
    start_time = time.time()
    try:
        client = create_ssh_client(
            host=host,
            port=port,
            username=username,
            auth_type=auth_type,
            password=password,
            private_key=private_key,
            passphrase=passphrase,
            timeout=timeout
        )
        stdin, stdout, stderr = client.exec_command("uname -s -r -m; hostname", timeout=timeout)
        output = stdout.read().decode("utf-8", errors="ignore").strip()
        client.close()
        latency = round((time.time() - start_time) * 1000, 1)
        return {
            "success": True,
            "message": f"Connection successful ({latency} ms)",
            "details": output,
            "latency_ms": latency
        }
    except Exception as e:
        latency = round((time.time() - start_time) * 1000, 1)
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
            "details": None,
            "latency_ms": latency
        }

def run_remote_command(
    server,
    command: str,
    timeout: int = 15
) -> dict:
    """Run an ad-hoc command on the remote server via SSH."""
    try:
        client = create_ssh_client(
            host=server.host,
            port=server.port,
            username=server.username,
            auth_type=server.auth_type,
            password=server.get_password(),
            private_key=server.get_private_key(),
            passphrase=server.get_passphrase(),
            timeout=settings.SSH_TIMEOUT
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out_str = stdout.read().decode("utf-8", errors="ignore")
        err_str = stderr.read().decode("utf-8", errors="ignore")
        exit_code = stdout.channel.recv_exit_status()
        client.close()
        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "stdout": out_str,
            "stderr": err_str
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e)
        }

def format_uptime(uptime_seconds: float) -> str:
    """Convert uptime seconds to a clean human-readable string."""
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)

def parse_collector_output(output: str, prev_metric: dict | None = None) -> dict:
    """Parse output from bundled Linux shell script."""
    sections = {}
    current_sec = None
    sec_lines = []

    for line in output.splitlines():
        if line.startswith("---SECTION_") and line.endswith("---"):
            if current_sec:
                sections[current_sec] = "\n".join(sec_lines).strip()
            current_sec = line.strip("-")
            sec_lines = []
        else:
            sec_lines.append(line)
    if current_sec:
        sections[current_sec] = "\n".join(sec_lines).strip()

    # 1. OS & Distro Info
    os_name = "Linux"
    os_sec = sections.get("SECTION_OS", "")
    if os_sec:
        pretty_match = re.search(r'PRETTY_NAME="?([^"\n]+)"?', os_sec)
        if pretty_match:
            os_name = pretty_match.group(1)
        else:
            name_match = re.search(r'NAME="?([^"\n]+)"?', os_sec)
            ver_match = re.search(r'VERSION="?([^"\n]+)"?', os_sec)
            if name_match:
                os_name = name_match.group(1)
                if ver_match:
                    os_name += f" {ver_match.group(1)}"
            elif os_sec.strip():
                os_name = os_sec.splitlines()[0].strip()

    # 2. Hostname
    hostname = sections.get("SECTION_HOST", "").strip() or "localhost"

    # 3. Uptime
    uptime_seconds = 0.0
    uptime_str = "0m"
    uptime_sec = sections.get("SECTION_UPTIME", "").strip()
    if uptime_sec:
        try:
            uptime_seconds = float(uptime_sec.split()[0])
            uptime_str = format_uptime(uptime_seconds)
        except Exception:
            pass

    # 4. Load Average
    load_1m, load_5m, load_15m = 0.0, 0.0, 0.0
    load_sec = sections.get("SECTION_LOAD", "").strip()
    if load_sec:
        parts = load_sec.split()
        if len(parts) >= 3:
            try:
                load_1m = float(parts[0])
                load_5m = float(parts[1])
                load_15m = float(parts[2])
            except Exception:
                pass

    # 5. CPU Cores & Model
    cpu_cores = 1
    cpu_model = "Generic CPU"
    cpuinfo_sec = sections.get("SECTION_CPUINFO", "").strip()
    if cpuinfo_sec:
        lines = cpuinfo_sec.splitlines()
        if len(lines) >= 1 and lines[0].strip().isdigit():
            cpu_cores = int(lines[0].strip())
        if len(lines) >= 2 and lines[1].strip():
            cpu_model = lines[1].strip()

    # 6. CPU Usage Percentage
    cpu_percent = 0.0
    stat1 = sections.get("SECTION_CPUSTAT1", "").strip()
    stat2 = sections.get("SECTION_CPUSTAT2", "").strip()
    if stat1 and stat2:
        try:
            vals1 = [float(x) for x in stat1.split()[1:]]
            vals2 = [float(x) for x in stat2.split()[1:]]
            if len(vals1) >= 4 and len(vals2) >= 4:
                # user, nice, system, idle, iowait, irq, softirq, steal
                idle1 = vals1[3] + (vals1[4] if len(vals1) > 4 else 0)
                idle2 = vals2[3] + (vals2[4] if len(vals2) > 4 else 0)
                total1 = sum(vals1)
                total2 = sum(vals2)
                idle_delta = idle2 - idle1
                total_delta = total2 - total1
                if total_delta > 0:
                    cpu_percent = round(max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta))), 1)
        except Exception:
            pass

    # 7. Memory & Swap
    ram_total_mb = 0.0
    ram_used_mb = 0.0
    ram_percent = 0.0
    swap_total_mb = 0.0
    swap_used_mb = 0.0
    swap_percent = 0.0

    mem_sec = sections.get("SECTION_MEM", "").strip()
    if mem_sec:
        mem_data = {}
        for line in mem_sec.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                num = v.strip().split()[0]
                if num.isdigit():
                    mem_data[k.strip()] = float(num) # in kB

        total_kb = mem_data.get("MemTotal", 0.0)
        free_kb = mem_data.get("MemFree", 0.0)
        avail_kb = mem_data.get("MemAvailable", None)
        buffers_kb = mem_data.get("Buffers", 0.0)
        cached_kb = mem_data.get("Cached", 0.0)

        if total_kb > 0:
            ram_total_mb = total_kb / 1024.0
            if avail_kb is not None:
                ram_used_mb = (total_kb - avail_kb) / 1024.0
            else:
                ram_used_mb = (total_kb - (free_kb + buffers_kb + cached_kb)) / 1024.0
            ram_used_mb = max(0.0, ram_used_mb)
            ram_percent = round((ram_used_mb / ram_total_mb) * 100.0, 1)

        swap_total_kb = mem_data.get("SwapTotal", 0.0)
        swap_free_kb = mem_data.get("SwapFree", 0.0)
        if swap_total_kb > 0:
            swap_total_mb = swap_total_kb / 1024.0
            swap_used_mb = (swap_total_kb - swap_free_kb) / 1024.0
            swap_percent = round((swap_used_mb / swap_total_mb) * 100.0, 1)

    # 8. Disk Partitions
    partitions = []
    disk_total_kb = 0.0
    disk_used_kb = 0.0
    disk_sec = sections.get("SECTION_DISK", "").strip()
    if disk_sec:
        skip_types = ("tmpfs", "devtmpfs", "none", "squashfs", "udev", "overlay", "shm")
        for line in disk_sec.splitlines():
            line = line.strip()
            if not line or "Filesystem" in line:
                continue
            parts = line.split()
            if len(parts) >= 6:
                fs = parts[0]
                if any(st in fs.lower() for st in skip_types):
                    continue
                try:
                    tot_kb = float(parts[1])
                    usd_kb = float(parts[2])
                    avail_kb = float(parts[3])
                    pct_str = parts[4].rstrip("%")
                    try:
                        pct = float(pct_str.replace(",", "."))
                    except Exception:
                        pct = 0.0
                    mount = " ".join(parts[5:])

                    partitions.append({
                        "filesystem": fs,
                        "mount": mount,
                        "total_gb": round(tot_kb / (1024.0 * 1024.0), 1),
                        "used_gb": round(usd_kb / (1024.0 * 1024.0), 1),
                        "free_gb": round(avail_kb / (1024.0 * 1024.0), 1),
                        "percent": pct
                    })
                    disk_total_kb += tot_kb
                    disk_used_kb += usd_kb
                except Exception:
                    continue

    disk_total_gb = round(disk_total_kb / (1024.0 * 1024.0), 1)
    disk_used_gb = round(disk_used_kb / (1024.0 * 1024.0), 1)
    disk_percent = round((disk_used_kb / disk_total_kb * 100.0), 1) if disk_total_kb > 0 else 0.0

    # 9. Network Traffic & Rate
    total_rx_bytes = 0
    total_tx_bytes = 0
    net_rx_rate_kbps = 0.0
    net_tx_rate_kbps = 0.0
    net_sec = sections.get("SECTION_NET", "").strip()
    if net_sec:
        for line in net_sec.splitlines():
            if ":" in line:
                iface, data = line.split(":", 1)
                iface = iface.strip()
                if iface == "lo":
                    continue
                fields = data.split()
                if len(fields) >= 9:
                    try:
                        rx = int(fields[0])
                        tx = int(fields[8])
                        total_rx_bytes += rx
                        total_tx_bytes += tx
                    except Exception:
                        pass

    if prev_metric and "total_rx_bytes" in prev_metric and "timestamp" in prev_metric:
        try:
            delta_time = time.time() - prev_metric["timestamp"]
            if delta_time > 0:
                rx_diff = max(0, total_rx_bytes - prev_metric["total_rx_bytes"])
                tx_diff = max(0, total_tx_bytes - prev_metric["total_tx_bytes"])
                net_rx_rate_kbps = round((rx_diff * 8) / (delta_time * 1024.0), 1)
                net_tx_rate_kbps = round((tx_diff * 8) / (delta_time * 1024.0), 1)
        except Exception:
            pass

    # 10. Top Processes
    processes = []
    procs_sec = sections.get("SECTION_PROCS", "").strip()
    if procs_sec:
        lines = procs_sec.splitlines()
        for line in lines:
            line = line.strip()
            if not line or "PID" in line or "COMMAND" in line:
                continue
            parts = line.split(None, 4)
            if len(parts) >= 5:
                try:
                    cpu_val = float(parts[2].replace(",", "."))
                    mem_val = float(parts[3].replace(",", "."))
                    processes.append({
                        "pid": parts[0],
                        "user": parts[1],
                        "cpu": cpu_val,
                        "mem": mem_val,
                        "command": parts[4].strip()
                    })
                except Exception:
                    continue
            elif len(parts) >= 4:
                try:
                    cpu_val = float(parts[2].replace(",", "."))
                    mem_val = float(parts[3].replace(",", "."))
                    processes.append({
                        "pid": parts[0],
                        "user": parts[1],
                        "cpu": cpu_val,
                        "mem": mem_val,
                        "command": "-"
                    })
                except Exception:
                    continue
            if len(processes) >= 10:
                break

    return {
        "os_name": os_name,
        "hostname": hostname,
        "uptime_seconds": uptime_seconds,
        "uptime_str": uptime_str,
        "cpu_cores": cpu_cores,
        "cpu_model": cpu_model,
        "cpu_percent": cpu_percent,
        "ram_total_mb": ram_total_mb,
        "ram_used_mb": ram_used_mb,
        "ram_percent": ram_percent,
        "swap_total_mb": swap_total_mb,
        "swap_used_mb": swap_used_mb,
        "swap_percent": swap_percent,
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_percent": disk_percent,
        "load_1m": load_1m,
        "load_5m": load_5m,
        "load_15m": load_15m,
        "total_rx_bytes": total_rx_bytes,
        "total_tx_bytes": total_tx_bytes,
        "net_rx_rate_kbps": net_rx_rate_kbps,
        "net_tx_rate_kbps": net_tx_rate_kbps,
        "partitions": partitions,
        "processes": processes,
    }

def collect_server_metrics(server, prev_metric: dict | None = None) -> dict:
    """Connect to server via SSH, run collector script, and return structured metric data."""
    client = None
    try:
        client = create_ssh_client(
            host=server.host,
            port=server.port,
            username=server.username,
            auth_type=server.auth_type,
            password=server.get_password(),
            private_key=server.get_private_key(),
            passphrase=server.get_passphrase(),
            timeout=settings.SSH_TIMEOUT
        )
        stdin, stdout, stderr = client.exec_command(COLLECTOR_SCRIPT, timeout=settings.SSH_TIMEOUT + 5)
        raw_output = stdout.read().decode("utf-8", errors="ignore")
        client.close()

        parsed = parse_collector_output(raw_output, prev_metric)
        parsed["success"] = True
        parsed["error"] = None
        return parsed
    except Exception as e:
        if client:
            try:
                client.close()
            except Exception:
                pass
        return {
            "success": False,
            "error": str(e),
        }
