# ===========================================
# TRADING SYSTEM PRODUCTION PROCFILE
# Nama file: admin_api_server.py
# ===========================================

# 1. Initialize database (run once on deploy)
release: python scripts/init_database.py

# 2. Main Admin API (web service - port 5000)
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --threads 2 admin_api_server:app

# 3. Trading Socket Server (background worker)
worker: python server.py

# 4. Customer API (additional worker)
customer_api: python customer_api.py