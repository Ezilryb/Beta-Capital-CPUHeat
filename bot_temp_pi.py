import discord
from discord.ext import commands, tasks
import subprocess
import asyncio
import schedule
import time
from datetime import datetime
import threading

# Variables globales
TOKEN = 'TON_TOKEN'  # Remplace par ton token Discord
CHANNEL_ID = 123456789012345678  # Remplace par l'ID du channel
TEMP_THRESHOLD = 72.0  # Seuil en °C
CHECK_INTERVAL = 300  # Vérification toutes les 5 minutes (en secondes)
temp_history = {}  # Dict pour stocker les températures par heure (clé: 'HH:MM', valeur: temp)

# Fonction pour obtenir la température du Pi
def get_temperature():
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
        temp_str = output.split('=')[1].split("'")[0]
        return float(temp_str)
    except Exception as e:
        print(f"Erreur lors de la mesure de température: {e}")
        return None

# Bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user}')
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("Bot de monitoring température Raspberry Pi démarré !")
    # Démarre la boucle de vérification d'alerte
    alert_loop.start()
    # Démarre le scheduler dans un thread séparé
    threading.Thread(target=run_scheduler, daemon=True).start()

# Boucle pour vérifier les alertes (>72°C)
@tasks.loop(seconds=CHECK_INTERVAL)
async def alert_loop():
    temp = get_temperature()
    if temp is not None and temp > TEMP_THRESHOLD:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"🚨 ALERTE : Température du Raspberry Pi dépasse {TEMP_THRESHOLD}°C ! Actuelle : {temp:.1f}°C")

# Fonctions du scheduler
def measure_temp_at_hour(hour):
    temp = get_temperature()
    if temp is not None:
        key = f"{hour:02d}:00"
        temp_history[key] = temp
        print(f"Température mesurée à {key} : {temp:.1f}°C")

async def send_daily_report():
    if temp_history:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            today = datetime.now().strftime("%Y-%m-%d")
            message = f"📊 Rapport quotidien température ({today}) :\n"
            for hour in ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00']:
                temp = temp_history.get(hour, "N/A")
                message += f"- {hour} : {temp:.1f}°C si disponible\n" if temp != "N/A" else f"- {hour} : N/A\n"
            await channel.send(message)
    # Reset pour le jour suivant
    temp_history.clear()

def run_scheduler():
    # Planifier les mesures aux heures fixes (UTC, ajuste si besoin pour ton fuseau horaire)
    schedule.every().day.at("00:00").do(measure_temp_at_hour, 0)
    schedule.every().day.at("04:00").do(measure_temp_at_hour, 4)
    schedule.every().day.at("08:00").do(measure_temp_at_hour, 8)
    schedule.every().day.at("12:00").do(measure_temp_at_hour, 12)
    schedule.every().day.at("16:00").do(measure_temp_at_hour, 16)
    schedule.every().day.at("20:00").do(measure_temp_at_hour, 20)
    # Planifier l'envoi du rapport à minuit (après la dernière mesure de 20h)
    schedule.every().day.at("00:00").do(lambda: asyncio.run_coroutine_threadsafe(send_daily_report(), bot.loop))

    while True:
        schedule.run_pending()
        time.sleep(1)

bot.run(TOKEN)
