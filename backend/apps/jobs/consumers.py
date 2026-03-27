from channels.generic.websocket import AsyncJsonWebsocketConsumer


class JobStatusConsumer(AsyncJsonWebsocketConsumer):
    GROUP = 'jobs'

    async def connect(self):
        # Validate the JWT passed as ?token=<access_token> in the WS URL.
        if not await self._authenticate():
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    # Handler for messages broadcast to the group (type 'job.update').
    async def job_update(self, event):
        await self.send_json(event['data'])

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _authenticate(self) -> bool:
        """
        Validate a JWT access token supplied via the `token` query-string
        parameter (e.g. ws://host/ws/jobs/?token=<jwt>).

        Returns True when a valid, active user is found; False otherwise.
        """
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
            user = await database_sync_to_async(User.objects.get)(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return False

        self.scope['user'] = user
        return True
