import os
import asyncio
from aiohttp import web
from bot import setup_bot, start_scheduler

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({"status": "ok", "service": "telegram_bot"})

async def init_app():
    """Initialize the web application"""
    app = web.Application()
    
    # Setup routes
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Serve static files
    app.router.add_static('/', 'static/', name='static')
    
    # Setup and start the bot
    bot_task = asyncio.create_task(setup_bot())
    scheduler_task = asyncio.create_task(start_scheduler())
    
    return app

if __name__ == '__main__':
    # Get port from environment, default to 5000
    port = int(os.getenv('PORT', 5000))
    
    # Run the web server
    web.run_app(init_app(), host='0.0.0.0', port=port)
