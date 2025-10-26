import asyncio
import time
from database import MongoDBManager
from uploader import BuzzheavierUploader

# Import MESSAGES directly from config to avoid circular imports
from config import MESSAGES

class GlobalQueueManager:
    def __init__(self, bot):
        self.db = MongoDBManager()
        self.uploader = BuzzheavierUploader(bot)
        self.bot = bot
        self.is_processing = False
        self.active_tasks = set()
    
    async def initialize(self):
        """Initialize the database indexes"""
        await self.db.ensure_indexes()
    
    async def add_to_queue(self, file_data):
        """Add file to global queue"""
        return await self.db.add_to_queue(file_data)
    
    async def process_queue(self):
        """Process the upload queue continuously"""
        if self.is_processing:
            return
        
        # Initialize database first
        await self.initialize()
        
        self.is_processing = True
        print("🚀 Starting queue processing...")
        
        try:
            while True:
                # Check if we can process more concurrent uploads
                if len(self.active_tasks) >= 3:
                    await asyncio.sleep(1)
                    continue
                
                # Get next item from queue
                queue_item = await self.db.get_next_upload()
                
                if not queue_item:
                    # No items in queue, wait and check again
                    await asyncio.sleep(5)
                    continue
                
                # Start upload task
                task = asyncio.create_task(
                    self.process_single_upload(queue_item)
                )
                self.active_tasks.add(task)
                task.add_done_callback(self.active_tasks.discard)
                
                # Small delay between starting tasks
                await asyncio.sleep(0.5)
                
        except Exception as e:
            print(f"Queue processing error: {e}")
        finally:
            self.is_processing = False
            await self.uploader.close()
            print("Queue processing stopped")
    
    async def process_single_upload(self, queue_item):
        """Process a single upload item"""
        try:
            # Send upload started message
            await self.bot.send_message(
                chat_id=queue_item['chat_id'],
                text="🚀 Starting upload...",
                reply_to_message_id=queue_item['message_id']
            )
            
            # Perform upload
            result = await self.uploader.upload_file(queue_item)
            
            if result['success']:
                # Mark as completed
                await self.db.mark_completed(
                    queue_item['file_id'],
                    download_url=result['download_url']
                )
                
                # Send success message
                await self.bot.send_message(
                    chat_id=queue_item['chat_id'],
                    text=MESSAGES['upload_success'].format(
                        result['file_name'],
                        result['download_url'],
                        result['file_size']
                    ),
                    reply_to_message_id=queue_item['message_id']
                )
            else:
                # Mark as failed
                await self.db.mark_completed(
                    queue_item['file_id'],
                    error=result['error']
                )
                
                # Send error message
                await self.bot.send_message(
                    chat_id=queue_item['chat_id'],
                    text=MESSAGES['upload_failed'].format(result['error']),
                    reply_to_message_id=queue_item['message_id']
                )
                
        except Exception as e:
            print(f"Error processing upload {queue_item['file_id']}: {e}")
            await self.db.mark_completed(
                queue_item['file_id'],
                error=str(e)
            )
    
    async def get_queue_stats(self):
        """Get queue statistics"""
        return await self.db.get_queue_stats()
    
    async def get_user_position(self, chat_id):
        """Get user's position in queue"""
        return await self.db.get_user_position(chat_id)
    
    async def get_user_stats(self, chat_id):
        """Get user upload statistics"""
        return await self.db.get_user_stats(chat_id)
    
    async def cleanup_stuck_uploads(self):
        """Clean up stuck uploads"""
        await self.db.cleanup_stuck_uploads()
