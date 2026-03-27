"""Capture login and logout events for the audit log."""
import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from .models import AuditLog

logger = logging.getLogger('audit')


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):  # noqa: ARG001
    AuditLog.objects.create(
        username=user.username,
        action='login',
        ip_address=_get_ip(request),
        method='POST',
        path='/api/token/',
    )
    logger.info('AUDIT LOGIN %s from %s', user.username, _get_ip(request))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):  # noqa: ARG001
    if user:
        AuditLog.objects.create(
            username=user.username,
            action='logout',
            ip_address=_get_ip(request),
            method='POST',
            path='/api/token/',
        )
        logger.info('AUDIT LOGOUT %s', user.username)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):  # noqa: ARG001
    AuditLog.objects.create(
        username=credentials.get('username', ''),
        action='login',
        detail='failed',
        ip_address=_get_ip(request),
        method='POST',
        path='/api/token/',
        status_code=401,
    )
    logger.warning(
        'AUDIT LOGIN_FAILED %s from %s',
        credentials.get('username', ''),
        _get_ip(request),
    )


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
