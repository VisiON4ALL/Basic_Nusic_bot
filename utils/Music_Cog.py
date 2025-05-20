import discord
from discord.ext import commands
from discord import app_commands
from utils.music import get_audio_source, play_next_song as utils_play_next
from collections import deque
import asyncio
from utils.Quare_manager import SONG_QUEUES

class Music(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a song or add it to the queue.")
    @app_commands.describe(song_query="Search query")
    async def play(self, interaction: discord.Interaction, song_query: str):
        await interaction.response.defer()
        user_voice = interaction.user.voice
        if not user_voice:
            await interaction.followup.send("You must be in a voice channel.")
            return

        voice_channel = user_voice.channel
        voice_client = interaction.guild.voice_client

        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_channel != voice_client.channel:
            await voice_client.move_to(voice_channel)

        audio_url, title = await get_audio_source(song_query)
        if not audio_url:
            await interaction.followup.send("No results found.")
            return

        guild_id = str(interaction.guild.id)
        if guild_id not in SONG_QUEUES:
            SONG_QUEUES[guild_id] = deque()

        SONG_QUEUES[guild_id].append((audio_url, title))

        if voice_client.is_playing() or voice_client.is_paused():
            await interaction.followup.send(f"Added to queue: **{title}**")
        else:
            await interaction.followup.send(f"Now playing: **{title}**")
            await self.start_next_song(voice_client, guild_id, interaction.channel)

    async def start_next_song(self, voice_client, guild_id, channel):
        audio_url, title = await utils_play_next(voice_client, guild_id, channel, self.bot)
        if not audio_url:
            return
        asyncio.create_task(self._play_audio(voice_client, guild_id, channel, audio_url, title))

    async def _play_audio(self, voice_client, guild_id, channel, audio_url, title):
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 64k",
            "executable": "bin\\ffmpeg\\ffmpeg.exe"
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(self.start_next_song(voice_client, guild_id, channel), self.bot.loop)

        voice_client.play(source, after=after_play)

    @app_commands.command(name="skip", description="Skips the current playing song")
    async def skip(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            await interaction.response.send_message("Skipped the current song.")
        else:
            await interaction.response.send_message("Not playing anything to skip.")

    @app_commands.command(name="pause", description="Pause the currently playing song.")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return await interaction.response.send_message("I'm not in a voice channel.")
        if not voice_client.is_playing():
            return await interaction.response.send_message("Nothing is currently playing.")
        voice_client.pause()
        await interaction.response.send_message("Playback paused!")

    @app_commands.command(name="resume", description="Resume the currently paused song.")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            return await interaction.response.send_message("I'm not in a voice channel.")
        if not voice_client.is_paused():
            return await interaction.response.send_message("I’m not paused right now.")
        voice_client.resume()
        await interaction.response.send_message("Playback resumed!")

    @app_commands.command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.followup.send_message("I'm not connected to any voice channel.")
        guild_id_str = str(interaction.guild.id)
        if guild_id_str in SONG_QUEUES:
            SONG_QUEUES[guild_id_str].clear()
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        await voice_client.disconnect()
        await interaction.followup.send("Stopped playback and disconnected!")

    async def tree_on_error(
            self,
            interaction: discord.Interaction,
            error: app_commands.AppCommandError
    ):
       await interaction.followup.send(f"Произошла ошибка- {error}")

async def setup(bot):
    await bot.add_cog(Music(bot))