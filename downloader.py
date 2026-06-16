import asyncio
import os
import yt_dlp


async def download_instagram_video(url: str) -> str:
    """
    Instagram videosini yuklab oladi va fayl yo'lini qaytaradi.
    Asinxron ishlaydi, botni to'xtatib qo'ymaydi.
    """
    # Yuklangan fayllar uchun 'downloads' papkasi
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    outtmpl = os.path.join("downloads", "%(id)s.%(ext)s")

    # ─── MANA SHU YERGA PROGRESS HOOK QO'SHILDI ───
    def progress_hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded_bytes = d.get('downloaded_bytes', 0)

            if total_bytes > 0:
                percent = downloaded_bytes / total_bytes

                # SIZ XO'XISH QILGAN ANIMATSIYA CHIZIG'I (20 belgidan iborat)
                bar_length = 20
                filled_length = int(round(bar_length * percent))
                bar = '█' * filled_length + '░' * (bar_length - filled_length)

                # MB o'lchoviga o'tkazish
                total_mb = total_bytes / (1024 * 1024)
                downloaded_mb = downloaded_bytes / (1024 * 1024)

                # Tezlik va qolgan vaqt
                speed = d.get('speed', 0)
                speed_mb = (speed / (1024 * 1024)) if speed else 0
                eta = d.get('eta', 0)

                # PyCharm konsolida animatsiyani chiroyli chiqarish
                progress_text = (
                    f"📥 Yuklanmoqda... |{bar}| {percent * 100:.1f}% "
                    f"({downloaded_mb:.1f}/{total_mb:.1f} MB) "
                    f"⚡ {speed_mb:.1f} MB/s | ⏱ {eta} sek"
                )
                print(progress_text, end="\r")

    # ───────────────────────────────────────────────

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',

        # FFmpeg o'rnatilgan "bin" papkasining manzilini ko'rsatamiz:
        'ffmpeg_location': r'C:\Users\QUTLIMUROD\Desktop\FFMPEG Fayl\ffmpeg-master-latest-win64-gpl-shared\bin',

        'outtmpl': '%(title)s.%(ext)s',
    }

    # Bot yuklash funksiyasi...
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp ni bloklamaydigan qilib alohida oqimda ishga tushiramiz
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            filename = ydl.prepare_filename(info)
            # Agar format o'zgargan bo'lsa (masalan mkv -> mp4)
            if not os.path.exists(filename):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            return filename
    except Exception as e:
        print(f"Yuklashda xatolik: {e}")
        return None