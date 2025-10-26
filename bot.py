import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

from config import BOT_TOKEN, MESSAGES
from queue_manager import GlobalQueueManager

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global queue manager instance
queue_manager = None

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if not size_bytes:
        return "0 B"
    
    size_bytes = int(size_bytes)
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(MESSAGES['welcome'])

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /queue command to show queue status"""
    global queue_manager
    if not queue_manager:
        await update.message.reply_text("❌ Queue manager not initialized yet. Please wait...")
        return
        
    stats = await queue_manager.get_queue_stats()
    user_position = await queue_manager.get_user_position(update.effective_chat.id)
    
    if user_position is None:
        position_text = MESSAGES['no_files_in_queue']
    else:
        position_text = f"#{user_position}"
    
    await update.message.reply_text(
        MESSAGES['queue_status'].format(
            stats['queued'],
            stats['processing'],
            position_text
        )
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    global queue_manager
    if not queue_manager:
        await update.message.reply_text("❌ Queue manager not initialized yet. Please wait...")
        return
        
    stats = await queue_manager.get_queue_stats()
    await update.message.reply_text(
        f"🔄 System Status\n"
        f"📊 Queue: {stats['queued']} waiting\n"
        f"⚡ Processing: {stats['processing']}\n"
        f"✅ Completed: {stats['completed']}\n"
        f"❌ Failed: {stats['failed']}\n"
        f"🔧 Processing: {'Active' if queue_manager.is_processing else 'Inactive'}"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats command"""
    global queue_manager
    if not queue_manager:
        await update.message.reply_text("❌ Queue manager not initialized yet. Please wait...")
        return
        
    user_stats = await queue_manager.get_user_stats(update.effective_chat.id)
    
    formatted_size = format_file_size(user_stats['total_size'])
    
    await update.message.reply_text(
        MESSAGES['user_stats'].format(
            user_stats['uploads_total'],
            user_stats['uploads_successful'],
            user_stats['uploads_failed'],
            formatted_size
        )
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with files"""
    global queue_manager
    if not update.message or not update.message.effective_attachment:
        await update.message.reply_text("Please send a file to upload to buzzheavier.com")
        return
    
    if not queue_manager:
        await update.message.reply_text("❌ Queue manager not initialized yet. Please wait a moment and try again.")
        return

    try:
        # Get file information
        file_type = 'document'
        if update.message.document:
            file_id = update.message.document.file_id
            file_name = update.message.document.file_name or "unknown_file"
            file_size = update.message.document.file_size
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_name = f"photo_{file_id}.jpg"
            file_size = update.message.photo[-1].file_size
            file_type = 'photo'
        elif update.message.video:
            file_id = update.message.video.file_id
            file_name = update.message.video.file_name or f"video_{file_id}.mp4"
            file_size = update.message.video.file_size
            file_type = 'video'
        elif update.message.audio:
            file_id = update.message.audio.file_id
            file_name = update.message.audio.file_name or f"audio_{file_id}.mp3"
            file_size = update.message.audio.file_size
            file_type = 'audio'
        else:
            await update.message.reply_text("❌ Unsupported file type")
            return
        
        # Prepare file data
        file_data = {
            'file_id': file_id,
            'file_name': file_name,
            'file_size': file_size,
            'file_type': file_type,
            'chat_id': update.effective_chat.id,
            'message_id': update.message.message_id
        }
        
        # Add to queue
        position = await queue_manager.add_to_queue(file_data)
        
        # Send confirmation
        await update.message.reply_text(
            MESSAGES['file_received'].format(position),
            reply_to_message_id=update.message.message_id
        )
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(
            MESSAGES['error'].format(str(e)),
            reply_to_message_id=update.message.message_id
        )

async def periodic_cleanup():
    """Periodic cleanup of stuck uploads"""
    global queue_manager
    while True:
        await asyncio.sleep(3600)  # Run every hour
        try:
            if queue_manager:
                await queue_manager.cleanup_stuck_uploads()
                logger.info("Performed periodic cleanup of stuck uploads")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

async def main():
    """Main function"""
    global queue_manager
    
    logger.info("Starting Buzzheavier Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("queue", queue_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("mystats", stats_command))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    # Initialize queue manager
    queue_manager = GlobalQueueManager(application.bot)
    
    # Start queue processing
    asyncio.create_task(queue_manager.process_queue())
    
    # Start cleanup task
    asyncio.create_task(periodic_cleanup())
    
    logger.info("Buzzheavier Bot started successfully!")
    
    # Start polling
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # Use asyncio.run() for simplicity
    asyncio.run(main())
