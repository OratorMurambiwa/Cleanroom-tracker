import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from .models import MessageThread, Message, Project


class ProjectChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.room_name = f"project_{self.project_id}"
        self.room_group_name = f"chat_{self.room_name}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_username = data['sender']

        saved_message = await self.save_message(self.project_id, sender_username, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': saved_message.body,
                'sender': saved_message.sender.username,
                'timestamp': saved_message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp'],
        }))

    @database_sync_to_async
    def save_message(self, project_id, sender_username, body):
        project = Project.objects.get(id=project_id)
        sender = User.objects.get(username=sender_username)
        thread, _ = MessageThread.objects.get_or_create(project=project)
        return Message.objects.create(thread=thread, sender=sender, body=body)
