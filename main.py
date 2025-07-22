import asyncio
from pyrogram import Client, filters
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from config import API_ID, API_HASH, BOT_TOKEN
from youtube_dl import YoutubeDL
import os

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

# Global state
queues = {}  # chat_id: [song1, song2, ...]
current = {}  # chat_id: current_song

def ytdl(url_or_query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url_or_query, download=True)
        file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        title = info.get('title', 'Unknown Title')
        return file, title

async def play_next(chat_id):
    if queues.get(chat_id):
        next_song = queues[chat_id].pop(0)
        current[chat_id] = next_song
        await pytgcalls.change_stream(chat_id, AudioPiped(next_song["file"]))
    else:
        current.pop(chat_id, None)
        await pytgcalls.leave_group_call(chat_id)

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply("🎵 Welcome to the Music Bot!\nUse /play <song name or URL> to begin.")

@app.on_message(filters.command("play") & filters.group)
async def play(_, message):
    if len(message.command) < 2:
        return await message.reply("Please provide a YouTube URL or search query.")

    query = " ".join(message.command[1:])
    msg = await message.reply("🔎 Searching and downloading...")
    try:
        audio_file, title = ytdl(query)
    except Exception as e:
        return await msg.edit(f"❌ Download error: {e}")

    song = {"file": audio_file, "title": title}

    if message.chat.id not in current:
        current[message.chat.id] = song
        await pytgcalls.join_group_call(
            message.chat.id,
            AudioPiped(song["file"])
        )
        await msg.edit(f"▶️ Now playing: **{title}**")
    else:
        queues.setdefault(message.chat.id, []).append(song)
        await msg.edit(f"➕ Queued: **{title}**")

@app.on_message(filters.command("skip") & filters.group)
async def skip(_, message):
    if message.chat.id not in current:
        return await message.reply("🚫 Nothing is playing.")
    await message.reply("⏭ Skipping...")
    await play_next(message.chat.id)

@app.on_message(filters.command("pause") & filters.group)
async def pause(_, message):
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply("⏸ Paused.")
    except:
        await message.reply("❌ Failed to pause.")

@app.on_message(filters.command("resume") & filters.group)
async def resume(_, message):
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply("▶️ Resumed.")
    except:
        await message.reply("❌ Failed to resume.")

@app.on_message(filters.command("stop") & filters.group)
async def stop(_, message):
    try:
        await pytgcalls.leave_group_call(message.chat.id)
        queues.pop(message.chat.id, None)
        current.pop(message.chat.id, None)
        await message.reply("🛑 Stopped and left voice chat.")
    except:
        await message.reply("❌ Failed to stop.")

@app.on_message(filters.command("queue") & filters.group)
async def show_queue(_, message):
    queue = queues.get(message.chat.id, [])
    if not queue:
        return await message.reply("📭 Queue is empty.")
    msg = "\n".join([f"{idx+1}. {s['title']}" for idx, s in enumerate(queue)])
    await message.reply(f"📃 **Queue:**\n{msg}")

@app.on_message(filters.command("now") & filters.group)
async def now_playing(_, message):
    song = current.get(message.chat.id)
    if song:
        await message.reply(f"🎶 Now playing: **{song['title']}**")
    else:
        await message.reply("🚫 Nothing is currently playing.")

# Main startup
async def main():
    await app.start()
    await pytgcalls.start()
    print("✅ Bot is online.")
    await idle()

from pyrogram.idle import idle
asyncio.get_event_loop().run_until_complete(main())
