from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DriftConsumer(AsyncJsonWebsocketConsumer):
    GROUP = 'drift'

    async def connect(self):
        if not await self._authenticate():
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def drift_event(self, event):
        await self.send_json(event['data'])

    async def _authenticate(self) -> bool:
        from urllib.parse import parse_qs
        from channels.db import database_sync_to_async
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from django.contrib.auth import get_user_model

        User = get_user_model()

        qs = parse_qs(self.scope.get('query_string', b'').decode())
        token_list = qs.get('token', [])
        if not token_list:
            return False

        try:
            validated = AccessToken(token_list[0])
            user_id = validated['user_id']
        except (InvalidToken, TokenError, KeyError):
            return False

        try:
            await database_sync_to_async(User.objects.get)(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return False

        return True
