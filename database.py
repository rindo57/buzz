import motor.motor_asyncio
from bson import ObjectId
from datetime import datetime, timedelta
from config import MONGODB_URI, MONGODB_DB_NAME, MONGODB_QUEUE_COLLECTION, MONGODB_USERS_COLLECTION, MONGODB_STATS_COLLECTION

class MongoDBManager:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[MONGODB_DB_NAME]
        self.queue = self.db[MONGODB_QUEUE_COLLECTION]
        self.users = self.db[MONGODB_USERS_COLLECTION]
        self.stats = self.db[MONGODB_STATS_COLLECTION]
        
        # Create indexes
        asyncio.create_task(self.create_indexes())
    
    async def create_indexes(self):
        """Create necessary indexes for performance"""
        await self.queue.create_index("status")
        await self.queue.create_index("chat_id")
        await self.queue.create_index("created_at")
        await self.queue.create_index([("status", 1), ("priority", -1), ("created_at", 1)])
        await self.users.create_index("chat_id", unique=True)
        await self.stats.create_index("chat_id")
    
    async def add_to_queue(self, file_data):
        """Add file to upload queue"""
        queue_item = {
            'file_id': file_data['file_id'],
            'file_name': file_data['file_name'],
            'file_size': file_data['file_size'],
            'file_type': file_data.get('file_type', 'document'),
            'chat_id': file_data['chat_id'],
            'message_id': file_data['message_id'],
            'status': 'queued',
            'priority': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'attempts': 0,
            'max_attempts': 3
        }
        
        result = await self.queue.insert_one(queue_item)
        
        # Get position in queue
        position = await self.queue.count_documents({
            'status': 'queued',
            'created_at': {'$lt': queue_item['created_at']}
        })
        
        return position + 1  # 1-based position
    
    async def get_next_upload(self):
        """Get next file for processing"""
        # Find oldest queued item
        item = await self.queue.find_one_and_update(
            {
                'status': 'queued',
                'attempts': {'$lt': '$max_attempts'}
            },
            {
                '$set': {
                    'status': 'processing',
                    'updated_at': datetime.utcnow()
                },
                '$inc': {'attempts': 1}
            },
            sort=[('priority', -1), ('created_at', 1)]
        )
        return item
    
    async def mark_completed(self, file_id, download_url=None, error=None):
        """Mark upload as completed or failed"""
        update_data = {
            'updated_at': datetime.utcnow()
        }
        
        if download_url and not error:
            update_data['status'] = 'completed'
            update_data['download_url'] = download_url
            update_data['completed_at'] = datetime.utcnow()
        else:
            update_data['status'] = 'failed'
            update_data['error'] = str(error)
        
        await self.queue.update_one(
            {'file_id': file_id},
            {'$set': update_data}
        )
        
        # Update user statistics
        if download_url and not error:
            await self.update_user_stats(file_id, True)
        else:
            await self.update_user_stats(file_id, False)
    
    async def update_user_stats(self, file_id, success=True):
        """Update user upload statistics"""
        # Get the file info first
        file_item = await self.queue.find_one({'file_id': file_id})
        if not file_item:
            return
        
        chat_id = file_item['chat_id']
        file_size = file_item.get('file_size', 0)
        
        # Update or create user stats
        update_fields = {
            'last_upload_at': datetime.utcnow(),
            'total_size': file_size
        }
        
        if success:
            update_fields['uploads_successful'] = 1
        else:
            update_fields['uploads_failed'] = 1
        
        await self.stats.update_one(
            {'chat_id': chat_id},
            {
                '$inc': update_fields,
                '$setOnInsert': {
                    'created_at': datetime.utcnow(),
                    'uploads_total': 1,
                    'uploads_successful': 1 if success else 0,
                    'uploads_failed': 0 if success else 1
                }
            },
            upsert=True
        )
    
    async def get_queue_stats(self):
        """Get queue statistics"""
        total_queued = await self.queue.count_documents({'status': 'queued'})
        total_processing = await self.queue.count_documents({'status': 'processing'})
        total_completed = await self.queue.count_documents({'status': 'completed'})
        total_failed = await self.queue.count_documents({'status': 'failed'})
        
        return {
            'queued': total_queued,
            'processing': total_processing,
            'completed': total_completed,
            'failed': total_failed
        }
    
    async def get_user_position(self, chat_id):
        """Get user's position in queue"""
        # Find oldest queued item for this user
        user_item = await self.queue.find_one(
            {
                'chat_id': chat_id,
                'status': 'queued'
            },
            sort=[('created_at', 1)]
        )
        
        if not user_item:
            return None
        
        # Count how many items are before this one
        position = await self.queue.count_documents({
            'status': 'queued',
            'created_at': {'$lt': user_item['created_at']}
        })
        
        return position + 1  # 1-based position
    
    async def get_user_stats(self, chat_id):
        """Get user upload statistics"""
        stats = await self.stats.find_one({'chat_id': chat_id})
        if not stats:
            return {
                'uploads_total': 0,
                'uploads_successful': 0,
                'uploads_failed': 0,
                'total_size': 0
            }
        
        return {
            'uploads_total': stats.get('uploads_total', 0),
            'uploads_successful': stats.get('uploads_successful', 0),
            'uploads_failed': stats.get('uploads_failed', 0),
            'total_size': stats.get('total_size', 0)
        }
    
    async def cleanup_stuck_uploads(self):
        """Clean up uploads stuck in processing state for too long"""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        await self.queue.update_many(
            {
                'status': 'processing',
                'updated_at': {'$lt': cutoff_time}
            },
            {
                '$set': {
                    'status': 'queued',
                    'updated_at': datetime.utcnow()
                }
            }
        )
    
    async def get_recent_uploads(self, chat_id, limit=10):
        """Get user's recent uploads"""
        cursor = self.queue.find(
            {
                'chat_id': chat_id,
                'status': {'$in': ['completed', 'failed']}
            }
        ).sort('created_at', -1).limit(limit)
        
        return await cursor.to_list(length=limit)
