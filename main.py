import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv



discord.utils.setup_logging()
discord.utils.setup_logging(level=logging.INFO, root=True)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.presences = True

load_dotenv('token.env')

token = os.getenv('TOKEN')


bot= commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Бот подключен: {bot.user.name}')

@bot.event
async def on_disconnect():
    print(f'Бот отключен: {bot.user.name}')

@bot.command(name="sync")
async def sync(ctx: commands.Context):
    await ctx.bot.tree.sync()
    await ctx.send("Команды синхронизированы глобально!")




async def load():
    await bot.load_extension("utils.Music_Cog")
    print ('Коги загружены')

if __name__ == "__main__":
    import asyncio
    asyncio.run(load())
    asyncio.run(bot.start(token))