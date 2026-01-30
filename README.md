# Hubitat mmWave Live Viewer

This project is a lightweight **Flask + Socket.IO** web app that connects to your **Hubitat Maker API**, polls a selected device (ex: Inovelli mmWave), and displays:

- Live mmWave target tracking (`targetInfo`)
- Target count (`targetCount`)
- **Occupancy indicator** (derived from `motion`: `active` → occupied, `inactive` → unoccupied)
- **Lux** (from `illuminance` or `lux`)
- Real-time plot + target trail history (Plotly)
- Live target table (X/Y/Z/Doppler)

Runs locally on your network and is easiest to deploy using **Docker Desktop**.

---

## What’s Included

This GitHub repo already contains everything you need:

- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `app.py`
- `templates/index.html`
- `.env` (**edit this for your environment**)

✅ You should only need to edit **`.env`**.

---

## Requirements

- Docker Desktop installed and running (Windows/macOS/Linux)

---

## Install / Run (Docker Desktop)

### 1) Clone the repo

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd <REPO_FOLDER_NAME>
```
### 2) Edit .env
Open the .env file in the repo and update these values:  
HUBITAT_HOST=192.168.1.101  
MAKERAPI_APP_ID=1234  
MAKERAPI_TOKEN=your_token_here  
POLL_HZ=10  

Field meanings  
HUBITAT_HOST = Hubitat hub IP address  
MAKERAPI_APP_ID = Maker API App ID from Hubitat  
MAKERAPI_TOKEN = Maker API access token  
POLL_HZ = polls per second (10 is a good default)  

### 3) Build + Start
From the repo folder:  
docker compose up --build  

This will build the image and start the container.  

### 4) Open the UI
In your browser:  

http://localhost:5000


## Docker Desktop GUI (Optional)
If you prefer using Docker Desktop visually:  
Open Docker Desktop  
Go to Containers  
You should see the running container (ex: hubitat-mmwave-live)  
Click the published port 5000 to open the app  


## Hubitat Maker API Setup
On Hubitat, install/open the Maker API app  
Select the device(s) you want exposed (your mmWave device must be included)  
Copy:  
App ID  
Access Token  

Paste them into .env  