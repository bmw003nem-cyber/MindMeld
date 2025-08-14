import json
import csv
from datetime import datetime
from typing import Dict, List
from config import *

def load_insights() -> Dict:
    """Load insights from JSON file"""
    try:
        with open(INSIGHTS_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default insights
        default_insights = {
            "insights": [
                "Что бы ты делал, если бы знал, что не ошибёшься?",
                "Чему ты уделяешь больше времени: своим мыслям или своим чувствам?",
                "Что в твоей жизни происходит на автопилоте?",
                "За что ты себя критикуешь, хотя другого бы простил?",
                "Какую часть себя ты скрываешь даже от близких?",
                "Что заставляет тебя откладывать то, что важно?",
                "В чём ты себе не доверяешь?",
                "Что произойдёт, если ты перестанешь всех устраивать?",
                "Когда ты последний раз делал что-то впервые?",
                "Что в твоей жизни кажется обязательным, но таковым не является?",
                "Какие твои сильные стороны ты недооцениваешь?",
                "Что ты делаешь для других, но никогда не делаешь для себя?",
                "О чём ты думаешь перед сном?",
                "Что бы ты изменил в своём окружении?",
                "За какими людьми ты наблюдаешь и почему?",
                "Что заставляет тебя чувствовать себя живым?",
                "Какую боль ты носишь, но не говоришь о ней?",
                "Что ты продолжаешь делать, хотя это тебе не подходит?",
                "В каких ситуациях ты теряешь себя?",
                "Что произойдёт, если ты скажешь «нет» там, где обычно говоришь «да»?",
                "Какие твои решения основаны на страхе?",
                "Что ты делаешь, когда никто не видит?",
                "Какую роль ты играешь, но устал от неё?",
                "Что в твоей жизни требует твоего внимания прямо сейчас?",
                "За что ты держишься, хотя пора отпустить?",
                "Что ты знаешь о себе, но делаешь вид, что не знаешь?",
                "Какие твои границы регулярно нарушаются?",
                "Что ты чувствуешь, когда остаёшься один?",
                "Какой совет ты дал бы себе в прошлом?",
                "Что мешает тебе быть собой?"
            ]
        }
        
        # Save default insights
        with open(INSIGHTS_STORE, "w", encoding="utf-8") as f:
            json.dump(default_insights, f, ensure_ascii=False, indent=2)
        
        return default_insights

def get_today_insight() -> str:
    """Get today's insight based on day of year"""
    insights_data = load_insights()
    insights = insights_data.get("insights", [])
    
    if not insights:
        return "Что тебе сейчас важно понять о себе?"
    
    # Use day of year to get consistent daily insight
    day_of_year = datetime.now().timetuple().tm_yday
    insight_index = (day_of_year - 1) % len(insights)
    
    return insights[insight_index]

def get_stats() -> str:
    """Generate bot usage statistics"""
    try:
        with open(STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            
            events = list(reader)
            
            if not events:
                return "Статистика пуста"
            
            # Count events
            event_counts = {}
            users = set()
            
            for row in events:
                if len(row) >= 3:
                    _, user_id, event = row[:3]
                    users.add(user_id)
                    event_counts[event] = event_counts.get(event, 0) + 1
            
            # Format stats
            stats = f"👥 Уникальных пользователей: {len(users)}\n"
            stats += f"📊 Всего событий: {len(events)}\n\n"
            stats += "События:\n"
            
            for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
                stats += f"• {event}: {count}\n"
            
            return stats
    
    except Exception as e:
        return f"Ошибка получения статистики: {e}"

async def broadcast_message(text: str) -> int:
    """Broadcast message to all users (placeholder - needs bot instance)"""
    # This would need to be implemented in bot.py with access to bot instance
    # For now, return 0
    return 0
