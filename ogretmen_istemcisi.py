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

async def ogretmen_baglan():
    # --- PROFESYONEL KARŞILAMA VE VERİ GİRİŞİ ---
    print("\n" + "="*40)
    print("🎓 AKILLI SINIF OYLAMA SİSTEMİ")
    print("👨‍🏫 ÖĞRETMEN İSTEMCİSİ BAŞLATILIYOR...")
    print("="*40)
    
    # İsmi kodun içine yazmak yerine öğretmenden (kullanıcıdan) dinamik olarak alıyoruz
    ogretmen_ismi = input("Lütfen sisteme giriş yapacak öğretmenin adını ve soyadını giriniz: ").strip()
    
    if not ogretmen_ismi:
        ogretmen_ismi = "İsimsiz Öğretmen"

    otomatik_ip = ip_adresimi_bul()
    uri = f"ws://{otomatik_ip}:8765" 
    
    print(f"\n🔍 Sistem IP Adresi: {otomatik_ip}")
    print(f"⏳ Sunucu aranıyor ({uri})...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Sunucu bağlantısı başarılı!\n")

            # Dinamik değişkeni JSON paketinin içine yerleştiriyoruz
            kimlik_bilgisi = {
                "rol": "ogretmen",
                "isim": ogretmen_ismi, 
                "msg": "Bağlantı doğrulama talebi"
            }
            
            await websocket.send(json.dumps(kimlik_bilgisi))
            print(f"📤 Kimlik doğrulama gönderildi (Kullanıcı: {ogretmen_ismi})")

            cevap = await websocket.recv()
            print(f"📥 Sunucu Yanıtı: {cevap}\n")

            print("="*40)
            print("⏳ Sistem hazır. İşlem yapmak veya öğrenci bağlantılarını görmek için bekleniyor...")
            print("="*40)
            
            # while True döngüsünü şununla değiştir:
            while True:
                soru_metni = input("\nSoru girin (çıkmak için 'q'): ").strip()
                if soru_metni == "q":
                    break
    
                secenekler = ["A) seçenek", "B) seçenek", "C) seçenek", "D) seçenek"]
                print("Şıkları girin (A B C D sırasıyla):")
                secenekler = []
                for harf in ["A", "B", "C", "D"]:
                    s = input(f"  {harf}: ").strip()
                    secenekler.append(f"{harf}) {s}")
    
                paket = {
                    "tip": "soru",
                    "soru": soru_metni,
                    "secenekler": secenekler
                }
                await websocket.send(json.dumps(paket))
                print("✅ Soru gönderildi!")

    except ConnectionRefusedError:
        print("\n❌ HATA: Sunucuya bağlanılamadı!")
        print("💡 Lütfen ana sunucunun (server.py) açık ve çalışır durumda olduğundan emin olun.")

# Sistemi çalıştır
asyncio.run(ogretmen_baglan())
