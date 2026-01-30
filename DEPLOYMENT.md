# Deployment Guide

## Quick Start (Local Development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup authentication (generate password hashes)
cd config
python setup_auth.py
cd ..

# 3. Run server
streamlit run app.py --server.port 8501

# 4. Access at http://localhost:8501
#    Login: admin / admin123
```

---

## Authentication System

### Default Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin (full access) |
| operator | operator123 | User (can upload) |

**สำคัญ: เปลี่ยนรหัสผ่านก่อน deploy บน production!**

### Roles
- **Admin**: จัดการทุกอย่าง + Admin Panel
- **User**: ใช้งานทั้งหมด + อัพโหลดไฟล์ได้
- **Viewer**: ดูข้อมูลได้อย่างเดียว

### Add New User
1. Login as Admin
2. Go to Admin Panel (👤 Admin)
3. Tab "เพิ่มผู้ใช้ใหม่"
4. Fill form and select role

### User Registration
- Users can register at `/Register` page
- Admin can approve/reject at Admin Panel
- Settings can be changed in Admin Panel > Settings

---

## Option 1: Docker (Recommended for Production)

### Create Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Setup auth config directory permissions
RUN chmod -R 755 /app/config

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  bio-dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./database:/app/database
      - ./config:/app/config
    restart: unless-stopped
    environment:
      - TZ=Asia/Bangkok
```

### Build and Run
```bash
# Build
docker-compose build

# Run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## Option 2: Streamlit Cloud (Free)

1. Push code to GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set app path: `bio_dashboard/app.py`
5. Deploy

### Secrets Management
Create secrets in Streamlit Cloud Settings → Secrets:
```toml
[database]
url = "postgresql://postgres.xxx:PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

[cookie]
key = "your-64-char-hex-key-here"
name = "bio_dashboard_auth"
expiry_days = 7
```

**Important**:
- Use Session Pooler URL (port 5432) for IPv4 compatibility
- Never commit credentials to Git
- Rotate credentials periodically

---

## Option 3: Linux Server (VPS/Cloud)

### Prerequisites
- Ubuntu 20.04+ or similar
- Python 3.9+
- Nginx (optional, for reverse proxy)

### Setup Steps

```bash
# 1. Create app directory
sudo mkdir -p /opt/bio-dashboard
cd /opt/bio-dashboard

# 2. Clone/copy your project files
# (upload files or git clone)

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Setup authentication
cd config
python setup_auth.py
cd ..

# 6. Test run
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Setup as Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/bio-dashboard.service
```

```ini
[Unit]
Description=Bio Dashboard Streamlit App
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/bio-dashboard
Environment="PATH=/opt/bio-dashboard/venv/bin"
ExecStart=/opt/bio-dashboard/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Set permissions
sudo chown -R www-data:www-data /opt/bio-dashboard

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable bio-dashboard
sudo systemctl start bio-dashboard
sudo systemctl status bio-dashboard
```

### Nginx Reverse Proxy with SSL

```bash
# Install Nginx and Certbot
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/bio-dashboard
```

```nginx
server {
    listen 80;
    server_name bio.yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }

    # WebSocket support for Streamlit
    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/bio-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Setup SSL (requires domain pointing to server)
sudo certbot --nginx -d bio.yourdomain.com
```

---

## Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#58a6ff"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#161b22"
textColor = "#c9d1d9"
```

---

## Security Checklist

### Before Going Live

- [x] Fix SQL Injection vulnerabilities (v1.3.7)
- [ ] Change default passwords (admin123, operator123)
- [ ] Update cookie key in Streamlit secrets
- [ ] Enable HTTPS (SSL certificate)
- [ ] Setup firewall (allow only 80, 443)
- [ ] Disable registration or enable approval mode
- [ ] Setup automated backups
- [ ] Review user permissions
- [ ] Consider enabling RLS on Supabase tables

### Firewall Setup (UFW)
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### Change Cookie Key
Edit `config/config.yaml`:
```yaml
cookie:
  key: "generate-a-random-32-character-string-here"
```

Generate random key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Database Management

### Backup
```bash
# Manual backup
cp database/bio_data.db database/backup_$(date +%Y%m%d_%H%M%S).db

# Auth config backup
cp config/config.yaml config/config_backup_$(date +%Y%m%d).yaml
```

### Automated Daily Backup (cron)
```bash
# Edit crontab
crontab -e

# Add line (backup at 2 AM daily)
0 2 * * * cp /opt/bio-dashboard/database/bio_data.db /backup/bio_data_$(date +\%Y\%m\%d).db
0 2 * * * cp /opt/bio-dashboard/config/config.yaml /backup/config_$(date +\%Y\%m\%d).yaml
```

### Restore from Backup
```bash
# Stop service
sudo systemctl stop bio-dashboard

# Restore
cp /backup/bio_data_20260128.db /opt/bio-dashboard/database/bio_data.db

# Start service
sudo systemctl start bio-dashboard
```

---

## Troubleshooting

### App won't start
```bash
# Check logs
sudo journalctl -u bio-dashboard -f

# Check if port is in use
sudo lsof -i :8501
sudo kill -9 <PID>
```

### Authentication issues
```bash
# Reset config
cd /opt/bio-dashboard/config
python setup_auth.py

# Restart app
sudo systemctl restart bio-dashboard
```

### Database locked
```bash
# Find and kill zombie processes
ps aux | grep streamlit
sudo kill -9 <PID>

# Restart service
sudo systemctl restart bio-dashboard
```

### Memory issues
```bash
# Check memory
free -h

# Increase swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Monitoring

### Check Status
```bash
# Service status
sudo systemctl status bio-dashboard

# View recent logs
sudo journalctl -u bio-dashboard --since "1 hour ago"

# Check resource usage
htop
```

### Health Check URL
```
http://localhost:8501/_stcore/health
```

---

## Contact & Support

For issues, check:
1. Application logs: `journalctl -u bio-dashboard`
2. Nginx logs: `/var/log/nginx/error.log`
3. Database integrity: `sqlite3 database/bio_data.db "PRAGMA integrity_check;"`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.3.8 | 2026-01-31 | **Feature**: Workload Forecast, Treemap, OB/SC charts, capacity line |
| 1.3.7 | 2026-01-31 | **Security**: SQL Injection fix, credential rotation |
| 1.3.6 | 2026-01-31 | COPY protocol, Card Delivery, Duplicate Check |
| 1.3.5 | 2026-01-31 | Card Delivery upload support |
| 1.3.4 | 2026-01-31 | PostgreSQL COPY protocol optimization |
| 1.3.0 | 2026-01-30 | ECharts integration, Upload 4 tabs |
| 1.1.0 | 2026-01-28 | User authentication system |
| 1.0.0 | 2026-01-28 | Initial release |
