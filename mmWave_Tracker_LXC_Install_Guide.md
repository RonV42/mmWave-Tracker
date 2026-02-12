# mmWave Tracker — Proxmox LXC Installation Guide

**Hubitat + Inovelli Blue mmWave Sensor Visualization**  
*February 2026*

***

## Overview

This guide walks through deploying the [mmWave Tracker](https://github.com/lnjustin/mmWave-Tracker) application as a Proxmox LXC container rather than Docker. The result is a lightweight, transparent Flask-based web UI that visualizes Inovelli Blue mmWave sensor data in real time via the Hubitat MakerAPI — giving you a proper coordinate-based visual editor instead of manually mapping detection zones with numbers and graph paper.

The approach treats the project's Dockerfile as a recipe — each instruction becomes a sequential step inside the LXC. This gives you a more transparent, inspectable system that integrates naturally with your existing Proxmox infrastructure.

***

## Prerequisites

| Component              | Version / Type       | Notes                                   |
|------------------------|----------------------|-----------------------------------------|
| Proxmox VE             | 7.x / 8.x / 9.x      | Running cluster or standalone node      |
| Debian 13 LXC Template | debian-13-standard   | Downloaded via Proxmox template manager |
| Hubitat Elevation      | Any current firmware | On same IoT VLAN as LXC                 |
| MakerAPI App           | Installed on Hubitat | With mmWave device(s) added             |
| Inovelli Blue Switch   | With mmWave module   | Paired and reporting in Hubitat         |
| Network                | IoT VLAN configured  | LXC and Hubitat on same VLAN segment    |

>   **NOTE:** The Inovelli Blue switch must have mmWave target reporting enabled in its Hubitat driver settings.

***

## Step 1: Create the LXC Container

Run the following command on your Proxmox host. Adjust the VMID, IP address, gateway, and bridge to match your IoT VLAN configuration.

```bash
pct create 221 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
  --hostname mmwavetracker \
  --memory 512 \
  --cores 1 \
  --net0 name=eth0,bridge=vmbr2,ip=192.168.x.x/24,gw=192.168.x.1 \
  --storage local-lvm \
  --unprivileged 1 \
  --features nesting=1
```

### Why `nesting=1`?

There is a known bug with recent Debian LXC templates in Proxmox where the native LXC console (`pct console`) does not attach correctly without nesting enabled. The container runs fine without it, but you will get a blank screen or hang when trying to access the console. Enabling nesting fixes this side effect and poses no real security concern for a single-purpose Flask container.

>   **NOTE:** If you already created the container without nesting, run:

>   bash

>   pct set 221 -features nesting=1

>   pct reboot 221

### Start and Enter the Container

```bash
pct start 221
pct enter 221
```

***

## Step 2: Install System Dependencies

Inside the LXC container, update the system and install Python:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip git
```

***

## Step 3: Deploy the Application

Create the application directory and clone the repository:

```bash
mkdir -p /app
cd /app
git clone https://github.com/lnjustin/mmWave-Tracker.git .
```

Install Python dependencies. Debian 13+ enforces PEP 668 which prevents system-wide pip installs by default. Since this is a dedicated single-purpose LXC, using `--break-system-packages` is safe and appropriate:

```bash
pip install --no-cache-dir --break-system-packages --root-user-action=ignore -r requirements.txt
```

>   **NOTE:** You will see a warning about running pip as root. This is expected and safe in a dedicated LXC. The `--root-user-action=ignore` flag suppresses the warning on subsequent runs.

***

## Step 4: Configure Environment Variables

The application reads its configuration from environment variables. It does **not** natively load a `.env` file despite what the GitHub documentation suggests — there is no `python-dotenv` implementation in the codebase. The correct approach is to bake the variables directly into the systemd service (see Step 5).

### Required Variables

| Variable          | Example Value | Description                                        |
|-------------------|---------------|----------------------------------------------------|
| `HUBITAT_HOST`    | `192.168.x.x` | IP address of your Hubitat hub on IoT VLAN         |
| `MAKERAPI_APP_ID` | `1234`        | App ID from Hubitat MakerAPI app settings          |
| `MAKERAPI_TOKEN`  | `your-token`  | Access token from Hubitat MakerAPI app settings    |
| `POLL_HZ`         | 10            | Polling rate in Hz — 10 is heavy on Zigbee network |
| `FLASK_PORT`      | `5000`        | Port Flask will listen on inside the LXC           |

### Finding Your MakerAPI Credentials

1.  Log in to your Hubitat web interface
2.  Navigate to **Apps** and open your MakerAPI instance
3.  The App ID is shown in the URL and in the app settings
4.  Generate or copy your Access Token from the MakerAPI app settings page
5.  Ensure your mmWave device(s) are added to the MakerAPI device list

>   .

***

## Step 5: Create the systemd Service

Create a systemd service so the application starts automatically on boot and restarts automatically if it crashes:

```bash
cat > /etc/systemd/system/mmwave-tracker.service << 'EOF'
[Unit]
Description=Hubitat mmWave Tracker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app
Environment="HUBITAT_HOST=192.168.x.x"
Environment="MAKERAPI_APP_ID=xxxx"
Environment="MAKERAPI_TOKEN=your-token-here"
Environment="POLL_HZ=10"
Environment="FLASK_PORT=5000"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /app/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start the service:

```bash
systemctl daemon-reload
systemctl enable mmwave-tracker
systemctl start mmwave-tracker
systemctl status mmwave-tracker
```

If the service started successfully you will see `Active: active (running)` in the status output.

***

## Step 6: Access the UI

From a browser on your trusted network, navigate to:

```
http://[LXC-IP]:5000
```

You should see the **Hubitat mmWave Live** interface. The status bar at the top will show the connection state and your device name once it connects to Hubitat.

### Expected Status Progression

| Status                                   | Meaning                                           |
|------------------------------------------|---------------------------------------------------|
| `Status: Connecting...`                  | App started, attempting to reach Hubitat MakerAPI |
| `Device: [your device name]`             | Hubitat connection established, device loaded     |
| `No targetInfo / invalid JSON`           | Parameter 107. mmWave Target Info Report not on   |
| `Status: OK` with coordinate dot on grid | Fully operational with live X/Y/Z tracking        |

>   **NOTE:** Firewall rules — the LXC and Hubitat are both on the IoT VLAN so no cross-VLAN rules are needed for their communication. You will need a rule allowing your trusted network to reach the LXC on port 5000 to access the UI from your workstation or browser.

***

## Troubleshooting

### Console shows blank screen or hangs

The `nesting` feature is not enabled. Run:

```bash
pct set 221 -features nesting=1
pct reboot 221
```

### pip install fails with `externally-managed-environment`

You are on Debian 12+ which enforces PEP 668. Add the `--break-system-packages` flag as shown in Step 3. This is safe for dedicated single-purpose LXC containers.

### Status stuck on `Connecting...`

-   Verify `HUBITAT_HOST` IP is correct in the systemd service
-   Confirm Hubitat and the LXC are both on the same IoT VLAN
-   Check that MakerAPI is installed and running on Hubitat
-   Verify the access token is correct

### `No targetInfo / invalid JSON`

-   Open MakerAPI settings on Hubitat
-   Enable parameter 107. mmWave Target Info Report
-   Click **Refresh** in the UI after enabling

### UI loads but Zigbee network is sluggish

The default `POLL_HZ=10` generates significant traffic on the Zigbee network, especially with multiple switches. Reduce to 1 or 2 Hz for normal monitoring and only increase during active tuning sessions:

```bash
nano /etc/systemd/system/mmwave-tracker.service
# Change POLL_HZ=10 to POLL_HZ=2

systemctl daemon-reload
systemctl restart mmwave-tracker
```

### Check service logs

```bash
journalctl -u mmwave-tracker -f
```

***

## Operational Notes

### Polling Rate and Zigbee Impact

The mmWave target reporting at high poll rates (10 Hz) creates substantial traffic on the Zigbee mesh. This is noticeable when multiple switches are reporting simultaneously. The recommended approach is to keep `POLL_HZ` at 1-2 for passive monitoring and increase it temporarily during active zone configuration sessions, then reduce again afterward.

### Backups

The LXC filesystem is backed up by your standard Proxmox backup schedule. There are no external volumes or Docker layers to worry about — everything is in the LXC filesystem. The only configuration that needs protecting is the systemd service file at `/etc/systemd/system/mmwave-tracker.service` which contains your MakerAPI credentials.

### Why LXC Instead of Docker

For a simple single-purpose Flask application like this, LXC offers several advantages over Docker: the filesystem is directly inspectable without image layers, troubleshooting is straightforward with direct SSH or console access, it integrates naturally with Proxmox backup and snapshot workflows, and resource overhead is lower since the container shares the host kernel. The Dockerfile from the original repository served as the build recipe — each instruction was translated into a sequential configuration step inside the LXC.

***

*mmWave Tracker by* [lnjustin](https://github.com/lnjustin/mmWave-Tracker)
