import aiohttp
import asyncio
import base64
from config import BUZZHEAVIER_API_KEY, BUZZHEAVIER_UPLOAD_BASE, MESSAGES

class BuzzheavierUploader:
    def __init__(self, bot):
        self.bot = bot
        self.session = None
    
    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    async def upload_file(self, file_data):
        """Upload file to buzzheavier.com using the provided API"""
        try:
            # Get the file from Telegram
            file = await self.bot.get_file(file_data['file_id'])
            file_name = file_data['file_name']
            
            # Download file content
            file_content = await file.download_as_bytearray()
            file_size = len(file_content)
            
            # Prepare upload URL based on available parameters
            upload_url = f"{BUZZHEAVIER_UPLOAD_BASE}/{file_name}"
            
            # Prepare headers
            headers = {}
            if BUZZHEAVIER_API_KEY:
                headers['Authorization'] = f'Bearer {BUZZHEAVIER_API_KEY}'
            
            # Upload to buzzheavier using PUT method
            session = await self.get_session()
            
            async with session.put(
                upload_url,
                data=file_content,
                headers=headers
            ) as response:
                
                if response.status in [200, 201]:
                    # For buzzheavier, the response might be the download URL or JSON
                    response_text = await response.text()
                    
                    # Try to parse as JSON, otherwise use as direct URL
                    try:
                        result = await response.json()
                        download_url = result.get('url', response_text)
                    except:
                        download_url = response_text
                    
                    # Format success message
                    formatted_size = self.format_file_size(file_size)
                    
                    return {
                        'success': True,
                        'download_url': download_url,
                        'file_name': file_name,
                        'file_size': formatted_size
                    }
                else:
                    error_text = await response.text()
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}: {error_text}"
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def upload_file_with_note(self, file_data, note_text):
        """Upload file with note to buzzheavier.com"""
        try:
            file = await self.bot.get_file(file_data['file_id'])
            file_name = file_data['file_name']
            file_content = await file.download_as_bytearray()
            
            # Encode note in base64
            note_b64 = base64.b64encode(note_text.encode()).decode()
            
            upload_url = f"{BUZZHEAVIER_UPLOAD_BASE}/{file_name}?note={note_b64}"
            
            headers = {}
            if BUZZHEAVIER_API_KEY:
                headers['Authorization'] = f'Bearer {BUZZHEAVIER_API_KEY}'
            
            session = await self.get_session()
            
            async with session.put(
                upload_url,
                data=file_content,
                headers=headers
            ) as response:
                
                if response.status in [200, 201]:
                    response_text = await response.text()
                    try:
                        result = await response.json()
                        download_url = result.get('url', response_text)
                    except:
                        download_url = response_text
                    
                    formatted_size = self.format_file_size(len(file_content))
                    
                    return {
                        'success': True,
                        'download_url': download_url,
                        'file_name': file_name,
                        'file_size': formatted_size
                    }
                else:
                    error_text = await response.text()
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}: {error_text}"
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def close(self):
        if self.session:
            await self.session.close()
