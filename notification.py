from abc import ABC, abstractmethod

"""
1. Define User with all properties
- user_id
- email_enabled
- sms_enabled
- email_address
- phone_number
"""
class User:
    def __init__(self, user_id, email_enabled, sms_enabled, email_address, phone_number):
        self.user_id = user_id
        self.email_enabled = email_enabled
        self.sms_enabled = sms_enabled
        self.email_address = email_address
        self.phone_number = phone_number

# 2. Define NotificationChannel interface with send method
class NotificationChannel(ABC):
    @abstractmethod
    def send(self, to, subject, content):
        pass

# 3. Mock Email & SMS channel
class EmailChannel(NotificationChannel):
    def send(self, to, subject, content):
        print(f"[Email] To: {to}, Subject: {subject}, Content: {content}")

class SMSChannel(NotificationChannel):
    def send(self, to, subject, content):
        print(f"[SMS] To: {to}, Content: {content}")

# 4. Notification Service
class NotificationService:
    def __init__(self):
        self.channels = {
            'email': EmailChannel(),
            'sms': SMSChannel(),
        }

    def notify(self, user, subject, message):
        if user.email_enabled and user.email_address:
            self.channels['email'].send(user.email_address, subject, message)
        elif user.sms_enabled and user.phone_number:
            self.channels['sms'].send(user.phone_number, None, message)
        else:
            print("No notification channel enabled for user.")

# 5. Demo
if __name__ == "__main__":
    user1_data = {
        "user_id": 1,
        "email_enabled": True,
        "sms_enabled": False,
        "email_address": "user1@example.com",
        "phone_number": "0123456789"
    }
    user2_data = {
        "user_id": 2,
        "email_enabled": False,
        "sms_enabled": True,
        "email_address": "",
        "phone_number": "0944314761"
    }
    user3_data = {
        "user_id": 3,
        "email_enabled": False,
        "sms_enabled": False,
        "email_address": "",
        "phone_number": ""
    }
    user1 = User(**user1_data)
    user2 = User(**user2_data)
    user3 = User(**user3_data)

    service = NotificationService()
    service.notify(user1, "Welcome", "Welcome to our service!")
    service.notify(user2, "Alert", "You have a new message.")
    service.notify(user3, "No Channel", "You have no notification channel enabled.")
