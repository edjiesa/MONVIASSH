# 🚀 Linux SSH Server Monitor (Docker + Web GUI)

Aplikasi monitoring server Linux berbasis **Docker** dan **Web GUI** yang bekerja secara **Agentless** langsung melalui protokol **SSH**. Anda dapat memantau berbagai armada server **CentOS** (CentOS 7, 8, Stream, Rocky, Alma) dan **Ubuntu** (18.04, 20.04, 22.04, 24.04, Debian) tanpa perlu memasang software agen apa pun di server target.

Aplikasi berjalan pada port **`3000`** (`http://localhost:3000`).

---

## ✨ Fitur Utama

- 🔒 **100% Agentless**: Tidak perlu menginstal node-exporter, telegraf, atau agen lain di server target. Cukup sediakan akun SSH standar.
- 🐧 **Kompatibel Lintas Distro**: Mendukung penuh CentOS (RHEL) dan Ubuntu/Debian menggunakan pembacaan standard POSIX `/proc` kernel.
- 📊 **Tampilan Web GUI Modern**:
  - Dark mode dashboard responsif (Tailwind CSS).
  - Indikator status real-time (Online/Offline, Uptime, CPU %, RAM %, Disk %, Network Rx/Tx kbps).
  - Filter cepat berdasarkan Sistem Operasi (CentOS, Ubuntu, Debian, All) dan pencarian teks.
- 📈 **Grafik Interaktif & Detail Partisi**:
  - Riwayat pemakaian CPU & RAM (Chart.js).
  - Rincian partisi penyimpanan (`/`, `/var`, `/home`, dll.).
  - Daftar 10 proses dengan penggunaan CPU & Memori tertinggi (`ps aux`).
- ⚡ **SSH Diagnostic Terminal**:
  - Menjalankan perintah cepat langsung dari browser (misal: `uptime`, `free -h`, `df -h`, `docker ps`, `systemctl status`).
- 🔐 **Kredensial Aman**:
  - Mendukung login via **Password** maupun **SSH Private Key** (RSA, Ed25519, ECDSA, passphrase).
  - Password & SSH Key dienkripsi di disk menggunakan algoritma Fernet AES-128.
- 🐳 **Docker Ready**:
  - Dijalankan cukup dengan `docker compose up -d`.
  - Dilengkapi persistent volume `./data` untuk database SQLite dan secret key.

---

## 🚀 Panduan Menjalankan dengan Docker

### 1. Prasyarat
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) sudah terpasang di komputer/server host Anda.

### 2. Jalankan Container
Buka terminal / PowerShell di direktori proyek ini, lalu jalankan:

```bash
docker compose up -d --build
```

### 3. Akses Dashboard Web
Buka browser dan kunjungi:
```
http://localhost:3000
```
*(Atau ganti `localhost` dengan IP host server Docker Anda jika diakses dari jaringan lain).*

### 4. Menghentikan Container
```bash
docker compose down
```

---

## 💻 Menjalankan Secara Lokal (Tanpa Docker)

Jika Anda ingin menjalankan langsung menggunakan Python lokal:

```bash
# 1. Buat dan aktifkan virtual environment (opsional)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Install dependensi
pip install -r requirements.txt

# 3. Jalankan server FastAPI pada port 3000
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

---

## 🛠️ Konfigurasi Server Target (CentOS & Ubuntu)

Agar server target dapat dipantau via SSH:

### A. Menggunakan SSH Password
1. Pastikan server target mengizinkan autentikasi password pada `/etc/ssh/sshd_config`:
   ```
   PasswordAuthentication yes
   ```
2. Isi form di dashboard: **Host**, **Port (22)**, **Username**, dan **Password**.
3. Klik tombol **"Test SSH Connection"** untuk memastikan koneksi berhasil sebelum disimpan.

### B. Menggunakan SSH Private Key (Direkomendasikan)
1. Salin Public Key Anda ke server target:
   ```bash
   ssh-copy-id username@target-server-ip
   ```
2. Pada modal tambah server di Web GUI, pilih metode **"SSH Private Key"**.
3. Upload file kunci (`id_rsa`, `id_ed25519`, `.pem`) atau tempelkan teks kuncinya ke dalam kotak isian.
4. Jika kunci dilindungi passphrase, masukkan juga passphrase-nya.
5. Klik **"Test SSH Connection"** lalu simpan.

---

## 📁 Struktur Direktori

```text
TOOLSMONVIASSH/
├── Dockerfile              # Definisi container Python 3.11 slim
├── docker-compose.yml      # Orkestrasi Docker (Port 3000 & volume ./data)
├── requirements.txt        # Dependensi Python (FastAPI, Paramiko, dll.)
├── .env.example            # Contoh variabel lingkungan
├── README.md               # Dokumentasi lengkap
├── data/                   # Persistent volume (SQLite DB & secret.key)
└── app/
    ├── __init__.py
    ├── main.py             # Router FastAPI & REST endpoints
    ├── config.py           # Konfigurasi aplikasi & default port 3000
    ├── database.py         # SQLAlchemy ORM setup
    ├── models.py           # Model Server & MetricRecord
    ├── crypto_utils.py     # Enkripsi kredensial SSH (Fernet AES)
    ├── ssh_collector.py    # Modul pengambil metrik via SSH (Agentless)
    ├── scheduler.py        # Background task polling & scheduler
    ├── static/
    │   ├── css/style.css   # Styling kustom & badge distro
    │   └── js/app.js       # Logika dashboard, modal, dan grafik Chart.js
    └── templates/
        └── index.html      # Tampilan Web GUI modern (Dark Mode)
```

---

## 🔧 Pengaturan Lanjutan (`.env` atau `docker-compose.yml`)

| Variabel | Default | Keterangan |
| :--- | :--- | :--- |
| `PORT` | `3000` | Port listening web GUI |
| `DEFAULT_POLL_INTERVAL` | `15` | Interval default polling server (detik) |
| `SSH_TIMEOUT` | `10` | Batas waktu tunggu koneksi SSH (detik) |
| `METRIC_HISTORY_LIMIT` | `60` | Jumlah data riwayat metrik per server di DB |

---

## 🔒 Keamanan
- Kredensial SSH (password dan private key) tidak disimpan dalam bentuk plain-text melainkan dienkripsi secara simetris menggunakan Fernet AES-128.
- Kunci enkripsi disimpan secara lokal di file `data/secret.key` yang terlindungi dalam volume persistent.
