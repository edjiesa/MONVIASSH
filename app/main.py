import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import Server, MetricRecord
from app.crypto_utils import encrypt_secret
from app.ssh_collector import test_ssh_connection, run_remote_command
from app.scheduler import start_scheduler, stop_scheduler, poll_server_by_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("monitor.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and start scheduler
    init_db()
    start_scheduler()
    yield
    # Shutdown: stop scheduler cleanly
    stop_scheduler()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# Setup templates and static assets
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Pydantic Schemas
class ServerCreateSchema(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    auth_type: str = "password"  # "password" or "key"
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    poll_interval: int = 15
    tags: str = ""

class ServerUpdateSchema(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    auth_type: str | None = None
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    poll_interval: int | None = None
    tags: str | None = None
    is_active: bool | None = None

class TestConnectionSchema(BaseModel):
    host: str
    port: int = 22
    username: str
    auth_type: str = "password"
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None

class ExecCommandSchema(BaseModel):
    command: str

# Web GUI Endpoint
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "port": settings.PORT
        }
    )

# API: Overview Statistics
@app.get("/api/stats/overview")
async def get_overview_stats(db: Session = Depends(get_db)):
    servers = db.query(Server).all()
    total = len(servers)
    online = sum(1 for s in servers if s.last_status == "online")
    offline = sum(1 for s in servers if s.last_status in ("offline", "error"))
    unknown = total - online - offline

    latest_cpu = []
    latest_ram = []
    for s in servers:
        if s.metrics and s.last_status == "online":
            latest_cpu.append(s.metrics[0].cpu_percent)
            latest_ram.append(s.metrics[0].ram_percent)

    avg_cpu = round(sum(latest_cpu) / len(latest_cpu), 1) if latest_cpu else 0.0
    avg_ram = round(sum(latest_ram) / len(latest_ram), 1) if latest_ram else 0.0

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "unknown": unknown,
        "avg_cpu": avg_cpu,
        "avg_ram": avg_ram
    }

# API: List Servers
@app.get("/api/servers")
async def list_servers(db: Session = Depends(get_db)):
    servers = db.query(Server).all()
    return [s.to_dict(include_latest_metric=True) for s in servers]

# API: Create Server
@app.post("/api/servers")
async def create_server(data: ServerCreateSchema, db: Session = Depends(get_db)):
    server = Server(
        name=data.name.strip(),
        host=data.host.strip(),
        port=data.port,
        username=data.username.strip(),
        auth_type=data.auth_type,
        password_encrypted=encrypt_secret(data.password) if data.password else None,
        private_key_encrypted=encrypt_secret(data.private_key) if data.private_key else None,
        key_passphrase_encrypted=encrypt_secret(data.passphrase) if data.passphrase else None,
        poll_interval=data.poll_interval,
        tags=data.tags.strip(),
        is_active=True
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    # Trigger immediate first poll in background
    await poll_server_by_id(server.id)
    db.refresh(server)

    return server.to_dict()

# API: Get Server by ID
@app.get("/api/servers/{server_id}")
async def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server.to_dict(include_latest_metric=True)

# API: Update Server
@app.put("/api/servers/{server_id}")
async def update_server(server_id: int, data: ServerUpdateSchema, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if data.name is not None:
        server.name = data.name.strip()
    if data.host is not None:
        server.host = data.host.strip()
    if data.port is not None:
        server.port = data.port
    if data.username is not None:
        server.username = data.username.strip()
    if data.auth_type is not None:
        server.auth_type = data.auth_type
    if data.password is not None and data.password != "":
        server.password_encrypted = encrypt_secret(data.password)
    if data.private_key is not None and data.private_key != "":
        server.private_key_encrypted = encrypt_secret(data.private_key)
    if data.passphrase is not None:
        server.key_passphrase_encrypted = encrypt_secret(data.passphrase)
    if data.poll_interval is not None:
        server.poll_interval = data.poll_interval
    if data.tags is not None:
        server.tags = data.tags.strip()
    if data.is_active is not None:
        server.is_active = data.is_active

    db.commit()
    db.refresh(server)
    return server.to_dict()

# API: Delete Server
@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(server)
    db.commit()
    return {"message": "Server deleted successfully"}

# API: Immediate Poll Trigger
@app.post("/api/servers/{server_id}/poll")
async def trigger_poll(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    res = await poll_server_by_id(server_id)
    db.refresh(server)
    return {"result": res, "server": server.to_dict()}

# API: Historical Metrics for Charts
@app.get("/api/servers/{server_id}/metrics")
async def get_server_metrics(server_id: int, limit: int = 50, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    records = db.query(MetricRecord)\
                .filter(MetricRecord.server_id == server_id)\
                .order_by(MetricRecord.timestamp.asc())\
                .limit(limit)\
                .all()
    return [r.to_dict() for r in records]

# API: Test Connection
@app.post("/api/servers/test")
async def test_connection(data: TestConnectionSchema):
    res = test_ssh_connection(
        host=data.host,
        port=data.port,
        username=data.username,
        auth_type=data.auth_type,
        password=data.password,
        private_key=data.private_key,
        passphrase=data.passphrase
    )
    return res

# API: Remote Command Execution / Terminal tool
@app.post("/api/servers/{server_id}/exec")
async def exec_server_command(server_id: int, data: ExecCommandSchema, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    cmd = data.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    res = run_remote_command(server, cmd)
    return res
