import socket
import uvicorn
from app.config import HOST, PORT

def get_local_ip() -> str:
    """Discovers the local machine IP on the local Wi-Fi / Ethernet network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually establish a connection, just queries routing table
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 68)
    print("🏔️  NH-7 UTTARAKHAND REAL-TIME LANDSLIDE RISK BACKEND")
    print("    Rishikesh ➔ Devprayag ➔ Srinagar ➔ Rudraprayag ➔ Joshimath")
    print("=" * 68)
    print(f"📡 Localhost URL:      http://localhost:{PORT}")
    print(f"📱 Team LAN URL:       http://{local_ip}:{PORT}")
    print(f"📖 Swagger Docs:       http://localhost:{PORT}/docs")
    print(f"🗺️  Interactive UI:     http://localhost:{PORT}/")
    print(f"📝 Rotating Log File:  logs/backend.log")
    print("=" * 68)
    print(f"Share http://{local_ip}:{PORT} with your mobile and web teammates!")
    print("=" * 68)

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info"
    )
