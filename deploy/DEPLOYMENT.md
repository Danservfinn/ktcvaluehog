# Dynasty Edge Deployment Guide

## Architecture Overview

```
┌─────────────────────┐     ┌──────────────────────┐
│   Streamlit Cloud   │────▶│   Railway (Neo4j)    │
│   (Free - UI/API)   │     │   ($5-10/mo - Data)  │
└─────────────────────┘     └──────────────────────┘
         │                           │
         │ HTTPS                     │ Bolt
         ▼                           ▼
    [Users/Browser]             [758K Nodes]
                               [193K Relationships]
```

**Cost**: ~$5-10/month (Railway Hobby plan)

---

## Step 1: Export Local Database

Before deploying, export your local Neo4j database to Cypher files.

```bash
# Navigate to project root
cd /Users/kurultai/ktcvaluehog

# Run full export (creates deploy/exports/*.cypher)
python scripts/export_neo4j.py

# Or test with a sample first
python scripts/export_neo4j.py --sample 1000
```

**Output location**: `deploy/exports/`
- `schema.cypher` - Indexes and constraints
- `nodes_*.cypher` - Node creation statements (by label)
- `relationships.cypher` - Relationship creation
- `export_manifest.json` - Export metadata

---

## Step 2: Deploy Neo4j to Railway

### 2a. Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Upgrade to **Hobby plan** ($5/month)

### 2b. Create New Project

1. Click **"New Project"** → **"Empty Project"**
2. Name it: `dynasty-edge-neo4j`

### 2c. Add Neo4j Service

**Option A: Using Railway CLI**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy from Dockerfile
railway up --dockerfile deploy/Dockerfile.neo4j
```

**Option B: GitHub Deployment**

1. Push this repo to GitHub
2. In Railway: **"Add Service"** → **"GitHub Repo"**
3. Select this repository
4. Railway will auto-detect `railway.toml`

### 2d. Configure Volume (Persistent Storage)

1. In Railway dashboard, click your Neo4j service
2. Go to **Settings** → **Volumes**
3. Click **"Add Volume"**
   - Mount path: `/data`
   - Size: 5GB (expandable)

### 2e. Get Connection URL

After deployment:
1. Go to **Settings** → **Networking**
2. Enable **Public Networking** for port 7687 (Bolt)
3. Copy the generated URL (e.g., `dynastyedge-production.up.railway.app`)

---

## Step 3: Import Data to Railway Neo4j

### 3a. Connect to Railway Neo4j

```bash
# Install cypher-shell if needed
brew install cypher-shell

# Connect (replace with your Railway URL)
cypher-shell -a bolt://YOUR_RAILWAY_URL:7687 -u neo4j -p dynastyedge2025
```

### 3b. Import Schema First

```bash
# Run schema creation
cat deploy/exports/schema.cypher | cypher-shell \
  -a bolt://YOUR_RAILWAY_URL:7687 \
  -u neo4j \
  -p dynastyedge2025
```

### 3c. Import Nodes

```bash
# Import each node file (in order)
for f in deploy/exports/nodes_*.cypher; do
  echo "Importing $f..."
  cat "$f" | cypher-shell \
    -a bolt://YOUR_RAILWAY_URL:7687 \
    -u neo4j \
    -p dynastyedge2025
done
```

### 3d. Import Relationships

```bash
# Import relationships last
cat deploy/exports/relationships.cypher | cypher-shell \
  -a bolt://YOUR_RAILWAY_URL:7687 \
  -u neo4j \
  -p dynastyedge2025
```

**Note**: For large imports, consider using Neo4j Browser or APOC load procedures.

---

## Step 4: Deploy Streamlit Dashboard

### 4a. Create requirements.txt

Ensure `requirements.txt` includes all dependencies:

```
streamlit
neo4j
pandas
numpy
plotly
anthropic
requests
python-dotenv
```

### 4b. Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **"New app"**
4. Select:
   - Repository: `your-username/ktcvaluehog`
   - Branch: `main`
   - Main file: `dashboard/app.py`

### 4c. Configure Secrets

1. In Streamlit Cloud, go to your app
2. Click **Settings** → **Secrets**
3. Paste contents from `deploy/secrets.toml.example`:

```toml
# Update with your Railway URL
neo4j_uri = "bolt://YOUR_RAILWAY_URL:7687"
neo4j_user = "neo4j"
neo4j_password = "dynastyedge2025"

ANTHROPIC_API_KEY = "your-key-here"
SLEEPER_LEAGUE_ID = "your-league-id"
```

### 4d. Verify Connection

Your Streamlit app should now connect to Railway Neo4j. Test by:
1. Opening the Streamlit URL
2. Verifying player stats load
3. Testing the AI Assistant (requires ANTHROPIC_API_KEY)

---

## Monitoring & Maintenance

### Railway Dashboard
- Monitor CPU/Memory usage
- Check logs for errors
- Scale up if needed (RAM)

### Database Backup
```bash
# Export periodically for backup
python scripts/export_neo4j.py --output backup_$(date +%Y%m%d)
```

### Updating Data
To update data in production:

1. Update locally first
2. Export changed labels:
   ```bash
   python scripts/export_neo4j.py --label Player KTCSnapshot
   ```
3. Import to Railway

---

## Troubleshooting

### Connection Refused
- Verify Railway service is running
- Check port 7687 is publicly accessible
- Confirm `bolt://` protocol (not `neo4j://`)

### Memory Issues
- Increase Railway plan memory
- Reduce `NEO4J_server_memory_heap_max__size` in Dockerfile
- Consider sharding large queries

### Slow Queries
- Add indexes for frequently queried properties
- Use PROFILE in Neo4j Browser to optimize
- Consider caching in Streamlit

---

## Cost Summary

| Service | Plan | Cost | Resources |
|---------|------|------|-----------|
| Railway | Hobby | $5/month | 8GB RAM, 5GB storage |
| Streamlit Cloud | Free | $0 | 1GB RAM, 3 apps |
| **Total** | | **~$5-10/month** | |

---

## Security Checklist

- [ ] Change default Neo4j password
- [ ] Use environment variables for secrets
- [ ] Enable SSL for Neo4j connections (neo4j+s://)
- [ ] Restrict Railway network access if possible
- [ ] Rotate API keys periodically
