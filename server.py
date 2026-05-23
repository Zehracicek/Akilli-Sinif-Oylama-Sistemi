import asyncio
import sys
import random
import websockets
import json
import socket
import threading
import http.server
import socketserver
import webbrowser
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# ================================================================
# AKILLI SINIF OYLAMA SISTEMI - MERKEZ SUNUCU v4.0 (QUIZ MODE)
# ================================================================
# YENİ ÖZELLİKLER:
#  - Test modu: hoca soruları önceden hazırlar, sırayla otomatik gönderilir
#  - Puan sistemi: doğru cevap 1000 puan + hız bonusu (maks 500)
#  - Sıralama tablosu: her soru sonunda ve testin sonunda
#  - Süre dolunca otomatik soru sonu + test modunda sonraki soruya geçiş
#  - Öğretmen "Duraklat": süre/cevap dondur · "Devam": kaldığı yerden sürdür
#  - Test bitince tüm ekrana sıralama yayınlanır
# ================================================================

connected_clients = set()
client_info = {}          # ws -> {isim, rol, ip, baglanti_zamani}
puan_tablosu = {}         # isim -> toplam_puan
streak_tablosu = {}       # isim -> ardışık doğru sayısı
cevap_baslama_zamani = {} # soru_id -> datetime (soru başladığında)
oyun_pin = None           # 6 haneli oyun PIN

aktif_soru = None
cevaplar = {}             # soru_id -> {isim: {cevap, zaman, puan}}
soru_arsivi = []
test_oturum_arsivi = []   # Mevcut test oturumundaki kilitlenmiş sorular (CSV rapor)
soru_sayaci = 0
zamanlayici_gorev = None
sonuc_gecis_gorev = None
ogretmen_ismi_global = ""
sonuc_paylasilan = set()

SONUC_BEKLE_SURE = 3  # Soru sonuç ekranı (sn), ardından otomatik sonraki soru (test modu)
ERKEN_BITIS_BEKLE = 2  # Herkes cevaplayınca kısa bekleme, sonra soru kapanır


def sure_int(deger, default=20):
    try:
        v = int(deger)
    except (TypeError, ValueError):
        return default
    return v if v > 0 else default

# TEST (QUIZ) MODU STATE
test_sorulari = []
test_aktif = False
test_soru_index = 0
test_bitti = False

MAX_PUAN = 1000
HIZ_BONUS_MAX = 500
COMBO_BONUS = {2: 200, 3: 400, 4: 600}  # streak -> bonus


def pin_olustur():
    return str(random.randint(100000, 999999))


def combo_bonus_hesapla(streak):
    if streak >= 4:
        return COMBO_BONUS[4]
    return COMBO_BONUS.get(streak, 0)


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
        liste.append({
            "isim": isim,
            "puan": puan,
            "streak": streak_tablosu.get(isim, 0),
        })
    liste.sort(key=lambda x: x["puan"], reverse=True)
    for i, item in enumerate(liste):
        item["sira"] = i + 1
    return liste


def test_rapor_olustur(siralama):
    return {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ogretmen": ogretmen_ismi_global,
        "sorular": list(test_oturum_arsivi),
        "siralama": siralama,
    }


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


def sunumlara_broadcast(mesaj_dict):
    sunumlar = {
        ws for ws, bilgi in client_info.items()
        if bilgi.get("rol") == "sunum" and ws in connected_clients
    }
    if sunumlar:
        websockets.broadcast(sunumlar, json.dumps(mesaj_dict))


def panel_broadcast(mesaj_dict):
    ogretmenlere_broadcast(mesaj_dict)
    sunumlara_broadcast(mesaj_dict)


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


def client_rol(ws):
    return client_info.get(ws, {}).get("rol")


def kuyruk_ogretmen_payload(sorular):
    """Öğretmen panelindeki sıra listesi ile sunucu test_sorulari'ni birebir eşitlemek için."""
    out = []
    for t in sorular or []:
        out.append({
            "soru": t.get("soru", ""),
            "secenekler": list(t.get("secenekler") or []),
            "soru_tipi": t.get("soru_tipi", "coktan_secmeli"),
            "gizli_oylama": t.get("gizli_oylama", False),
            "sure": int(t.get("sure") or 0) or 20,
            "dogru_cevap": t.get("dogru_cevap", ""),
            "gorsel_url": t.get("gorsel_url", ""),
            "kaynak": t.get("kaynak") or "plan",
        })
    return out


def streak_combo_uygula(soru_id):
    if not aktif_soru:
        return
    dogru = aktif_soru.get("dogru_cevap", "")
    for isim, entry in cevaplar.get(soru_id, {}).items():
        cevap = entry.get("cevap", "")
        dogru_mu = bool(
            dogru and cevap
            and cevap.strip().upper() == dogru.strip().upper()
        )
        if dogru_mu:
            streak_tablosu[isim] = streak_tablosu.get(isim, 0) + 1
            combo = combo_bonus_hesapla(streak_tablosu[isim])
            entry["streak"] = streak_tablosu[isim]
            entry["combo_bonus"] = combo
            if combo > 0:
                entry["puan"] = entry.get("puan", 0) + combo
                puan_tablosu[isim] = puan_tablosu.get(isim, 0) + combo
        else:
            streak_tablosu[isim] = 0
            entry["streak"] = 0
            entry["combo_bonus"] = 0


async def sunum_durum_gonder(ws):
    ogrenciler = [
        k for k in kullanici_durum_bilgisi()
        if k.get("rol") == "ogrenci" and k.get("durum") == "bagli"
    ]
    aktif_ozet = None
    if aktif_soru:
        aktif_ozet = {k: v for k, v in aktif_soru.items() if k != "dogru_cevap"}
        aktif_ozet["kilitli"] = aktif_soru.get("kilitli", False)
        if aktif_soru.get("kilitli"):
            aktif_ozet["dogru_cevap"] = aktif_soru.get("dogru_cevap", "")
    paket = {
        "tip": "sunum_durum",
        "pin": oyun_pin,
        "ogretmen": ogretmen_ismi_global,
        "ogrenci_sayisi": len(ogrenciler),
        "kullanicilar": ogrenciler,
        "test_aktif": test_aktif,
        "test_bitti": test_bitti,
        "toplam_soru": len(test_sorulari),
        "soru_index": test_soru_index,
        "siralama": siralama_hesapla()[:10],
        "aktif_soru": aktif_ozet,
    }
    if aktif_soru and aktif_soru.get("soru_id"):
        sid = aktif_soru["soru_id"]
        paket["cevap_sayisi"] = len(cevaplar.get(sid, {}))
        paket["istatistik"] = istatistik_hesapla(sid)
    await ws.send(json.dumps(paket))


def arsive_ekle(soru_id):
    global aktif_soru, test_oturum_arsivi
    if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
        return
    for a in soru_arsivi:
        if a.get("soru_id") == soru_id:
            return
    ist = istatistik_hesapla(soru_id)
    kayit = {
        "soru_id": soru_id,
        "soru": aktif_soru.get("soru", ""),
        "soru_tipi": aktif_soru.get("soru_tipi", ""),
        "secenekler": aktif_soru.get("secenekler", []),
        "dogru_cevap": aktif_soru.get("dogru_cevap", ""),
        "gorsel_url": aktif_soru.get("gorsel_url", ""),
        "gizli_oylama": aktif_soru.get("gizli_oylama", False),
        "istatistik": ist,
        "cevaplar": dict(cevaplar.get(soru_id, {})),
        "zaman": aktif_soru.get("zaman", "")
    }
    soru_arsivi.append(kayit)
    if test_aktif:
        test_oturum_arsivi.append(kayit)


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


async def sonuc_her_ogrenciye_gonder(soru_id):
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
                "combo_bonus": entry.get("combo_bonus", 0),
                "streak": entry.get("streak", streak_tablosu.get(isim, 0)),
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
                await ws.send(json.dumps(sonuc))
            except Exception:
                pass


def _planla_erken_bitis(soru_id, bekle_sn=ERKEN_BITIS_BEKLE):
    """Aynı soru için tek erken bitiş görevi planla."""
    if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
        return
    if aktif_soru.get("kilitli"):
        return
    gorev = aktif_soru.get("erken_bitis_gorev")
    if gorev and not gorev.done():
        return
    aktif_soru["erken_bitis_gorev"] = asyncio.create_task(_erken_soru_bitir(soru_id, bekle_sn))


async def _erken_soru_bitir(soru_id, bekle_sn=ERKEN_BITIS_BEKLE):
    """Tüm öğrenciler cevapladığında süre bitmeden soruyu kapat."""
    try:
        await asyncio.sleep(bekle_sn)
        if aktif_soru and aktif_soru.get("soru_id") == soru_id and not aktif_soru.get("kilitli"):
            await soru_sonlandir(soru_id, otomatik_gecis=test_aktif)
    except asyncio.CancelledError:
        pass
    finally:
        if aktif_soru and aktif_soru.get("soru_id") == soru_id:
            aktif_soru["erken_bitis_gorev"] = None


async def zamanlayici_baslat(sure_saniye, soru_id):
    global aktif_soru, test_aktif
    try:
        for kalan in range(sure_saniye, 0, -1):
            if aktif_soru and aktif_soru.get("duraklatildi"):
                aktif_soru["kalan_sure"] = kalan
                return
            await asyncio.sleep(1)
            if aktif_soru and aktif_soru.get("soru_id") == soru_id:
                aktif_soru["kalan_sure"] = kalan - 1
            herkese_broadcast({
                "tip": "zamanlayici", "soru_id": soru_id, "kalan_sure": kalan - 1
            })

        if aktif_soru and aktif_soru.get("soru_id") == soru_id and not aktif_soru.get("duraklatildi"):
            print(f"[TIMER] Süre doldu — soru #{soru_id} sonlandırılıyor")
            await soru_sonlandir(soru_id, otomatik_gecis=test_aktif)

    except asyncio.CancelledError:
        pass


async def soru_sonlandir(soru_id, otomatik_gecis=False):
    """Soru bitti: cevapları kilitle, sonuçları yayınla; test modunda kısa süre sonra sonraki soru."""
    global aktif_soru, zamanlayici_gorev, sonuc_gecis_gorev, test_aktif

    if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
        return
    if aktif_soru.get("kilitli"):
        return

    aktif_soru["kilitli"] = True
    aktif_soru["duraklatildi"] = False

    if zamanlayici_gorev and not zamanlayici_gorev.done():
        zamanlayici_gorev.cancel()

    herkese_broadcast({
        "tip": "zaman_bitti",
        "soru_id": soru_id,
        "mesaj": "Süre doldu — cevaplar kilitlendi.",
    })
    herkese_broadcast({
        "tip": "soru_kilitlendi",
        "soru_id": soru_id,
        "mesaj": "Soru sona erdi — sonuçlar paylaşılıyor.",
        "sonuclandi": True,
    })

    streak_combo_uygula(soru_id)
    ist = istatistik_hesapla(soru_id)
    panel_broadcast({"tip": "istatistik", "soru_id": soru_id, "istatistik": ist})
    arsive_ekle(soru_id)
    await sonuc_her_ogrenciye_gonder(soru_id)
    sonuc_paylasilan.add(soru_id)
    siralama = siralama_hesapla()
    panel_broadcast({"tip": "siralama_guncelleme", "siralama": siralama})
    sunumlara_broadcast({
        "tip": "sunum_sonuc",
        "soru_id": soru_id,
        "dogru_cevap": aktif_soru.get("dogru_cevap", ""),
        "istatistik": ist,
        "siralama": siralama[:5],
        "soru_no": aktif_soru.get("soru_no"),
        "toplam_soru": len(test_sorulari) if test_aktif else 0,
        "kalan_soru": max(0, len(test_sorulari) - test_soru_index) if test_aktif else 0,
        "test_aktif": test_aktif,
    })

    if otomatik_gecis and test_aktif:
        if sonuc_gecis_gorev and not sonuc_gecis_gorev.done():
            sonuc_gecis_gorev.cancel()
        sonuc_gecis_gorev = asyncio.create_task(_otomatik_sonraki_soru_bekle())


async def _otomatik_sonraki_soru_bekle():
    global sonuc_gecis_gorev, test_aktif
    try:
        await asyncio.sleep(SONUC_BEKLE_SURE)
        if test_aktif:
            await test_sonraki_soru_gonder()
    except asyncio.CancelledError:
        pass
    finally:
        sonuc_gecis_gorev = None


async def test_sonraki_soru_gonder():
    global test_soru_index, test_aktif, test_bitti, aktif_soru, soru_sayaci, zamanlayici_gorev, sonuc_gecis_gorev

    if sonuc_gecis_gorev and not sonuc_gecis_gorev.done():
        sonuc_gecis_gorev.cancel()
        sonuc_gecis_gorev = None

    if test_soru_index >= len(test_sorulari):
        test_aktif = False
        test_bitti = True
        siralama = siralama_hesapla()
        print(f"\n[TEST] Tamamlandı! {len(siralama)} öğrenci")

        herkese_broadcast({
            "tip": "test_bitti",
            "siralama": siralama,
            "toplam_soru": len(test_sorulari),
            "mesaj": "Test tamamlandı! 🎉",
            "rapor": test_rapor_olustur(siralama),
        })
        return

    soru_data = test_sorulari[test_soru_index]
    test_soru_index += 1

    soru_sayaci += 1
    soru_id = soru_sayaci
    zaman = datetime.now().strftime("%H:%M:%S")
    cevap_baslama_zamani[soru_id] = datetime.now()
    sure_sn = sure_int(soru_data.get("sure", 20))

    if zamanlayici_gorev and not zamanlayici_gorev.done():
        zamanlayici_gorev.cancel()

    soru_paketi = {
        "tip": "soru",
        "soru_id": soru_id,
        "soru": soru_data.get("soru", ""),
        "secenekler": soru_data.get("secenekler", []),
        "soru_tipi": soru_data.get("soru_tipi", "coktan_secmeli"),
        "gizli_oylama": soru_data.get("gizli_oylama", False),
        "sure": sure_sn,
        "dogru_cevap": soru_data.get("dogru_cevap", ""),
        "gorsel_url": soru_data.get("gorsel_url", ""),
        "zaman": zaman, "kilitli": False, "duraklatildi": False,
        "kalan_sure": sure_sn,
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

    panel_broadcast({
        "tip": "soru_onay",
        "soru_id": soru_id,
        "ogrenci_sayisi": ogrenci_sayisi,
        "soru_no": test_soru_index,
        "toplam_soru": len(test_sorulari),
        "test_aktif": True,
        "kuyruk": kuyruk_ogretmen_payload(test_sorulari),
        "soru": soru_paketi.get("soru", ""),
        "secenekler": soru_paketi.get("secenekler", []),
        "soru_tipi": soru_paketi.get("soru_tipi", ""),
        "sure": soru_paketi.get("sure", 0),
        "dogru_cevap": soru_paketi.get("dogru_cevap", ""),
        "gorsel_url": soru_paketi.get("gorsel_url", ""),
        "gizli_oylama": soru_paketi.get("gizli_oylama", False),
    })

    if sure_sn > 0:
        zamanlayici_gorev = asyncio.create_task(
            zamanlayici_baslat(sure_sn, soru_id)
        )
    elif test_aktif:
        _planla_erken_bitis(soru_id, 3)


async def handler(websocket):
    global aktif_soru, soru_sayaci, zamanlayici_gorev, ogretmen_ismi_global, sonuc_gecis_gorev
    global test_sorulari, test_aktif, test_soru_index, test_bitti, puan_tablosu
    global oyun_pin, streak_tablosu, test_oturum_arsivi

    client_ip = websocket.remote_address[0]
    connected_clients.add(websocket)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                continue

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

                if rol == "ogrenci":
                    pin = str(data.get("pin", "")).strip()
                    if oyun_pin and pin != oyun_pin:
                        await websocket.send(json.dumps({
                            "durum": "hata",
                            "mesaj": "Geçersiz PIN! Öğretmenden 6 haneli PIN alın."
                        }))
                        continue

                client_info[websocket] = {
                    "isim": isim, "rol": rol,
                    "ip": client_ip, "baglanti_zamani": zaman
                }

                if rol == "ogrenci":
                    puan_tablosu.setdefault(isim, 0)
                    streak_tablosu.setdefault(isim, 0)

                print(f"[+] {isim} ({rol}) | {client_ip}")

                if rol == "ogretmen":
                    ogretmen_ismi_global = isim
                    oyun_pin = pin_olustur()
                    print(f"[PIN] Yeni oyun PIN: {oyun_pin}")
                    herkese_broadcast({"tip": "pin_guncelle", "pin": oyun_pin})

                basarili = {
                    "durum": "basarili",
                    "mesaj": f"Hoş geldiniz, {isim}!",
                    "rol": rol,
                }
                if oyun_pin:
                    basarili["pin"] = oyun_pin
                await websocket.send(json.dumps(basarili))

                if rol == "sunum":
                    await sunum_durum_gonder(websocket)
                    continue

                diger = connected_clients - {websocket}
                websockets.broadcast(diger, json.dumps({
                    "tip": "giris", "isim": isim, "rol": rol, "zaman": zaman
                }))

                panel_broadcast({
                    "tip": "kullanici_listesi",
                    "kullanicilar": kullanici_durum_bilgisi(),
                    "toplam": len(connected_clients),
                    "siralama": siralama_hesapla(),
                    "pin": oyun_pin,
                })
                sunumlara_broadcast({
                    "tip": "lobby_guncelle",
                    "ogrenci_sayisi": len([
                        k for k in kullanici_durum_bilgisi()
                        if k.get("rol") == "ogrenci" and k.get("durum") == "bagli"
                    ]),
                    "kullanicilar": [
                        k for k in kullanici_durum_bilgisi()
                        if k.get("rol") == "ogrenci"
                    ],
                    "pin": oyun_pin,
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

            elif websocket not in client_info:
                continue

            rol = client_rol(websocket)
            if rol == "sunum":
                if data.get("tip") == "ping":
                    await websocket.send(json.dumps({"tip": "pong"}))
                continue

            # ── TEST HAZIRLA ───────────────────────────────────────
            elif data.get("tip") == "test_hazirla":
                if rol != "ogretmen":
                    continue
                test_sorulari = list(data.get("sorular") or [])
                for i, s in enumerate(test_sorulari):
                    test_sorulari[i] = dict(s)
                    test_sorulari[i]["sure"] = sure_int(s.get("sure", 20))
                test_aktif = False
                test_soru_index = 0
                test_bitti = False
                test_oturum_arsivi = []
                oyun_pin = pin_olustur()
                streak_tablosu.clear()
                for ws2, bilgi2 in client_info.items():
                    if bilgi2.get("rol") == "ogrenci":
                        puan_tablosu[bilgi2["isim"]] = 0
                        streak_tablosu[bilgi2["isim"]] = 0

                print(f"[TEST] {len(test_sorulari)} soru hazırlandı. PIN: {oyun_pin}")
                herkese_broadcast({"tip": "pin_guncelle", "pin": oyun_pin})
                panel_broadcast({
                    "tip": "test_hazir",
                    "soru_sayisi": len(test_sorulari),
                    "mesaj": f"{len(test_sorulari)} soru yüklendi!",
                    "kuyruk": kuyruk_ogretmen_payload(test_sorulari),
                    "pin": oyun_pin,
                })
                ogrencilere_broadcast({
                    "tip": "test_hazirlaniyor",
                    "toplam_soru": len(test_sorulari),
                    "mesaj": "Öğretmen testi hazırlıyor, bekleyin...",
                    "pin": oyun_pin,
                })

            # ── TEST BAŞLAT ────────────────────────────────────────
            elif data.get("tip") == "test_baslat":
                if rol != "ogretmen":
                    continue
                if not test_sorulari:
                    panel_broadcast({"tip": "uyari", "mesaj": "Önce soruları kaydedin!"})
                    continue

                test_aktif = True
                test_soru_index = 0
                test_bitti = False
                test_oturum_arsivi = []
                puan_tablosu.clear()
                streak_tablosu.clear()
                for ws2, bilgi2 in client_info.items():
                    if bilgi2.get("rol") == "ogrenci":
                        puan_tablosu[bilgi2["isim"]] = 0
                        streak_tablosu[bilgi2["isim"]] = 0

                print(f"[TEST] Başlatıldı! {len(test_sorulari)} soru")
                ogrencilere_broadcast({
                    "tip": "test_basladi",
                    "toplam_soru": len(test_sorulari),
                    "mesaj": "Test başlıyor! 🚀"
                })
                await asyncio.sleep(2)
                await test_sonraki_soru_gonder()

            # ── SIRAYA ANLIK SORU (test devam ederken, her zaman listenin sonuna) ──
            elif data.get("tip") == "siraya_soru_ekle":
                if client_rol(websocket) != "ogretmen":
                    continue
                if not test_aktif:
                    await websocket.send(json.dumps({
                        "tip": "uyari",
                        "mesaj": "Sıraya eklemek için test açık olmalı. Önce testi başlatın.",
                    }))
                    continue
                yeni = {
                    "soru": data.get("soru", ""),
                    "secenekler": data.get("secenekler", []),
                    "soru_tipi": data.get("soru_tipi", "coktan_secmeli"),
                    "gizli_oylama": data.get("gizli_oylama", False),
                    "sure": int(data.get("sure") or 0) or 20,
                    "dogru_cevap": data.get("dogru_cevap", ""),
                    "gorsel_url": data.get("gorsel_url", ""),
                    "kaynak": "anlik",
                }
                test_sorulari.append(yeni)
                n = len(test_sorulari)
                print(f"[SIRAYA] siraya_soru_ekle -> sonda. test_soru_index={test_soru_index} len={n}")
                panel_broadcast({
                    "tip": "siraya_soru_eklendi",
                    "kayit": yeni,
                    "toplam_soru": n,
                    "kuyruk": kuyruk_ogretmen_payload(test_sorulari),
                })
                ogrencilere_broadcast({
                    "tip": "test_kuyruk_guncellendi",
                    "toplam_soru": n,
                })

            # ── TEKİL SORU (anlık, test dışı — doğrudan yayın) ─────────────────────
            elif data.get("tip") == "soru":
                if client_rol(websocket) != "ogretmen":
                    continue
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
                    "sure": sure_int(data.get("sure", 0)),
                    "dogru_cevap": data.get("dogru_cevap", ""),
                    "gorsel_url": data.get("gorsel_url", ""),
                    "zaman": zaman, "kilitli": False, "duraklatildi": False,
                    "kalan_sure": sure_int(data.get("sure", 0)),
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
                panel_broadcast({
                    "tip": "soru_onay", "soru_id": soru_id,
                    "ogrenci_sayisi": ogrenci_sayisi, "soru_no": 1, "toplam_soru": 1,
                    "test_aktif": False,
                    "soru": soru_paketi.get("soru", ""),
                    "secenekler": soru_paketi.get("secenekler", []),
                    "soru_tipi": soru_paketi.get("soru_tipi", ""),
                    "sure": soru_paketi.get("sure", 0),
                    "dogru_cevap": soru_paketi.get("dogru_cevap", ""),
                    "gorsel_url": soru_paketi.get("gorsel_url", ""),
                    "gizli_oylama": soru_paketi.get("gizli_oylama", False),
                })

                if soru_paketi["sure"] > 0:
                    zamanlayici_gorev = asyncio.create_task(
                        zamanlayici_baslat(soru_paketi["sure"], soru_id)
                    )
            elif data.get("tip") == "cevap":
                if client_rol(websocket) != "ogrenci":
                    continue
                try:
                    soru_id = int(data.get("soru_id"))
                except (TypeError, ValueError):
                    continue
                ogrenci_ismi = client_info.get(websocket, {}).get("isim", "Anonim")
                cevap = data.get("cevap", "")

                if not aktif_soru:
                    continue
                if aktif_soru.get("kilitli") or aktif_soru.get("duraklatildi"):
                    mesaj = "Soru duraklatıldı." if aktif_soru.get("duraklatildi") else "Soru kilitli."
                    await websocket.send(json.dumps({"tip": "uyari", "mesaj": mesaj}))
                    continue

                if soru_id and soru_id in cevaplar:
                    ilk_mi = ogrenci_ismi not in cevaplar[soru_id]
                    sure = sure_int(aktif_soru.get("sure", 0), 0)
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
                    panel_broadcast({
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
                    sunumlara_broadcast({
                        "tip": "sunum_cevap",
                        "soru_id": soru_id,
                        "cevaplayan": cevaplayan,
                        "toplam_ogrenci": toplam_ogrenci,
                        "istatistik": ist,
                    })

                    if cevaplayan >= toplam_ogrenci and toplam_ogrenci > 0:
                        panel_broadcast({
                            "tip": "tum_cevaplar_tamam", "soru_id": soru_id, "istatistik": ist
                        })
                        if test_aktif and not aktif_soru.get("kilitli"):
                            _planla_erken_bitis(soru_id)

            # ── DURAKLAT (öğretmen — süre/cevap dondur) ─────────────
            elif data.get("tip") == "kilitle":
                if client_rol(websocket) != "ogretmen":
                    continue
                soru_id = data.get("soru_id")
                if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
                    continue
                if aktif_soru.get("kilitli"):
                    await websocket.send(json.dumps({
                        "tip": "uyari",
                        "mesaj": "Soru zaten bitti. Sonraki soruya geçebilirsiniz.",
                    }))
                    continue
                if aktif_soru.get("duraklatildi"):
                    continue

                aktif_soru["duraklatildi"] = True
                if zamanlayici_gorev and not zamanlayici_gorev.done():
                    zamanlayici_gorev.cancel()

                kalan = aktif_soru.get("kalan_sure", 0)
                herkese_broadcast({
                    "tip": "soru_duraklatildi",
                    "soru_id": soru_id,
                    "kalan_sure": kalan,
                    "mesaj": "Öğretmen soruyu duraklattı — cevap süresi durdu.",
                })

            # ── KİLİDİ AÇ / DEVAM (öğretmen) ───────────────────────
            elif data.get("tip") == "kilidi_ac":
                if client_rol(websocket) != "ogretmen":
                    continue
                soru_id = data.get("soru_id")
                if not aktif_soru or aktif_soru.get("soru_id") != soru_id:
                    continue
                if aktif_soru.get("kilitli"):
                    await websocket.send(json.dumps({
                        "tip": "uyari",
                        "mesaj": "Soru sona erdi, devam ettirilemez.",
                    }))
                    continue
                if not aktif_soru.get("duraklatildi"):
                    continue

                aktif_soru["duraklatildi"] = False
                kalan = max(1, int(aktif_soru.get("kalan_sure") or 0))
                aktif_soru["kalan_sure"] = kalan

                if zamanlayici_gorev and not zamanlayici_gorev.done():
                    zamanlayici_gorev.cancel()
                if kalan > 0:
                    zamanlayici_gorev = asyncio.create_task(zamanlayici_baslat(kalan, soru_id))

                herkese_broadcast({
                    "tip": "soru_devam_ediyor",
                    "soru_id": soru_id,
                    "kalan_sure": kalan,
                    "mesaj": "Yarışma devam ediyor!",
                })

            # ── SONRAKİ SORU (manuel — test modu) ──────────────────
            elif data.get("tip") == "sonraki_soru":
                if client_rol(websocket) != "ogretmen":
                    continue
                if test_aktif:
                    if aktif_soru and not aktif_soru.get("kilitli"):
                        await soru_sonlandir(aktif_soru.get("soru_id"), otomatik_gecis=False)
                    await test_sonraki_soru_gonder()

            # ── TESTİ BİTİR (erken) ───────────────────────────────
            elif data.get("tip") == "test_bitir":
                if client_rol(websocket) != "ogretmen":
                    continue
                if sonuc_gecis_gorev and not sonuc_gecis_gorev.done():
                    sonuc_gecis_gorev.cancel()
                if zamanlayici_gorev and not zamanlayici_gorev.done():
                    zamanlayici_gorev.cancel()
                if aktif_soru and not aktif_soru.get("kilitli"):
                    await soru_sonlandir(aktif_soru.get("soru_id"), otomatik_gecis=False)
                test_aktif = False
                test_bitti = True
                siralama = siralama_hesapla()
                print(f"\n[TEST] Öğretmen testi erken bitirdi! {len(siralama)} öğrenci")
                herkese_broadcast({
                    "tip": "test_bitti",
                    "siralama": siralama,
                    "toplam_soru": len(test_sorulari),
                    "mesaj": "Test tamamlandı! 🎉",
                    "rapor": test_rapor_olustur(siralama),
                })

            # ── ARŞİV ─────────────────────────────────────────────
            elif data.get("tip") == "arsiv_talep":
                if client_rol(websocket) != "ogretmen":
                    continue
                await websocket.send(json.dumps({"tip": "arsiv", "sorular": soru_arsivi}))

            # ── GEÇMİŞ ────────────────────────────────────────────
            elif data.get("tip") == "gecmis_talep":
                if client_rol(websocket) != "ogrenci":
                    continue
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
            sunumlara_broadcast({
                "tip": "lobby_guncelle",
                "ogrenci_sayisi": len([
                    k for k in kullanici_durum_bilgisi()
                    if k.get("rol") == "ogrenci" and k.get("durum") == "bagli"
                ]),
                "kullanicilar": [
                    k for k in kullanici_durum_bilgisi()
                    if k.get("rol") == "ogrenci"
                ],
                "pin": oyun_pin,
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

    # config.js oluştur — HTML sayfaları bu dosyadan IP bilgisini alır
    import os
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.js")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(f'const SERVER_IP = "{yerel_ip}";\n')
        f.write(f'const SERVER_HTTP = "http://{yerel_ip}:9090";\n')
        f.write(f'const SERVER_WS = "ws://{yerel_ip}:8765";\n')

    http_thread = threading.Thread(target=start_http_server, args=(yerel_ip,), daemon=True)
    http_thread.start()

    print("  Bağlantılar bekleniyor...\n")
    try:
        webbrowser.open(f"http://{yerel_ip}:9090/index.html")
    except Exception:
        pass

    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
