
import asyncio
from collections import deque
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from utils.Quare_manager import SONG_QUEUES

executor = ThreadPoolExecutor(max_workers=2)

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

async def get_audio_source(song_query):
    try:
        ydl_options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "default_search": "auto"
        }
        query = song_query
        results = await search_ytdlp_async(query, ydl_options)
        tracks = results.get("entries", [])
        if not tracks:
            return None, None
        first_track = tracks[0]
        return first_track["url"], first_track.get("title", "Untitled")
    except Exception as e:
        print(f"Error getting audio: {e}")
        return None, None


async def play_next_song(voice_client, guild_id, channel, bot):
    from utils.Quare_manager import SONG_QUEUES
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()
        await channel.send(f"Now playing: **{title}**")
        if len(SONG_QUEUES[guild_id]) >= 1:
            next_query = SONG_QUEUES[guild_id][0][1]
            asyncio.create_task(get_audio_source(next_query))

        return audio_url, title
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()
    return None, None