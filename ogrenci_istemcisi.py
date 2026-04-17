import asyncio
import websockets
import json
import socket

def ip_adresimi_bul():
    """Bilgisayarın yerel ağdaki (LAN) IPv4 adresini otomatik bulur."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

async def ogrenci_baglan():
    # --- PROFESYONEL KARŞILAMA VE VERİ GİRİŞİ ---
    print("\n" + "="*40)
    print("🎓 AKILLI SINIF OYLAMA SİSTEMİ")
    print("👨‍🎓 ÖĞRENCİ İSTEMCİSİ BAŞLATILIYOR...")
    print("="*40)
    
    # İsmi kodun içine yazmak yerine öğrenciden (kullanıcıdan) dinamik olarak alıyoruz
    ogrenci_ismi = input("Lütfen sisteme giriş yapacak öğrencinin adını ve soyadını giriniz: ").strip()
    
    if not ogrenci_ismi:
        ogrenci_ismi = "İsimsiz Öğrenci"

    otomatik_ip = ip_adresimi_bul()
    # Eğer sunucu farklı bir bilgisayardaysa, otomatik IP yerine sunucunun IP'sini girmelisiniz.
    # Aynı bilgisayarda test edildiği varsayılarak kendi IP'sini alıyoruz.
    uri = f"ws://{otomatik_ip}:8765" 
    
    print(f"\n🔍 Sistem IP Adresi: {otomatik_ip}")
    print(f"⏳ Sunucu aranıyor ({uri})...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Sunucu bağlantısı başarılı!\n")

            # Dinamik değişkeni JSON paketinin içine yerleştiriyoruz
            kimlik_bilgisi = {
                "rol": "ogrenci",
                "isim": ogrenci_ismi, 
                "msg": "Bağlantı doğrulama talebi"
            }
            
            await websocket.send(json.dumps(kimlik_bilgisi))
            print(f"📤 Kimlik doğrulama gönderildi (Kullanıcı: {ogrenci_ismi})")

            cevap = await websocket.recv()
            print(f"📥 Sunucu Yanıtı: {cevap}\n")

            print("="*40)
            print("⏳ Sistem hazır. Öğretmenin başlatacağı oylama için bekleniyor...")
            print("="*40)
            
            # Bağlantıyı açık tutma döngüsü
            while True:
                try:
                    # Gelen bir mesaj (örn. oylama başlaması) olursa almak için
                    mesaj = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(mesaj)

                    if data.get("tip") == "soru":
                        print("\n" + "="*40)
                        print("📋 YENİ SORU GELDİ!")
                        print(f"❓ {data['soru']}")
                        for secenek in data.get("secenekler", []):
                            print(f"   {secenek}")
                        print("="*40)
                    else:
                        print(f"📥 Mesaj: {mesaj}")
                except asyncio.TimeoutError:
                    # Zaman aşımında sadece döngü devam edip bağlantıyı açık tutar
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print("\n[-] Sunucu ile bağlantı koptu.")
                    break

    except ConnectionRefusedError:
        print("\n❌ HATA: Sunucuya bağlanılamadı!")
        print("💡 Lütfen ana sunucunun (server.py) açık ve çalışır durumda olduğundan emin olun.")

# Sistemi çalıştır
if __name__ == "__main__":
    asyncio.run(ogrenci_baglan())
