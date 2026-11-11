import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models import Server, MetricRecord
from app.ssh_collector import collect_server_metrics

logger = logging.getLogger("monitor.scheduler")

# Memory cache for delta calculations (rx/tx bandwidth)
_prev_metrics_cache: dict[int, dict] = {}
_scheduler_running = False
_scheduler_task = None

def _process_server_metrics(db: Session, server: Server) -> dict:
    """Collect and persist metrics for a single server."""
    prev = _prev_metrics_cache.get(server.id)
    metric_data = collect_server_metrics(server, prev)

    if metric_data.get("success"):
        server.last_status = "online"
        server.last_error = None
        server.last_seen = datetime.now(timezone.utc)

        if metric_data.get("os_name"):
            server.os_name = metric_data["os_name"]
        if metric_data.get("hostname"):
            server.hostname = metric_data["hostname"]
        if metric_data.get("cpu_cores"):
            server.cpu_cores = metric_data["cpu_cores"]
        if metric_data.get("cpu_model"):
            server.cpu_model = metric_data["cpu_model"]
        if metric_data.get("ram_total_mb"):
            server.total_ram_mb = metric_data["ram_total_mb"]
        if metric_data.get("disk_total_gb"):
            server.total_disk_gb = metric_data["disk_total_gb"]
        if metric_data.get("uptime_str"):
            server.uptime_str = metric_data["uptime_str"]

        # Cache network metrics for delta rate computation
        _prev_metrics_cache[server.id] = {
            "total_rx_bytes": metric_data.get("total_rx_bytes", 0),
            "total_tx_bytes": metric_data.get("total_tx_bytes", 0),
            "timestamp": time.time()
        }

        # Store detailed arrays in JSON
        raw_extra = {
            "partitions": metric_data.get("partitions", []),
            "processes": metric_data.get("processes", [])
        }

        new_metric = MetricRecord(
            server_id=server.id,
            timestamp=datetime.now(timezone.utc),
            cpu_percent=metric_data.get("cpu_percent", 0.0),
            ram_used_mb=metric_data.get("ram_used_mb", 0.0),
            ram_total_mb=metric_data.get("ram_total_mb", 0.0),
            ram_percent=metric_data.get("ram_percent", 0.0),
            swap_used_mb=metric_data.get("swap_used_mb", 0.0),
            swap_total_mb=metric_data.get("swap_total_mb", 0.0),
            swap_percent=metric_data.get("swap_percent", 0.0),
            disk_used_gb=metric_data.get("disk_used_gb", 0.0),
            disk_total_gb=metric_data.get("disk_total_gb", 0.0),
            disk_percent=metric_data.get("disk_percent", 0.0),
            load_1m=metric_data.get("load_1m", 0.0),
            load_5m=metric_data.get("load_5m", 0.0),
            load_15m=metric_data.get("load_15m", 0.0),
            net_rx_rate_kbps=metric_data.get("net_rx_rate_kbps", 0.0),
            net_tx_rate_kbps=metric_data.get("net_tx_rate_kbps", 0.0),
            raw_data_json=json.dumps(raw_extra)
        )
        db.add(new_metric)
        db.commit()

        # Trim old records beyond limit
        history_limit = settings.METRIC_HISTORY_LIMIT
        subq = db.query(MetricRecord.id)\
                 .filter(MetricRecord.server_id == server.id)\
                 .order_by(MetricRecord.timestamp.desc())\
                 .offset(history_limit)\
                 .all()
        if subq:
            ids_to_del = [row[0] for row in subq]
            db.query(MetricRecord).filter(MetricRecord.id.in_(ids_to_del)).delete(synchronize_session=False)
            db.commit()

        return {"success": True, "server_id": server.id, "status": "online"}
    else:
        server.last_status = "offline"
        server.last_error = metric_data.get("error", "Unknown SSH error")
        db.commit()
        return {"success": False, "server_id": server.id, "status": "offline", "error": server.last_error}

async def poll_server_by_id(server_id: int) -> dict:
    """Manually trigger metric poll for a specific server in background thread."""
    loop = asyncio.get_running_loop()
    def _task():
        db = SessionLocal()
        try:
            server = db.query(Server).filter(Server.id == server_id).first()
            if not server:
                return {"success": False, "error": "Server not found"}
            return _process_server_metrics(db, server)
        finally:
            db.close()

    return await loop.run_in_executor(None, _task)

async def _scheduler_loop():
    """Continuous async loop that polls servers according to their intervals."""
    logger.info("Background SSH monitoring scheduler started.")
    last_polled: dict[int, float] = {}

    while _scheduler_running:
        try:
            db = SessionLocal()
            try:
                active_servers = db.query(Server).filter(Server.is_active == True).all()
                now = time.time()
                tasks = []
                for s in active_servers:
                    interval = max(5, s.poll_interval or settings.DEFAULT_POLL_INTERVAL)
                    last_time = last_polled.get(s.id, 0.0)
                    if (now - last_time) >= interval:
                        last_polled[s.id] = now
                        tasks.append(poll_server_by_id(s.id))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")

        await asyncio.sleep(2)

def start_scheduler():
    global _scheduler_running, _scheduler_task
    if not _scheduler_running:
        _scheduler_running = True
        _scheduler_task = asyncio.create_task(_scheduler_loop())

def stop_scheduler():
    global _scheduler_running, _scheduler_task
    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
