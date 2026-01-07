# Gluesync Whisperer Docker Image

This Docker image packages the **Gluesync Whisperer** module, a MOLO17 component that orchestrates controlled insert, update, and delete workloads across heterogeneous databases. It pairs a FastAPI backend with a React frontend to let you configure "pillow fight" jobs, observe execution metrics, and stress-test database integrations from a single containerized runtime.

> 📘 **Official documentation**: https://docs.molo17.com/gluesync/v2.1/gs-modules/whisperer.html

---

## Image Contents

| Component | Description |
|-----------|-------------|
| Backend API | FastAPI service exposing REST endpoints for connections, table configs, PillowFight jobs, and SQL execution |
| Frontend UI | Vite/React single-page app served through the same container for connection and job management |
| JDBC Drivers | Pre-bundled drivers for MSSQL, MariaDB/MySQL, PostgreSQL, Oracle, and AS400/DB2 (JT400) to ensure JDBC-only connectivity |
| SQLite Storage | Embedded metadata database persisted to `/app/data` by default |

The container is multi-arch capable (linux/amd64 and linux/arm64) when built with Buildx or the supplied `build-multiarch.sh` script.

---

## Quick Start

```bash
# 1. Pull or build the image
# docker pull registry.example.com/gluesync-whisperer:latest
# or build locally
docker build -t gluesync-whisperer .

# 2. Run the container
mkdir -p data logs

docker run -d \
  --name whisperer \
  -p 8000:8000 \
  -p 5173:5173 \
  -v "$PWD/data:/app/data" \
  -v "$PWD/logs:/app/logs" \
  -e PORT=8000 \
  gluesync-whisperer:latest

# 3. Access services
# Frontend: http://localhost:5173
# Backend API / Swagger: http://localhost:8000/docs
```

> When running in production you can expose only `8000` and serve the frontend via a reverse proxy. Port `5173` is mainly useful during development builds.

---

## Configuration

All configuration is performed through environment variables passed to the container. Common settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_URL` | `sqlite:///./data/whisperer.db` | Metadata database used by the module (SQLite file stored under `/app/data`). |
| `PORT` | `8000` | Backend HTTP port (UI is served through the same port in production builds). |
| `HOST` | `0.0.0.0` | Interface the FastAPI server binds to. |
| `DEBUG` | `False` | Enables verbose logging when `true`. |
| `SSL_ENABLED` | `False` | Set to `true` to enable TLS; provide `SSL_CERT_FILE` and `SSL_KEY_FILE`. |
| `DEFAULT_OPERATION_DELAY` | `1.0` | Default interval (seconds) between PillowFight operations when not overridden per table. |
| `DEFAULT_BATCH_SIZE` | `1` | Default batch size for PillowFight operations. |
| `MAX_OPERATIONS` | `0` | Limit of operations per table (0 = unlimited). |
| `INSERT_WEIGHT` / `UPDATE_WEIGHT` / `DELETE_WEIGHT` | `0.33 / 0.33 / 0.34` | Probability weights for each operation type when `operation_type = ALL`. |

### JDBC Drivers

Ship the required vendor JDBC JARs under `/app/jdbc_drivers`. The Docker image already includes the JT400 (AS400), Microsoft SQL Server, MySQL/MariaDB, and PostgreSQL drivers. Mount your own directory if you need additional or updated drivers:

```bash
-v /path/to/jars:/app/jdbc_drivers
```

---

## Volumes & Persistence

| Mount | Purpose |
|-------|---------|
| `/app/data` | Stores the internal SQLite metadata DB (`whisperer.db`) and any cached schema data. |
| `/app/logs` | Container log files, useful when shipping logs to external systems. |
| `/app/jdbc_drivers` (optional) | Override/add JDBC drivers. |

Persisting `/app/data` ensures job history, connection metadata, and PillowFight stats survive container restarts.

---

## Networking & Ports

| Port | Description |
|------|-------------|
| `8000/tcp` | FastAPI backend + production SPA hosting + OpenAPI/Swagger docs. |
| `5173/tcp` | Development React dev server (only needed if building/running the frontend in dev mode). |

Behind a reverse proxy you can terminate TLS and only expose `8000`.

---

## Usage Flow

1. **Start the container** and open the frontend (default credentials are not required; access is open unless you add your own authentication layer).
2. **Create database connections** for each target system (MSSQL, PostgreSQL, MariaDB, Oracle, AS400, etc.). All connections are executed through JDBC.
3. **Configure tables** specifying schema, operation type, cadence, batch size, and optional cascade-delete behavior.
4. **Launch PillowFight jobs** via the UI or API to simulate load. Monitor inserts/updates/deletes per table with warning/error counters.
5. **Inspect logs & metrics** through the UI or by tailing `/app/logs/whisperer.log` from the mounted volume.

The REST API is fully documented at `http://<host>:8000/docs`, enabling automation or CI-driven load scenarios.

---

## Health & Monitoring

- The container logs structured messages through Python’s logging module; mount `/app/logs` or use `docker logs`.
- Use `GET /api/v1/pillow-fight/jobs` to observe active jobs and per-table stats (warning/error counts, operation totals, etc.).
- Add your own readiness/liveness probes via `docker-compose.yml`/Kubernetes using the `/health` endpoint (FastAPI default or add-on).

---

## Security Guidelines

- Rotate JDBC credentials frequently and avoid embedding them in images; inject via secrets or environment variables.
- Run the container behind an HTTPS reverse proxy or enable TLS with `SSL_ENABLED=true`.
- Restrict access to the PillowFight UI/REST API via network policies or an authenticating proxy, as the module can modify data on connected databases.

---

## License

Gluesync Whisperer is **dual-licensed**:

1. **GNU General Public License (GPL) v3** — free to use, modify, and distribute under GPL v3 terms. See `LICENSE-GPL` or <http://www.gnu.org/licenses/gpl-3.0.html>.
2. **MOLO17 Commercial License** — contact [info@molo17.com](mailto:info@molo17.com) for proprietary deployments that require warranty/support and do not wish to open-source derivative work.

Using the Docker image constitutes acceptance of one of the licenses above. Copyright © 2025 MOLO17.

---

## Support & Further Reading

- 📘 Official docs: https://docs.molo17.com/gluesync/v2.1/gs-modules/whisperer.html
- 🐞 Report issues or request features through your MOLO17 support channel or the project issue tracker (if available to you).
- 💬 For commercial licensing, SLAs, or professional services, email [info@molo17.com](mailto:info@molo17.com).
