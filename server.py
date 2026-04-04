import asyncio
import websockets
import json
from datetime import datetime

connected_clients = set()
client_info = {}

async def handler(websocket):
    client_ip = websocket.remote_address[0]
    connected_clients.add(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)

            if "rol" in data and "isim" in data and websocket not in client_info:
                client_info[websocket] = {"isim": data["isim"], "rol": data["rol"]}
                isim = data["isim"]
                rol = data["rol"].capitalize()
                zaman = datetime.now().strftime("%H:%M:%S")

                print(f"\n{'='*45}")
                print(f"[{zaman}] ✅ BAĞLANDI  » {isim} ({rol})")
                print(f"           IP      : {client_ip}")
                print(f"           Toplam  : {len(connected_clients)} kişi bağlı")
                print(f"{'='*45}\n")

                await websocket.send(json.dumps({
                    "durum": "basarili",
                    "mesaj": f"Hoş geldiniz, {isim}!"
                }))

                giris_bildirimi = json.dumps({
                    "tip": "giris",
                    "isim": isim,
                    "zaman": zaman
                })
                diger_istemciler = connected_clients - {websocket}
                print(f"[DEBUG] Giriş bildirimi → {len(diger_istemciler)} kişiye gönderiliyor")
                websockets.broadcast(diger_istemciler, giris_bildirimi)

            else:
                response = {
                    "from": client_info.get(websocket, {}).get("isim", client_ip),
                    "data": data,
                    "time": datetime.now().strftime("%H:%M:%S")
                }
                websockets.broadcast(connected_clients, json.dumps(response))

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        bilgi = client_info.pop(websocket, None)
        connected_clients.discard(websocket)
        zaman = datetime.now().strftime("%H:%M:%S")
        isim_yaz = bilgi["isim"] if bilgi else "Kimliksiz"
        rol_yaz = bilgi["rol"].capitalize() if bilgi else "?"
        print(f"[-] AYRILDI: {isim_yaz} ({rol_yaz}) | IP: {client_ip} | Kalan: {len(connected_clients)}")

        if bilgi:
            cikis_bildirimi = json.dumps({
                "tip": "cikis",
                "isim": isim_yaz,
                "zaman": zaman
            })
            print(f"[DEBUG] Çıkış bildirimi → {len(connected_clients)} kişiye gönderiliyor")
            websockets.broadcast(connected_clients, cikis_bildirimi)

async def main():
    HOST = "0.0.0.0"
    PORT = 8765
    print(f"WebSocket sunucusu başlatılıyor → ws://{HOST}:{PORT}\n")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())