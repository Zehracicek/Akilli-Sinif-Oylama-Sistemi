import asyncio
import websockets
import json
import socket
import threading
import http.server
import socketserver
import webbrowser
from datetime import datetime

# ================================================================
# AKILLI SINIF OYLAMA SISTEMI - MERKEZ SUNUCU v4.0 (QUIZ MODE)
# ================================================================
# YENİ ÖZELLİKLER:
#  - Test modu: hoca soruları önceden hazırlar, sırayla otomatik gönderilir
#  - Puan sistemi: doğru cevap 1000 puan + hız bonusu (maks 500)
#  - Sıralama tablosu: her soru sonunda ve testin sonunda
#  - Süre dolunca boş sayılıp otomatik sonraki soruya geçilir
#  - Test bitince tüm ekrana sıralama yayınlanır
# ================================================================

connected_clients = set()
client_info = {}          # ws -> {isim, rol, ip, baglanti_zamani}
puan_tablosu = {}         # isim -> toplam_puan
cevap_baslama_zamani = {} # soru_id -> datetime (soru başladığında)

aktif_soru = None
cevaplar = {}             # soru_id -> {isim: {cevap, zaman, puan}}
soru_arsivi = []
soru_sayaci = 0
zamanlayici_gorev = None
ogretmen_ismi_global = ""
sonuc_paylasilan = set()

# TEST (QUIZ) MODU STATE
test_sorulari = []
test_aktif = False
test_soru_index = 0
test_bitti = False

MAX_PUAN = 1000
HIZ_BONUS_MAX = 500


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


def siralama_hesapla():
    liste = []
    for isim, puan in puan_tablosu.items():
        liste.append({"isim": isim, "puan": puan})
    liste.sort(key=lambda x: x["puan"], reverse=True)
    for i, item in enumerate(liste):
        item["sira"] = i + 1
    return liste


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


def herkese_broadcast(mesaj_dict):
    if connected_clients:
        websockets.broadcast(connected_clients, json.dumps(mesaj_dict))


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
    for ws, bilgi in client_info.items():
        if bilgi.get("rol") == "ogretmen" and ws in connected_clients:
            return True
    return False


def arsive_ekle(soru_id):
    global aktif_soru
    if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
        return
    for a in soru_arsivi:
        if a.get("soru_id") == soru_id:
            return
    ist = istatistik_hesapla(soru_id)
    soru_arsivi.append({
        "soru_id": soru_id,
        "soru": aktif_soru.get("soru", ""),
        "soru_tipi": aktif_soru.get("soru_tipi", ""),
        "secenekler": aktif_soru.get("secenekler", []),
        "dogru_cevap": aktif_soru.get("dogru_cevap", ""),
        "gizli_oylama": aktif_soru.get("gizli_oylama", False),
        "istatistik": ist,
        "cevaplar": cevaplar.get(soru_id, {}),
        "zaman": aktif_soru.get("zaman", "")
    })


def puan_hesapla_fn(dogru_cevap, verilen_cevap, soru_id, toplam_sure):
    if not dogru_cevap:
        return 0
    if not verilen_cevap:
        return 0
    if verilen_cevap.strip().upper() != dogru_cevap.strip().upper():
        return 0
    base = MAX_PUAN
    if toplam_sure > 0 and soru_id in cevap_baslama_zamani:
        gecen = (datetime.now() - cevap_baslama_zamani[soru_id]).total_seconds()
        kalan = max(0, toplam_sure - gecen)
        hiz_bonus = int(HIZ_BONUS_MAX * (kalan / toplam_sure))
    else:
        hiz_bonus = 0
    return base + hiz_bonus


def sonuc_her_ogrenciye_gonder(soru_id):
    if not aktif_soru:
        return
    dogru = aktif_soru.get("dogru_cevap", "")
    ist = istatistik_hesapla(soru_id)
    siralama = siralama_hesapla()

    for ws, bilgi in client_info.items():
        if bilgi.get("rol") == "ogrenci" and ws in connected_clients:
            isim = bilgi["isim"]
            entry = cevaplar.get(soru_id, {}).get(isim, {})
            kendi_cevabi = entry.get("cevap", "")
            kazanilan_puan = entry.get("puan", 0)
            dogru_mu = (kendi_cevabi.strip().upper() == dogru.strip().upper()) if (dogru and kendi_cevabi) else None
            kendi_siram = next((s["sira"] for s in siralama if s["isim"] == isim), None)

            sonuc = {
                "tip": "sonuc",
                "soru_id": soru_id,
                "dogru_cevap": dogru,
                "kendi_cevap": kendi_cevabi,
                "dogru_mu": dogru_mu,
                "kazanilan_puan": kazanilan_puan,
                "toplam_puan": puan_tablosu.get(isim, 0),
                "kendi_siram": kendi_siram,
                "siralama": siralama[:5],
                "istatistik": ist,
                "test_aktif": test_aktif,
                "kalan_soru": max(0, len(test_sorulari) - test_soru_index),
                "toplam_soru": len(test_sorulari) if test_aktif else 0,
                "soru_index": test_soru_index
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
            herkese_broadcast({
                "tip": "zamanlayici", "soru_id": soru_id, "kalan_sure": kalan - 1
            })

        print(f"[TIMER] Süre doldu! Soru #{soru_id}")
        herkese_broadcast({
            "tip": "sure_doldu", "soru_id": soru_id, "mesaj": "Süre doldu!"
        })

        if aktif_soru and aktif_soru.get("soru_id") == soru_id:
            aktif_soru["kilitli"] = True

        ist = istatistik_hesapla(soru_id)
        ogretmenlere_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
        arsive_ekle(soru_id)
        sonuc_her_ogrenciye_gonder(soru_id)
        sonuc_paylasilan.add(soru_id)

        ogretmenlere_broadcast({
            "tip": "siralama_guncelleme",
            "siralama": siralama_hesapla()
        })

        if test_aktif:
            await asyncio.sleep(4)
            await test_sonraki_soru_gonder()

    except asyncio.CancelledError:
        pass


async def test_sonraki_soru_gonder():
    global test_soru_index, test_aktif, test_bitti, aktif_soru, soru_sayaci, zamanlayici_gorev

    if test_soru_index >= len(test_sorulari):
        test_aktif = False
        test_bitti = True
        siralama = siralama_hesapla()
        print(f"\n[TEST] Tamamlandı! {len(siralama)} öğrenci")

        herkese_broadcast({
            "tip": "test_bitti",
            "siralama": siralama,
            "toplam_soru": len(test_sorulari),
            "mesaj": "Test tamamlandı! 🎉"
        })
        return

    soru_data = test_sorulari[test_soru_index]
    test_soru_index += 1

    soru_sayaci += 1
    soru_id = soru_sayaci
    zaman = datetime.now().strftime("%H:%M:%S")
    cevap_baslama_zamani[soru_id] = datetime.now()

    if zamanlayici_gorev and not zamanlayici_gorev.done():
        zamanlayici_gorev.cancel()

    soru_paketi = {
        "tip": "soru",
        "soru_id": soru_id,
        "soru": soru_data.get("soru", ""),
        "secenekler": soru_data.get("secenekler", []),
        "soru_tipi": soru_data.get("soru_tipi", "coktan_secmeli"),
        "gizli_oylama": soru_data.get("gizli_oylama", False),
        "sure": soru_data.get("sure", 20),
        "dogru_cevap": soru_data.get("dogru_cevap", ""),
        "zaman": zaman, "kilitli": False,
        "soru_no": test_soru_index,
        "toplam_soru": len(test_sorulari)
    }

    aktif_soru = soru_paketi
    cevaplar[soru_id] = {}
    sonuc_paylasilan.discard(soru_id)

    ogrenci_sayisi = len([
        ws for ws, b in client_info.items()
        if b.get("rol") == "ogrenci" and ws in connected_clients
    ])

    print(f"\n[TEST {test_soru_index}/{len(test_sorulari)}] '{soru_paketi['soru'][:50]}' -> {ogrenci_sayisi} öğrenci")

    ogrenci_paketi = {k: v for k, v in soru_paketi.items() if k != "dogru_cevap"}
    ogrencilere_broadcast(ogrenci_paketi)

    ogretmenlere_broadcast({
        "tip": "soru_onay",
        "soru_id": soru_id,
        "ogrenci_sayisi": ogrenci_sayisi,
        "soru_no": test_soru_index,
        "toplam_soru": len(test_sorulari)
    })

    if soru_paketi["sure"] > 0:
        zamanlayici_gorev = asyncio.create_task(
            zamanlayici_baslat(soru_paketi["sure"], soru_id)
        )


async def handler(websocket):
    global aktif_soru, soru_sayaci, zamanlayici_gorev, ogretmen_ismi_global
    global test_sorulari, test_aktif, test_soru_index, test_bitti, puan_tablosu

    client_ip = websocket.remote_address[0]
    connected_clients.add(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)

            # ── KİMLİK ────────────────────────────────────────────
            if "rol" in data and "isim" in data and websocket not in client_info:
                isim = data["isim"]
                rol = data["rol"]
                zaman = datetime.now().strftime("%H:%M:%S")

                if rol == "ogretmen" and bagli_ogretmen_var_mi():
                    await websocket.send(json.dumps({
                        "durum": "hata",
                        "mesaj": "Zaten bir öğretmen bağlı!"
                    }))
                    continue

                client_info[websocket] = {
                    "isim": isim, "rol": rol,
                    "ip": client_ip, "baglanti_zamani": zaman
                }

                if rol == "ogrenci":
                    puan_tablosu.setdefault(isim, 0)

                print(f"[+] {isim} ({rol}) | {client_ip}")

                if rol == "ogretmen":
                    ogretmen_ismi_global = isim

                await websocket.send(json.dumps({
                    "durum": "basarili", "mesaj": f"Hoş geldiniz, {isim}!", "rol": rol
                }))

                diger = connected_clients - {websocket}
                websockets.broadcast(diger, json.dumps({
                    "tip": "giris", "isim": isim, "rol": rol, "zaman": zaman
                }))

                ogretmenlere_broadcast({
                    "tip": "kullanici_listesi",
                    "kullanicilar": kullanici_durum_bilgisi(),
                    "toplam": len(connected_clients),
                    "siralama": siralama_hesapla()
                })

                if rol == "ogrenci" and ogretmen_ismi_global:
                    await websocket.send(json.dumps({
                        "tip": "ogretmen_bilgi", "ogretmen_ismi": ogretmen_ismi_global
                    }))

                if rol == "ogrenci" and aktif_soru and not aktif_soru.get("kilitli"):
                    ogrenci_paketi = {k: v for k, v in aktif_soru.items() if k != "dogru_cevap"}
                    await websocket.send(json.dumps(ogrenci_paketi))

                if rol == "ogrenci" and test_bitti:
                    await websocket.send(json.dumps({
                        "tip": "test_bitti",
                        "siralama": siralama_hesapla(),
                        "toplam_soru": len(test_sorulari),
                        "mesaj": "Test tamamlandı! 🎉"
                    }))

                continue

            # ── TEST HAZIRLA ───────────────────────────────────────
            elif data.get("tip") == "test_hazirla":
                test_sorulari = data.get("sorular", [])
                test_aktif = False
                test_soru_index = 0
                test_bitti = False
                for ws2, bilgi2 in client_info.items():
                    if bilgi2.get("rol") == "ogrenci":
                        puan_tablosu[bilgi2["isim"]] = 0

                print(f"[TEST] {len(test_sorulari)} soru hazırlandı.")
                ogretmenlere_broadcast({
                    "tip": "test_hazir",
                    "soru_sayisi": len(test_sorulari),
                    "mesaj": f"{len(test_sorulari)} soru yüklendi!"
                })
                ogrencilere_broadcast({
                    "tip": "test_hazirlaniyor",
                    "toplam_soru": len(test_sorulari),
                    "mesaj": "Öğretmen testi hazırlıyor, bekleyin..."
                })

            # ── TEST BAŞLAT ────────────────────────────────────────
            elif data.get("tip") == "test_baslat":
                if not test_sorulari:
                    ogretmenlere_broadcast({"tip": "uyari", "mesaj": "Önce soruları kaydedin!"})
                    continue

                test_aktif = True
                test_soru_index = 0
                test_bitti = False
                for ws2, bilgi2 in client_info.items():
                    if bilgi2.get("rol") == "ogrenci":
                        puan_tablosu[bilgi2["isim"]] = 0
                puan_tablosu.clear()
                for ws2, bilgi2 in client_info.items():
                    if bilgi2.get("rol") == "ogrenci":
                        puan_tablosu[bilgi2["isim"]] = 0

                print(f"[TEST] Başlatıldı! {len(test_sorulari)} soru")
                ogrencilere_broadcast({
                    "tip": "test_basladi",
                    "toplam_soru": len(test_sorulari),
                    "mesaj": "Test başlıyor! 🚀"
                })
                await asyncio.sleep(2)
                await test_sonraki_soru_gonder()

            # ── TEKİL SORU (anlık, test dışı) ─────────────────────
            elif data.get("tip") == "soru":
                if aktif_soru and not aktif_soru.get("kilitli"):
                    aktif_soru["kilitli"] = True
                    arsive_ekle(aktif_soru.get("soru_id"))

                soru_sayaci += 1
                soru_id = soru_sayaci
                zaman = datetime.now().strftime("%H:%M:%S")
                cevap_baslama_zamani[soru_id] = datetime.now()

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
                    "zaman": zaman, "kilitli": False,
                    "soru_no": 1, "toplam_soru": 1
                }
                aktif_soru = soru_paketi
                cevaplar[soru_id] = {}

                ogrenci_sayisi = len([
                    ws for ws, b in client_info.items()
                    if b.get("rol") == "ogrenci" and ws in connected_clients
                ])
                print(f"[SORU #{soru_id}] {ogrenci_sayisi} öğrenciye gönderildi")

                ogrenci_paketi = {k: v for k, v in soru_paketi.items() if k != "dogru_cevap"}
                ogrencilere_broadcast(ogrenci_paketi)
                ogretmenlere_broadcast({
                    "tip": "soru_onay", "soru_id": soru_id,
                    "ogrenci_sayisi": ogrenci_sayisi, "soru_no": 1, "toplam_soru": 1
                })

                if soru_paketi["sure"] > 0:
                    zamanlayici_gorev = asyncio.create_task(
                        zamanlayici_baslat(soru_paketi["sure"], soru_id)
                    )

            # ── ÖĞRENCİ CEVAP ─────────────────────────────────────
            elif data.get("tip") == "cevap":
                soru_id = data.get("soru_id")
                ogrenci_ismi = client_info.get(websocket, {}).get("isim", "Anonim")
                cevap = data.get("cevap", "")

                if not aktif_soru:
                    continue
                if aktif_soru.get("kilitli"):
                    await websocket.send(json.dumps({"tip": "uyari", "mesaj": "Soru kilitli."}))
                    continue

                if soru_id and soru_id in cevaplar:
                    ilk_mi = ogrenci_ismi not in cevaplar[soru_id]
                    sure = aktif_soru.get("sure", 0)
                    dogru = aktif_soru.get("dogru_cevap", "")
                    kazanilan = puan_hesapla_fn(dogru, cevap, soru_id, sure)

                    if not ilk_mi:
                        # Cevap değiştirdi: eski puanı geri al
                        eski_puan = cevaplar[soru_id][ogrenci_ismi].get("puan", 0)
                        puan_tablosu[ogrenci_ismi] = max(0, puan_tablosu.get(ogrenci_ismi, 0) - eski_puan)

                    cevaplar[soru_id][ogrenci_ismi] = {
                        "cevap": cevap,
                        "zaman": datetime.now().strftime("%H:%M:%S"),
                        "puan": kazanilan
                    }
                    puan_tablosu[ogrenci_ismi] = puan_tablosu.get(ogrenci_ismi, 0) + kazanilan

                    toplam_ogrenci = len([
                        ws for ws, b in client_info.items()
                        if b.get("rol") == "ogrenci" and ws in connected_clients
                    ])
                    cevaplayan = len(cevaplar[soru_id])
                    dogru_mu = (cevap.strip().upper() == dogru.strip().upper()) if dogru else None

                    print(f"   [{ogrenci_ismi}] {cevap} | +{kazanilan}puan ({cevaplayan}/{toplam_ogrenci})")

                    await websocket.send(json.dumps({
                        "tip": "cevap_onay", "mesaj": "Cevabın gönderildi.", "soru_id": soru_id
                    }))

                    ist = istatistik_hesapla(soru_id)
                    ogretmenlere_broadcast({
                        "tip": "canli_cevap", "soru_id": soru_id,
                        "isim": ogrenci_ismi if not aktif_soru.get("gizli_oylama") else "Anonim",
                        "cevap": cevap, "dogru_mu": dogru_mu,
                        "soru_tipi": aktif_soru.get("soru_tipi", ""),
                        "gizli": aktif_soru.get("gizli_oylama", False),
                        "istatistik": ist, "cevaplayan": cevaplayan,
                        "toplam_ogrenci": toplam_ogrenci,
                        "tum_cevaplar": cevaplar[soru_id],
                        "siralama": siralama_hesapla()
                    })

                    if cevaplayan >= toplam_ogrenci and toplam_ogrenci > 0:
                        ogretmenlere_broadcast({
                            "tip": "tum_cevaplar_tamam", "soru_id": soru_id, "istatistik": ist
                        })

            # ── KİLİTLE ───────────────────────────────────────────
            elif data.get("tip") == "kilitle":
                soru_id = data.get("soru_id")
                if aktif_soru and aktif_soru.get("soru_id") == soru_id:
                    aktif_soru["kilitli"] = True
                    if zamanlayici_gorev and not zamanlayici_gorev.done():
                        zamanlayici_gorev.cancel()

                    herkese_broadcast({"tip": "sure_doldu", "soru_id": soru_id, "mesaj": "Kilitlendi."})
                    ist = istatistik_hesapla(soru_id)
                    ogretmenlere_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
                    arsive_ekle(soru_id)
                    sonuc_her_ogrenciye_gonder(soru_id)
                    sonuc_paylasilan.add(soru_id)
                    ogretmenlere_broadcast({"tip": "siralama_guncelleme", "siralama": siralama_hesapla()})

                    if test_aktif:
                        await asyncio.sleep(4)
                        await test_sonraki_soru_gonder()

            # ── ARŞİV ─────────────────────────────────────────────
            elif data.get("tip") == "arsiv_talep":
                await websocket.send(json.dumps({"tip": "arsiv", "sorular": soru_arsivi}))

            # ── GEÇMİŞ ────────────────────────────────────────────
            elif data.get("tip") == "gecmis_talep":
                ogrenci_ismi = client_info.get(websocket, {}).get("isim", "")
                gecmis = []
                for arsiv in soru_arsivi:
                    entry = arsiv.get("cevaplar", {}).get(ogrenci_ismi, None)
                    dogru = arsiv.get("dogru_cevap", "")
                    kc = entry.get("cevap", "") if entry else ""
                    puan = entry.get("puan", 0) if entry else 0
                    gecmis.append({
                        "soru_id": arsiv["soru_id"], "soru": arsiv["soru"],
                        "dogru_cevap": dogru, "kendi_cevabi": kc, "puan": puan,
                        "dogru_mu": (kc.strip().upper() == dogru.strip().upper()) if dogru and kc else None,
                        "zaman": arsiv.get("zaman", "")
                    })
                await websocket.send(json.dumps({
                    "tip": "gecmis", "sorular": gecmis,
                    "toplam_puan": puan_tablosu.get(ogrenci_ismi, 0)
                }))

            elif data.get("tip") == "siralama_talep":
                await websocket.send(json.dumps({
                    "tip": "siralama", "siralama": siralama_hesapla()
                }))

            elif data.get("tip") == "ping":
                await websocket.send(json.dumps({"tip": "pong"}))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        bilgi = client_info.pop(websocket, None)
        connected_clients.discard(websocket)
        isim_yaz = bilgi["isim"] if bilgi else "Kimliksiz"
        rol_yaz = bilgi["rol"].capitalize() if bilgi else "?"
        zaman = datetime.now().strftime("%H:%M:%S")
        print(f"[-] {isim_yaz} ({rol_yaz}) ayrıldı | Kalan: {len(connected_clients)}")

        if bilgi:
            if bilgi["rol"] == "ogretmen":
                ogretmen_ismi_global = ""
            websockets.broadcast(connected_clients, json.dumps({
                "tip": "cikis", "isim": isim_yaz, "rol": bilgi["rol"], "zaman": zaman
            }))
            ogretmenlere_broadcast({
                "tip": "kullanici_listesi",
                "kullanicilar": kullanici_durum_bilgisi(),
                "toplam": len(connected_clients)
            })


def start_http_server(yerel_ip):
    PORT = 9090

    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    try:
        with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), SilentHandler) as httpd:
            print(f"  Web Arayüzü     : http://{yerel_ip}:{PORT}/index.html")
            print(f"  Öğrenci QR Link : http://{yerel_ip}:{PORT}/ogrenci.html")
            print("=" * 55)
            httpd.serve_forever()
    except Exception as e:
        print(f"  Web sunucusu başlatılamadı (Port {PORT} meşgul): {e}")


async def main():
    HOST = "0.0.0.0"
    PORT = 8765
    yerel_ip = ip_adresimi_bul()
    print("=" * 55)
    print("  AKILLI SINIF - SUNUCU v4.0 (QUIZ + PUANLAMA)")
    print("=" * 55)
    print(f"  WebSocket  : ws://{yerel_ip}:{PORT}")
    print(f"  Başlangıç  : {datetime.now().strftime('%H:%M:%S')}")

    http_thread = threading.Thread(target=start_http_server, args=(yerel_ip,), daemon=True)
    http_thread.start()

    print("  Bağlantılar bekleniyor...\n")
    try:
        webbrowser.open(f"http://{yerel_ip}:9090/index.html")
    except:
        pass

    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
