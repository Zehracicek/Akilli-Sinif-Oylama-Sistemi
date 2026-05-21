import asyncio
import websockets
import json
import time

WS_URI = 'ws://127.0.0.1:8765'

async def teacher_task():
    async with websockets.connect(WS_URI) as ws:
        print('[TEACHER] connected')
        await ws.send(json.dumps({'rol':'ogretmen','isim':'Test Ogretmen'}))
        # wait a bit for students to connect
        await asyncio.sleep(1)
        soru = {
            'tip':'soru', 'soru':'Test soru: Hangisi doğru?',
            'secenekler':['Seçenek A','Seçenek B'], 'soru_tipi':'coktan_secmeli',
            'gizli_oylama':False, 'sure':5, 'dogru_cevap':'A'
        }
        print('[TEACHER] sending question')
        await ws.send(json.dumps(soru))

        # Listen for a few seconds to see live updates
        end = time.time() + 8
        try:
            while time.time() < end:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                print('[TEACHER recv]', msg)
        except asyncio.TimeoutError:
            pass

async def student_task(name, answer, delay=0.5):
    async def run_student():
        async with websockets.connect(WS_URI) as ws:
            await ws.send(json.dumps({'rol': 'ogrenci', 'isim': name}))
            while True:
                msg = await ws.recv()
                d = json.loads(msg)
                print(f'[STUDENT {name} recv]', d)
                if d.get('tip') == 'soru':
                    await asyncio.sleep(delay)
                    await ws.send(json.dumps({'tip': 'cevap', 'soru_id': d.get('soru_id'), 'cevap': answer}))
                if d.get('tip') in ('sure_doldu', 'sonuc', 'zaman_bitti'):
                    break

    try:
        await asyncio.wait_for(run_student(), timeout=15)
    except asyncio.TimeoutError:
        print(f'[STUDENT {name}] timeout — bağlantı kesildi')

async def main():
    t = asyncio.create_task(teacher_task())
    await asyncio.sleep(0.2)
    s1 = asyncio.create_task(student_task('Alice','A',delay=1))
    s2 = asyncio.create_task(student_task('Bob','B',delay=2))

    await asyncio.gather(t, s1, s2)

if __name__ == '__main__':
    asyncio.run(main())
