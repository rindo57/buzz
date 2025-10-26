import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = "8444487030:AAEqLWrqWSoAjU7BoHzXiYwALZujx-WZlQI"

# Buzzheavier API Configuration
BUZZHEAVIER_API_KEY = os.getenv('BUZZHEAVIER_API_KEY')
BUZZHEAVIER_UPLOAD_BASE = "https://w.buzzheavier.com"
BUZZHEAVIER_API_BASE = "https://buzzheavier.com/api"

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://noitamina:Emina4002@cluster0.uaq2e0l.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'buzzheavier_bot')
MONGODB_QUEUE_COLLECTION = "upload_queue"
MONGODB_USERS_COLLECTION = "users"
MONGODB_STATS_COLLECTION = "stats"

# Queue Configuration
MAX_CONCURRENT_UPLOADS = 3

# Bot Messages
MESSAGES = {
    'welcome': "🤖 Welcome to Buzzheavier Upload Bot!\n\nSend me any file and I'll upload it to buzzheavier.com\n\nCommands:\n/queue - Check your position\n/status - System status\n/mystats - Your upload statistics",
    'file_received': "📁 File received! Added to upload queue. Position in queue: {}",
    'upload_started': "🚀 Starting upload...",
    'upload_success': "✅ Upload successful!\n📄 File: {}\n🔗 Download URL: {}\n📊 Size: {}",
    'upload_failed': "❌ Upload failed: {}",
    'queue_status': "📊 Queue Status:\nTotal in queue: {}\nCurrently processing: {}\nYour position: {}",
    'user_stats': "📈 Your Upload Statistics:\nTotal Uploads: {}\nSuccessful: {}\nFailed: {}\nTotal Size: {}",
    'error': "⚠️ An error occurred: {}",
    'no_files_in_queue': "📭 You have no files in the queue"
}
