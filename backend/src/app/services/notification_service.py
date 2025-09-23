from typing import List

class NotificationService:
    def __init__(self):
        self.notifications = []

    def add_notification(self, user_id: str, type: str, title: str, body: str = None):
        # Placeholder: in real impl, save to DB and push to UI
        self.notifications.append({
            'user_id': user_id,
            'type': type,
            'title': title,
            'body': body,
            'read': False
        })

    def get_notifications(self, user_id: str) -> List[dict]:
        return [n for n in self.notifications if n['user_id'] == user_id]

# Global instance
notification_service = NotificationService()