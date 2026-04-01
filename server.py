import asyncio
import websockets
import json
from datetime import datetime

# Bağlı tüm istemcileri tutan set
connected_clients = set()

async def handler(websocket):
    """Her yeni bağlantı için çalışır"""
    client_ip = websocket.remote_address[0]
    print(f"[+] Yeni bağlantı: {client_ip} | Toplam: {len(connected_clients)+1}")
    
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            data = json.loads(message)
            print(f"[MSG] {client_ip}: {data}")
            
            # Gelen mesajı tüm bağlı istemcilere ilet (broadcast)
            response = {
                "from": client_ip,
                "data": data,
                "time": datetime.now().strftime("%H:%M:%S")
            }
            
            websockets.broadcast(connected_clients, json.dumps(response))
    
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] Bağlantı kesildi: {client_ip}")
    
    finally:
        connected_clients.discard(websocket)
        print(f"[i] Kalan bağlantı: {len(connected_clients)}")

async def main():
    HOST = "0.0.0.0"   # Tüm ağ arayüzlerini dinle
    PORT = 8765

    print(f"WebSocket sunucusu başlatılıyor...")
    print(f"Adres : ws://{HOST}:{PORT}")
    print(f"LAN IP: Kendi IP adresinle bağlanın")
    print(f"Bekleniyor...\n")

    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # Sonsuza kadar çalış

if __name__ == "__main__":
    asyncio.run(main())