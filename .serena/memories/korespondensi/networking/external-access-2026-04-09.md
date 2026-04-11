# Progress: External LAN Access for Korespondensi Server (2026-04-09)

## Objective
Ensure `/home/aseps/MCP/korespondensi-server` can be accessed from other local-network devices, including dynamic IP change scenarios.

## What Was Changed
1. `src/main.py`
- Web host/port made configurable via environment variables.
- Uses:
  - `WEB_HOST` (default `0.0.0.0`)
  - `WEB_PORT` (default `8082`)

2. `.env.example`
- Added/standardized:
  - `WEB_HOST=0.0.0.0`
  - `WEB_PORT=8082`

3. `README.md`
- Updated default web routes to port `8082`.
- Added LAN access note and usage examples.
- Added doctor mode docs:
  - `./run.sh doctor`
  - `./run.sh web --doctor`

4. `run.sh`
- Added robust mode handling (`set -euo pipefail`).
- Added `doctor` mode to check:
  - IPv4 addresses
  - local endpoint `127.0.0.1:$WEB_PORT`
  - listening socket on `$WEB_PORT`
  - optional Windows health checker invocation via `powershell.exe` when available.

5. Added script `scripts/windows_network_health.ps1`
- Outputs:
  - active Windows network profile(s)
  - active LAN IPv4 candidates
  - localhost port test result
  - client URL candidates `http://<IP>:<PORT>`
  - basic firewall-rule hints

6. `install_services.sh`
- Comment updated to reflect korespondensi server port `8082` (not `8081`).

## Networking Findings / Decisions
- Linux-side app binds correctly to `0.0.0.0:8082` and responds with HTTP 200.
- `ufw` is not installed/used on this host.
- Main issue was Windows/WSL networking path confusion and placeholder usage.
- Working setup confirmed after:
  - removing unneeded `portproxy` entries,
  - testing from Windows `http://localhost:8082` (HTTP 200),
  - then confirming external access from another PC.

## Operational Notes (Important)
- Environment appears to behave like WSL with mirrored-style behavior (WSL and Windows sharing practical LAN-reachable path), so hardcoded `portproxy` is not always needed and can cause confusion.
- For recurring DHCP renew/IP change, use `./run.sh doctor` to print fresh candidates.

## Known Good Access Pattern
- Local check: `http://localhost:8082`
- External client check: `http://<current-Windows-LAN-IPv4>:8082`

## User Confirmation
- User reported: access from another PC is now successful.
