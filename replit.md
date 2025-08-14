# Overview

This is a Telegram bot for life coaching and mentoring services. The bot provides users with access to psychological guidance, self-development resources, daily insights, and consultation services. It's designed as a personal brand platform for a life coach named Roman, offering interactive features like downloadable PDF guides, daily motivational questions, and scheduling functionality for consultations and mentoring sessions.

# User Preferences

Preferred communication style: Simple, everyday language.
Technical requirement: Must use aiogram v2.25.1 API structure with @dp.callback_query_handler decorators for compatibility.
Keep-alive feature: Integrated web server on port 5000 prevents Replit sleeping and enables UptimeRobot monitoring.

# System Architecture

## Bot Framework Architecture
The application uses the aiogram framework for Telegram bot functionality, built on Python's asyncio for asynchronous operations. The main bot logic is contained in `bot.py` with modular handlers in `handlers.py` and utility functions in `utils.py`.

## Web Server Integration
The bot includes an integrated aiohttp web server for keep-alive functionality, preventing the Replit project from sleeping. The server provides health check endpoints at port 5000 with a JSON status response, making it compatible with monitoring services like UptimeRobot for continuous uptime monitoring.

## Data Storage Strategy
The application uses a file-based storage approach:
- **JSON files** for configuration data like daily insights (`insights.json`)
- **CSV files** for event logging and analytics (`events.csv`)  
- **PDF generation** on-demand for downloadable guides using ReportLab
- **In-memory data structures** (defaultdict) for session management and user state tracking

## Scheduling System
Implements APScheduler (AsyncIOScheduler) with Moscow timezone for automated tasks like sending daily insights and managing recurring bot functions.

## Content Management
Uses a hybrid content delivery system:
- **Generated PDFs** for internal guides created dynamically from text content
- **Static file serving** for external resources and media
- **Base64 encoding** for fallback images when assets are missing

## User Interaction Flow
The bot follows a callback-driven architecture with inline keyboards for navigation. User preferences and download history are tracked in-memory with CSV logging for persistence and analytics.

# External Dependencies

## Core Bot Framework
- **aiogram v2.25.1**: Telegram Bot API wrapper for Python (downgraded from v3 for compatibility)
- **APScheduler v3.10.4**: Advanced Python Scheduler for automated tasks

## PDF Generation
- **ReportLab v4.2.2**: PDF creation library for generating downloadable guides

## Web Server
- **aiohttp v3.8.6**: Asynchronous HTTP client/server framework for web endpoints (compatible with aiogram v2)

## Data Processing
- **Python standard library**: json, csv, os modules for file operations and data management

## Environment Configuration
- **BOT_TOKEN**: Telegram bot token from environment variables
- **PORT**: Configurable port for keep-alive web server (defaults to 5000)

## File System Dependencies
- Static assets stored in `/static/` directory
- Generated guides stored in local file system
- Analytics data persisted to CSV files
- JSON configuration files for bot content