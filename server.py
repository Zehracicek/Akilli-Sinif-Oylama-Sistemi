import asyncio
import websockets
import json
import socket
import threading
import http.server
import socketserver
import webbrowser
import os
from datetime import datetime

# ===============================================================
# AKILLI SINIF OYLAMA SISTEMI - MERKEZ SUNUCU (v3.0 LMS)
# ===============================================================

connected_clients = set()
client_info = {}
aktif_soru = None
cevaplar = {}
soru_arsivi = []
soru_sayaci = 0
zamanlayici_gorev = None
ogretmen_ismi_global = ""
sonuc_paylasilan = set()  # Sonucu zaten paylasilmis soru ID'leri


def ip_adresimi_bul():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def istatistik_hesapla(soru_id):
    if soru_id not in cevaplar:
        return {}
    yanit_listesi = cevaplar[soru_id]
    toplam = len(yanit_listesi)
    if toplam == 0:
        return {}
    sayim = {}
    for isim, cevap_data in yanit_listesi.items():
        c = cevap_data.get("cevap", "?")
        sayim[c] = sayim.get(c, 0) + 1
    oranlar = {}
    for sik, adet in sayim.items():
        oranlar[sik] = {"adet": adet, "yuzde": round((adet / toplam) * 100, 1)}
    return {"toplam_cevap": toplam, "dagilim": oranlar}


def ogretmenlere_broadcast(mesaj_dict):
    ogretmenler = {
        ws for ws, bilgi in client_info.items()
        if bilgi.get("rol") == "ogretmen" and ws in connected_clients
    }
    if ogretmenler:
        websockets.broadcast(ogretmenler, json.dumps(mesaj_dict))


def ogrencilere_broadcast(mesaj_dict):
    ogrenciler = {
        ws for ws, bilgi in client_info.items()
        if bilgi.get("rol") == "ogrenci" and ws in connected_clients
    }
    if ogrenciler:
        websockets.broadcast(ogrenciler, json.dumps(mesaj_dict))


def kullanici_durum_bilgisi():
    kullanicilar = []
    for ws, bilgi in client_info.items():
        kullanicilar.append({
            "isim": bilgi["isim"], "rol": bilgi["rol"],
            "ip": bilgi.get("ip", "?"),
            "baglanti_zamani": bilgi.get("baglanti_zamani", "?"),
            "durum": "bagli" if ws in connected_clients else "kopuk"
        })
    return kullanicilar


def bagli_ogretmen_var_mi():
    """Zaten bagli bir ogretmen var mi kontrol et."""
    for ws, bilgi in client_info.items():
        if bilgi.get("rol") == "ogretmen" and ws in connected_clients:
            return True
    return False


def arsive_ekle(soru_id):
    """Aktif soruyu arsive ekler."""
    global aktif_soru
    if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
        return
    # Zaten arsivde mi kontrol et
    for a in soru_arsivi:
        if a.get("soru_id") == soru_id:
            return
    ist = istatistik_hesapla(soru_id)
    arsiv_kaydi = {
        "soru_id": soru_id,
        "soru": aktif_soru.get("soru", ""),
        "soru_tipi": aktif_soru.get("soru_tipi", ""),
        "secenekler": aktif_soru.get("secenekler", []),
        "dogru_cevap": aktif_soru.get("dogru_cevap", ""),
        "gizli_oylama": aktif_soru.get("gizli_oylama", False),
        "istatistik": ist,
        "cevaplar": cevaplar.get(soru_id, {}),
        "zaman": aktif_soru.get("zaman", "")
    }
    soru_arsivi.append(arsiv_kaydi)


def sonuc_her_ogrenciye_gonder(soru_id):
    """Her ogrenciye kendi dogru/yanlis durumunu gonderir."""
    if not aktif_soru:
        return
    dogru = aktif_soru.get("dogru_cevap", "")
    ist = istatistik_hesapla(soru_id)
    for ws, bilgi in client_info.items():
        if bilgi.get("rol") == "ogrenci" and ws in connected_clients:
            isim = bilgi["isim"]
            kendi_cevabi = cevaplar.get(soru_id, {}).get(isim, {}).get("cevap", "")
            sonuc = {
                "tip": "sonuc",
                "soru_id": soru_id,
                "dogru_cevap": dogru,
                "kendi_cevap": kendi_cevabi,
                "dogru_mu": (kendi_cevabi.strip().upper() == dogru.strip().upper()) if dogru else None,
                "istatistik": ist
            }
            try:
                asyncio.ensure_future(ws.send(json.dumps(sonuc)))
            except Exception:
                pass


async def zamanlayici_baslat(sure_saniye, soru_id):
    global aktif_soru
    try:
        for kalan in range(sure_saniye, 0, -1):
            await asyncio.sleep(1)
            zamanlayici_paketi = {
                "tip": "zamanlayici", "soru_id": soru_id, "kalan_sure": kalan - 1
            }
            websockets.broadcast(connected_clients, json.dumps(zamanlayici_paketi))

        print(f"[TIMER] Sure doldu! Soru #{soru_id} kilitlendi.")
        kilit_paketi = {
            "tip": "sure_doldu", "soru_id": soru_id,
            "mesaj": "Sure doldu! Cevaplama kilitlendi."
        }
        websockets.broadcast(connected_clients, json.dumps(kilit_paketi))

        if aktif_soru and aktif_soru.get("soru_id") == soru_id:
            aktif_soru["kilitli"] = True

        ist = istatistik_hesapla(soru_id)
        ogretmenlere_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
        arsive_ekle(soru_id)
        # Sonuclari otomatik paylas
        sonuc_her_ogrenciye_gonder(soru_id)
        sonuc_paylasilan.add(soru_id)

    except asyncio.CancelledError:
        pass


async def handler(websocket):
    global aktif_soru, soru_sayaci, zamanlayici_gorev, ogretmen_ismi_global

    client_ip = websocket.remote_address[0]
    connected_clients.add(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)

            # --- KIMLIK DOGRULAMA ---
            if "rol" in data and "isim" in data and websocket not in client_info:
                isim = data["isim"]
                rol = data["rol"]
                zaman = datetime.now().strftime("%H:%M:%S")

                # Madde 13: Sadece 1 ogretmen
                if rol == "ogretmen" and bagli_ogretmen_var_mi():
                    await websocket.send(json.dumps({
                        "durum": "hata",
                        "mesaj": "Zaten bir ogretmen bagli! Ayni anda sadece 1 ogretmen giris yapabilir."
                    }))
                    continue

                client_info[websocket] = {
                    "isim": isim, "rol": rol,
                    "ip": client_ip, "baglanti_zamani": zaman
                }

                print(f"\n{'='*50}")
                print(f"[{zaman}] [+] BAGLANDI: {isim} ({rol.capitalize()})")
                print(f"           IP      : {client_ip}")
                print(f"           Toplam  : {len(connected_clients)} kisi bagli")
                print(f"{'='*50}\n")

                if rol == "ogretmen":
                    ogretmen_ismi_global = isim

                await websocket.send(json.dumps({
                    "durum": "basarili",
                    "mesaj": f"Hos geldiniz, {isim}!",
                    "rol": rol
                }))

                giris_bildirimi = {
                    "tip": "giris", "isim": isim, "rol": rol, "zaman": zaman
                }
                diger_istemciler = connected_clients - {websocket}
                websockets.broadcast(diger_istemciler, json.dumps(giris_bildirimi))

                ogretmenlere_broadcast({
                    "tip": "kullanici_listesi",
                    "kullanicilar": kullanici_durum_bilgisi(),
                    "toplam": len(connected_clients)
                })

                # Madde 14: Ogrenciye ogretmen adini gonder
                if rol == "ogrenci" and ogretmen_ismi_global:
                    await websocket.send(json.dumps({
                        "tip": "ogretmen_bilgi",
                        "ogretmen_ismi": ogretmen_ismi_global
                    }))

                # Yeni ogrenciye aktif soruyu gonder (kilitli degilse)
                if rol == "ogrenci" and aktif_soru and not aktif_soru.get("kilitli"):
                    ogrenci_paketi = {k: v for k, v in aktif_soru.items() if k != "dogru_cevap"}
                    await websocket.send(json.dumps(ogrenci_paketi))

                # Madde 12: Yeniden baglanan ogretmene eski arsiv gonderilMEZ
                # (arsiv sadece o oturumdaki sorulari gosterir)

                continue

            # --- SORU GONDERME ---
            if data.get("tip") == "soru":
                # Onceki soruyu arsivle (kilitli degilse)
                if aktif_soru and not aktif_soru.get("kilitli"):
                    aktif_soru["kilitli"] = True
                    arsive_ekle(aktif_soru.get("soru_id"))

                soru_sayaci += 1
                soru_id = soru_sayaci
                zaman = datetime.now().strftime("%H:%M:%S")

                if zamanlayici_gorev and not zamanlayici_gorev.done():
                    zamanlayici_gorev.cancel()

                soru_paketi = {
                    "tip": "soru", "soru_id": soru_id,
                    "soru": data.get("soru", ""),
                    "secenekler": data.get("secenekler", []),
                    "soru_tipi": data.get("soru_tipi", "coktan_secmeli"),
                    "gizli_oylama": data.get("gizli_oylama", False),
                    "sure": data.get("sure", 0),
                    "dogru_cevap": data.get("dogru_cevap", ""),
                    "zaman": zaman, "kilitli": False
                }

                aktif_soru = soru_paketi
                cevaplar[soru_id] = {}

                ogrenci_sayisi = len([
                    ws for ws, b in client_info.items()
                    if b.get("rol") == "ogrenci" and ws in connected_clients
                ])

                print(f"\n[SORU #{soru_id}] Soru gonderildi -> {ogrenci_sayisi} ogrenciye")
                print(f"       Soru: {soru_paketi['soru']}")

                ogrenci_paketi = {k: v for k, v in soru_paketi.items() if k != "dogru_cevap"}
                ogrencilere_broadcast(ogrenci_paketi)

                ogretmenlere_broadcast({
                    "tip": "soru_onay", "soru_id": soru_id,
                    "mesaj": f"Soru #{soru_id} gonderildi.",
                    "ogrenci_sayisi": ogrenci_sayisi
                })

                if soru_paketi["sure"] > 0:
                    zamanlayici_gorev = asyncio.create_task(
                        zamanlayici_baslat(soru_paketi["sure"], soru_id)
                    )

            # --- OGRENCI CEVAP ---
            elif data.get("tip") == "cevap":
                soru_id = data.get("soru_id")
                ogrenci_ismi = client_info.get(websocket, {}).get("isim", "Anonim")
                cevap = data.get("cevap", "")

                if aktif_soru and aktif_soru.get("kilitli"):
                    await websocket.send(json.dumps({
                        "tip": "uyari",
                        "mesaj": "Soru kilitli. Cevap kabul edilemez."
                    }))
                    continue

                if soru_id and soru_id in cevaplar:
                    # Madde 2: Cevap guncellemeye izin ver
                    ilk_mi = ogrenci_ismi not in cevaplar[soru_id]
                    cevaplar[soru_id][ogrenci_ismi] = {
                        "cevap": cevap,
                        "zaman": datetime.now().strftime("%H:%M:%S")
                    }

                    toplam_ogrenci = len([
                        ws for ws, b in client_info.items()
                        if b.get("rol") == "ogrenci" and ws in connected_clients
                    ])
                    cevaplayan = len(cevaplar[soru_id])

                    eylem = "cevap verdi" if ilk_mi else "cevabini degistirdi"
                    print(f"   [CEVAP] {ogrenci_ismi} {eylem}: {cevap} ({cevaplayan}/{toplam_ogrenci})")

                    # Madde 3: Ogrenci cevabi gonderince sadece 'gonderildi' yazsin
                    await websocket.send(json.dumps({
                        "tip": "cevap_onay",
                        "mesaj": "Cevabınız gönderildi.",
                        "soru_id": soru_id
                    }))

                    # Ogretmene canli guncelleme
                    ist = istatistik_hesapla(soru_id)
                    dogru = aktif_soru.get("dogru_cevap", "") if aktif_soru else ""
                    dogru_mu = (cevap.strip().upper() == dogru.strip().upper()) if dogru else None
                    canli_guncelleme = {
                        "tip": "canli_cevap", "soru_id": soru_id,
                        "isim": ogrenci_ismi if not (aktif_soru and aktif_soru.get("gizli_oylama")) else "Anonim",
                        "cevap": cevap,
                        "dogru_mu": dogru_mu,
                        "soru_tipi": aktif_soru.get("soru_tipi", "") if aktif_soru else "",
                        "gizli": aktif_soru.get("gizli_oylama", False) if aktif_soru else False,
                        "istatistik": ist,
                        "cevaplayan": cevaplayan,
                        "toplam_ogrenci": toplam_ogrenci,
                        "tum_cevaplar": cevaplar[soru_id]
                    }
                    ogretmenlere_broadcast(canli_guncelleme)

                    if cevaplayan >= toplam_ogrenci and toplam_ogrenci > 0:
                        print(f"   [OK] Tum ogrenciler cevap verdi!")
                        ogretmenlere_broadcast({
                            "tip": "tum_cevaplar_tamam",
                            "soru_id": soru_id, "istatistik": ist
                        })

            # --- KILITLE ---
            elif data.get("tip") == "kilitle":
                soru_id = data.get("soru_id")
                if aktif_soru and aktif_soru.get("soru_id") == soru_id:
                    aktif_soru["kilitli"] = True
                    if zamanlayici_gorev and not zamanlayici_gorev.done():
                        zamanlayici_gorev.cancel()

                    kilit_paketi = {
                        "tip": "sure_doldu", "soru_id": soru_id,
                        "mesaj": "Soru kilitlendi."
                    }
                    websockets.broadcast(connected_clients, json.dumps(kilit_paketi))

                    ist = istatistik_hesapla(soru_id)
                    ogretmenlere_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
                    arsive_ekle(soru_id)

                    # Sonuclari otomatik paylas
                    sonuc_her_ogrenciye_gonder(soru_id)
                    sonuc_paylasilan.add(soru_id)
                    print(f"   [KILIT] Soru #{soru_id} kilitlendi ve arsive eklendi.")

            # --- ARSIV TALEBI ---
            elif data.get("tip") == "arsiv_talep":
                await websocket.send(json.dumps({
                    "tip": "arsiv", "sorular": soru_arsivi
                }))

            # --- GECMIS TALEBI ---
            elif data.get("tip") == "gecmis_talep":
                ogrenci_ismi = client_info.get(websocket, {}).get("isim", "")
                ogrenci_gecmisi = []
                for arsiv in soru_arsivi:
                    kendi_cevabi = arsiv.get("cevaplar", {}).get(ogrenci_ismi, None)
                    dogru = arsiv.get("dogru_cevap", "")
                    kc = kendi_cevabi.get("cevap", "") if kendi_cevabi else ""
                    ogrenci_gecmisi.append({
                        "soru_id": arsiv["soru_id"],
                        "soru": arsiv["soru"],
                        "dogru_cevap": dogru,
                        "kendi_cevabi": kc,
                        "dogru_mu": (kc.strip().upper() == dogru.strip().upper()) if dogru and kc else None,
                        "zaman": arsiv.get("zaman", "")
                    })
                await websocket.send(json.dumps({
                    "tip": "gecmis", "sorular": ogrenci_gecmisi
                }))

            # --- SONUC PAYLAS ---
            elif data.get("tip") == "sonuc_paylas":
                soru_id = data.get("soru_id")
                # Madde 17: Sadece 1 kere paylasilabilir
                if soru_id in sonuc_paylasilan:
                    ogretmenlere_broadcast({
                        "tip": "uyari",
                        "mesaj": "Bu sorunun sonuclari zaten paylasildi!"
                    })
                    continue
                sonuc_paylasilan.add(soru_id)

                # Kilitli degilse kilitle
                if aktif_soru and aktif_soru.get("soru_id") == soru_id:
                    aktif_soru["kilitli"] = True
                    if zamanlayici_gorev and not zamanlayici_gorev.done():
                        zamanlayici_gorev.cancel()

                arsive_ekle(soru_id)
                sonuc_her_ogrenciye_gonder(soru_id)

                # Ogretmene kilit + arsiv bildirimi
                ist = istatistik_hesapla(soru_id)
                ogretmenlere_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
                ogretmenlere_broadcast({
                    "tip": "sonuc_paylasim_onay", "soru_id": soru_id,
                    "mesaj": "Sonuclar ogrencilerle paylasildi!"
                })

                # Ogrencilere kilit bildirimi
                ogrencilere_broadcast({
                    "tip": "sure_doldu", "soru_id": soru_id,
                    "mesaj": "Soru kilitlendi."
                })

                print(f"   [SONUC] Soru #{soru_id} sonuclari paylasildi.")

            # --- PING/PONG ---
            elif data.get("tip") == "ping":
                await websocket.send(json.dumps({"tip": "pong"}))

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        bilgi = client_info.pop(websocket, None)
        connected_clients.discard(websocket)
        zaman = datetime.now().strftime("%H:%M:%S")
        isim_yaz = bilgi["isim"] if bilgi else "Kimliksiz"
        rol_yaz = bilgi["rol"].capitalize() if bilgi else "?"

        print(f"[-] AYRILDI: {isim_yaz} ({rol_yaz}) | Kalan: {len(connected_clients)}")

        if bilgi:
            if bilgi["rol"] == "ogretmen":
                ogretmen_ismi_global = ""

            cikis_bildirimi = {
                "tip": "cikis", "isim": isim_yaz,
                "rol": bilgi["rol"], "zaman": zaman
            }
            websockets.broadcast(connected_clients, json.dumps(cikis_bildirimi))
            ogretmenlere_broadcast({
                "tip": "kullanici_listesi",
                "kullanicilar": kullanici_durum_bilgisi(),
                "toplam": len(connected_clients)
            })


def start_http_server(yerel_ip):
    PORT = 9090
    Handler = http.server.SimpleHTTPRequestHandler
    try:
        with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
            print(f"  Web Arayüzü     : http://{yerel_ip}:{PORT}/index.html")
            print("=" * 55)
            httpd.serve_forever()
    except Exception as e:
        print(f"  Web sunucusu baslatilamadi (Port {PORT} mesgul olabilir): {e}")

async def main():
    HOST = "0.0.0.0"
    PORT = 8765
    yerel_ip = ip_adresimi_bul()
    print("=" * 55)
    print("  AKILLI SINIF OYLAMA SISTEMI - MERKEZ SUNUCU v3.0")
    print("=" * 55)
    print(f"  Sunucu Adresi   : ws://{yerel_ip}:{PORT}")
    print(f"  Dinleme Adresi  : ws://{HOST}:{PORT}")
    print(f"  Baslangic       : {datetime.now().strftime('%H:%M:%S')}")
    
    http_thread = threading.Thread(target=start_http_server, args=(yerel_ip,), daemon=True)
    http_thread.start()
    
    print("  Istemci baglantilari bekleniyor...\n")
    
    try:
        webbrowser.open(f"http://{yerel_ip}:9090/index.html")
    except:
        pass

    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())