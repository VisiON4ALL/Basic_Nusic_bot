import discord
from discord.ext import commands
from discord import app_commands
from utils.music import get_audio_source, play_next_song as utils_play_next
from collections import deque
import asyncio
from utils.Quare_manager import SONG_QUEUES


class Music(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		tree = self.bot.tree
		self._old_tree_error = tree.on_error
		tree.on_error = self.tree_on_error

	@app_commands.command(name="play", description="Начать воспроизведение музыки или добавить в очередь")
	@app_commands.describe(song_query="Запрос для поиска трека")
	async def play(self, interaction: discord.Interaction, song_query: str):
		await interaction.response.defer()
		user_voice = interaction.user.voice
		if not user_voice:
			await interaction.followup.send("Нужно быть в голосовом канале.")
			return

		voice_channel: discord.VoiceChannel = user_voice.channel
		voice_client = interaction.guild.voice_client

		async def connect_with_fallback(vch: discord.VoiceChannel):
			async def try_connect(timeout=20, attempts=2):
				for _ in range(attempts):
					try:
						return await vch.connect(timeout=timeout, reconnect=True)
					except asyncio.TimeoutError:
						await asyncio.sleep(1)

			vc = await try_connect()
			if vc:
				return vc
			candidates = ["helsinki", "stockholm", "warsaw", "frankfurt", "rotterdam", "vienna", "prague"]
			for r in candidates:
				try:
					print(f"[voice] try region: {r}")
					await vch.edit(rtc_region=r)
					vc = await try_connect()
					if vc:
						return vc
				except asyncio.TimeoutError:
					continue
				except discord.Forbidden:
					break

			try:
				await vch.edit(rtc_region=None)
			except discord.Forbidden:
				pass
			return None

		if not voice_client:
			voice_client = await connect_with_fallback(voice_channel)
		elif voice_channel != voice_client.channel:
			try:
				await voice_client.move_to(voice_channel, timeout=10)
			except asyncio.TimeoutError:
				voice_client = await connect_with_fallback(voice_channel)

		if not voice_client or not voice_client.is_connected():
			await interaction.followup.send("Не удалось подключиться к голосовому каналу. Попробуйте другой регион/канал.")
			return


		vch = await interaction.guild.fetch_channel(voice_channel.id)
		region = getattr(vch, "rtc_region", None)
		region_str = getattr(region, "value", None) or (str(region) if region is not None else "auto")
		print(f"[voice] region now: {region_str}")
		await interaction.followup.send(f"Регион голосового канала: {region_str}")

		audio_url, title = await get_audio_source(song_query)
		if not audio_url:
			await interaction.followup.send("Ничего не найдено.")
			return

		guild_id = str(interaction.guild.id)
		if guild_id not in SONG_QUEUES:
			SONG_QUEUES[guild_id] = deque()

		SONG_QUEUES[guild_id].append((audio_url, title))

		if voice_client.is_playing() or voice_client.is_paused():
			await interaction.followup.send(f"Добавлено в очередь: **{title}**")
		else:
			await interaction.followup.send(f"Сейчас играет: **{title}**")
			await self.start_next_song(voice_client, guild_id, interaction.channel)

	async def start_next_song(self, voice_client, guild_id, channel):
		audio_url, title = await utils_play_next(voice_client, guild_id, channel, self.bot)
		if not audio_url:
			return
		asyncio.create_task(self._play_audio(voice_client, guild_id, channel, audio_url, title))

	async def _play_audio(self, voice_client, guild_id, channel, audio_url, title):
		ffmpeg_options = {
			"before_options": "-re -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
			"options": "-vn"
		}

		source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)

		def after_play(error):
			if error:
				asyncio.run_coroutine_threadsafe(
					channel.send(f"Ошибка воспроизведения {title}: {error}"),
					self.bot.loop
				)
			asyncio.run_coroutine_threadsafe(
				self.start_next_song(voice_client, guild_id, channel),
				self.bot.loop
			)

		voice_client.play(source, after=after_play)

	@app_commands.command(name="skip", description="Пропустить текущий трек")
	async def skip(self, interaction: discord.Interaction):
		voice_client = interaction.guild.voice_client
		if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
			voice_client.stop()
			await interaction.response.send_message("Трек пропущен.")
		else:
			await interaction.response.send_message("Сейчас ничего не играет.")
		return

	@app_commands.command(name="pause", description="Пауза")
	async def pause(self, interaction: discord.Interaction):
		voice_client = interaction.guild.voice_client
		if voice_client is None:
			return await interaction.response.send_message("Я не в голосовом канале.")
		if not voice_client.is_playing():
			return await interaction.response.send_message("Ничего не играет.")
		voice_client.pause()
		await interaction.response.send_message("Пауза!")
		return

	@app_commands.command(name="resume", description="Возобновить")
	async def resume(self, interaction: discord.Interaction):
		voice_client = interaction.guild.voice_client
		if voice_client is None:
			return await interaction.response.send_message("Я не в голосовом канале.")
		if not voice_client.is_paused():
			return await interaction.response.send_message("Сейчас не на паузе.")
		voice_client.resume()
		await interaction.response.send_message("Продолжаем!")
		return

	@app_commands.command(name="stop", description="Остановить и очистить очередь")
	async def stop(self, interaction: discord.Interaction):
		await interaction.response.defer()
		voice_client = interaction.guild.voice_client
		if not voice_client or not voice_client.is_connected():
			return await interaction.followup.send("Я не подключен к голосовому каналу.")
		guild_id_str = str(interaction.guild.id)
		if guild_id_str in SONG_QUEUES:
			SONG_QUEUES[guild_id_str].clear()
		if voice_client.is_playing() or voice_client.is_paused():
			voice_client.stop()
		await voice_client.disconnect()
		await interaction.followup.send("Воспроизведение остановлено и бот отключен")
		return

	async def tree_on_error(
		self,
		interaction: discord.Interaction,
		error: app_commands.AppCommandError
	):
		await interaction.followup.send(f"Произошла ошибка: {error}")


async def setup(bot):
	await bot.add_cog(Music(bot))