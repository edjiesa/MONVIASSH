import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.crypto_utils import decrypt_secret

def utc_now():
    return datetime.now(timezone.utc)

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)
    auth_type = Column(String(20), default="password") # "password" or "key"
    
    password_encrypted = Column(Text, nullable=True)
    private_key_encrypted = Column(Text, nullable=True)
    key_passphrase_encrypted = Column(Text, nullable=True)
    sudo_password_encrypted = Column(Text, nullable=True)

    poll_interval = Column(Integer, default=15)
    tags = Column(String(255), default="")
    is_active = Column(Boolean, default=True)

    # Health & status
    last_status = Column(String(30), default="unknown") # online, offline, error, unknown
    last_error = Column(Text, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # Static / Semi-static hardware & OS info
    os_name = Column(String(150), nullable=True)
    hostname = Column(String(150), nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    cpu_model = Column(String(200), nullable=True)
    total_ram_mb = Column(Float, nullable=True)
    total_disk_gb = Column(Float, nullable=True)
    uptime_str = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    metrics = relationship("MetricRecord", back_populates="server", cascade="all, delete-orphan", order_by="desc(MetricRecord.timestamp)")

    def get_password(self) -> str | None:
        return decrypt_secret(self.password_encrypted)

    def get_private_key(self) -> str | None:
        return decrypt_secret(self.private_key_encrypted)

    def get_passphrase(self) -> str | None:
        return decrypt_secret(self.key_passphrase_encrypted)

    def get_sudo_password(self) -> str | None:
        dec = decrypt_secret(self.sudo_password_encrypted)
        if dec:
            return dec
        return self.get_password()

    def to_dict(self, include_latest_metric: bool = True) -> dict:
        latest_metric = None
        if include_latest_metric and self.metrics:
            latest_metric = self.metrics[0].to_dict()

        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "auth_type": self.auth_type,
            "poll_interval": self.poll_interval,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()] if self.tags else [],
            "is_active": self.is_active,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "os_name": self.os_name,
            "hostname": self.hostname,
            "cpu_cores": self.cpu_cores,
            "cpu_model": self.cpu_model,
            "total_ram_mb": self.total_ram_mb,
            "total_disk_gb": self.total_disk_gb,
            "uptime_str": self.uptime_str,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "latest_metric": latest_metric,
        }

def safe_round(val, decimals=1, default=0.0):
    if val is None:
        return default
    try:
        return round(float(val), decimals)
    except Exception:
        return default

class MetricRecord(Base):
    __tablename__ = "metric_records"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    timestamp = Column(DateTime, default=utc_now, index=True)

    cpu_percent = Column(Float, default=0.0)
    ram_used_mb = Column(Float, default=0.0)
    ram_total_mb = Column(Float, default=0.0)
    ram_percent = Column(Float, default=0.0)
    swap_used_mb = Column(Float, default=0.0)
    swap_total_mb = Column(Float, default=0.0)
    swap_percent = Column(Float, default=0.0)

    disk_used_gb = Column(Float, default=0.0)
    disk_total_gb = Column(Float, default=0.0)
    disk_percent = Column(Float, default=0.0)

    load_1m = Column(Float, default=0.0)
    load_5m = Column(Float, default=0.0)
    load_15m = Column(Float, default=0.0)

    net_rx_rate_kbps = Column(Float, default=0.0)
    net_tx_rate_kbps = Column(Float, default=0.0)

    # Detailed json data (partitions, top processes, network interfaces)
    raw_data_json = Column(Text, nullable=True)

    server = relationship("Server", back_populates="metrics")

    def to_dict(self) -> dict:
        parsed_extra = {}
        if self.raw_data_json:
            try:
                parsed_extra = json.loads(self.raw_data_json)
            except Exception:
                pass

        return {
            "id": self.id,
            "server_id": self.server_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "cpu_percent": safe_round(self.cpu_percent, 1),
            "ram_used_mb": safe_round(self.ram_used_mb, 1),
            "ram_total_mb": safe_round(self.ram_total_mb, 1),
            "ram_percent": safe_round(self.ram_percent, 1),
            "swap_used_mb": safe_round(self.swap_used_mb, 1),
            "swap_total_mb": safe_round(self.swap_total_mb, 1),
            "swap_percent": safe_round(self.swap_percent, 1),
            "disk_used_gb": safe_round(self.disk_used_gb, 1),
            "disk_total_gb": safe_round(self.disk_total_gb, 1),
            "disk_percent": safe_round(self.disk_percent, 1),
            "load_1m": safe_round(self.load_1m, 2),
            "load_5m": safe_round(self.load_5m, 2),
            "load_15m": safe_round(self.load_15m, 2),
            "net_rx_rate_kbps": safe_round(self.net_rx_rate_kbps, 1),
            "net_tx_rate_kbps": safe_round(self.net_tx_rate_kbps, 1),
            "partitions": parsed_extra.get("partitions", []),
            "processes": parsed_extra.get("processes", []),
        }
