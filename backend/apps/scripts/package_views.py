"""Views for ScriptPackage CRUD and the package test action."""
import logging

from apps.devices.models import Device
from apps.jobs.tasks import _get_collector
from core.canonical import validate_canonical
from core.collection.render import render_script
from core.parser.runner import run_parser
from core.permissions import IsAdminOrReadOnly
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .package_models import ScriptPackage
from .package_serializers import ScriptPackageSerializer

logger = logging.getLogger(__name__)


class ScriptPackageViewSet(viewsets.ModelViewSet):
    """CRUD for ScriptPackages plus an on-demand test action."""

    permission_classes = [IsAdminOrReadOnly]
    queryset = ScriptPackage.objects.select_related(
        'collection_script', 'parser_script'
    ).all()
    serializer_class = ScriptPackageSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['target_os', 'is_active']
    ordering_fields = ['name', 'created_at']

    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):  # noqa: ARG002
        """Run only the collection script against a device.

        Request body:
            device_id           int  required
            collection_content  str  optional — use this content instead of saved

        Response:
            success    bool
            raw_output str | null
            error      str | null
        """
        package = self.get_object()
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'device_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = Device.objects.get(pk=device_id, is_active=True)
        except Device.DoesNotExist:
            return Response({'error': 'Device not found or inactive.'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('collection_content')
        if content is None:
            if not package.collection_script:
                return Response({'error': 'Package has no collection script.'}, status=status.HTTP_400_BAD_REQUEST)
            content = package.collection_script.content

        try:
            rendered = render_script(content, device)
            raw_output = _get_collector(device).run(rendered)
            return Response({'success': True, 'raw_output': raw_output, 'error': None})
        except Exception as exc:  # noqa: BLE001
            logger.warning('Package collect: failed on device %s: %s', device.pk, exc)
            return Response({
                'success': False, 'raw_output': None,
                'error': f'Collection failed: {exc}',
            })

    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):  # noqa: ARG002
        """Run only the parser against provided raw input.

        Request body:
            raw_output      str  required — the raw collector output to parse
            parser_content  str  optional — use this content instead of saved

        Response:
            success           bool
            parsed_output     dict | null
            validation_errors str | null
            error             str | null
        """
        package = self.get_object()
        raw_output = request.data.get('raw_output')
        if raw_output is None:
            return Response({'error': 'raw_output is required'}, status=status.HTTP_400_BAD_REQUEST)

        content = request.data.get('parser_content')
        if content is None:
            if not package.parser_script:
                return Response({'error': 'Package has no parser script.'}, status=status.HTTP_400_BAD_REQUEST)
            content = package.parser_script.content

        try:
            parsed_output = run_parser(content, raw_output)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Package parse: failed: %s', exc)
            return Response({'success': False, 'parsed_output': None, 'validation_errors': None, 'error': f'Parser failed: {exc}'})

        validation_errors = None
        try:
            validate_canonical(parsed_output)
        except ValueError as exc:
            validation_errors = str(exc)

        return Response({
            'success': validation_errors is None,
            'parsed_output': parsed_output,
            'validation_errors': validation_errors,
            'error': None,
        })

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):  # noqa: ARG002
        """Run the package against a real device without persisting anything.

        Request body:
            device_id           int  required
            save                bool optional — persist script edits first
            collection_content  str  optional (used with save=true)
            parser_content      str  optional (used with save=true)

        Response:
            success           bool
            raw_output        str | null
            parsed_output     dict | null
            validation_errors str | null
            error             str | null
        """
        package = self.get_object()

        if request.data.get('save'):
            _save_script_content(
                package.collection_script,
                request.data.get('collection_content'),
            )
            _save_script_content(
                package.parser_script,
                request.data.get('parser_content'),
            )
            package.refresh_from_db()

        device_id = request.data.get('device_id')
        if not device_id:
            return Response(
                {'error': 'device_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not package.collection_script:
            return Response(
                {'error': 'Package has no collection script.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not package.parser_script:
            return Response(
                {'error': 'Package has no parser script.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            device = Device.objects.get(pk=device_id, is_active=True)
        except Device.DoesNotExist:
            return Response(
                {'error': 'Device not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return _run_test(device, package)


# ── module-level helpers (avoids pylint "too-few-public-methods") ─────────────

def _save_script_content(script, content):
    if script is not None and content is not None:
        script.content = content
        script.save(update_fields=['content', 'updated_at'])


def _run_test(device, package):
    """Collect → parse → validate; return a Response without side-effects."""
    # Step 1 — collect
    try:
        raw_output = _get_collector(device).run(
            render_script(package.collection_script.content, device)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            'Package test: collection failed on device %s: %s',
            device.pk, exc,
        )
        return Response({
            'success': False,
            'raw_output': None,
            'parsed_output': None,
            'validation_errors': None,
            'error': f'Collection failed: {exc}',
        })

    # Step 2 — parse
    try:
        parsed_output = run_parser(
            package.parser_script.content, raw_output
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            'Package test: parser failed on device %s: %s',
            device.pk, exc,
        )
        return Response({
            'success': False,
            'raw_output': raw_output,
            'parsed_output': None,
            'validation_errors': None,
            'error': f'Parser failed: {exc}',
        })

    # Step 3 — validate canonical schema
    validation_errors = None
    try:
        validate_canonical(parsed_output)
    except ValueError as exc:
        validation_errors = str(exc)

    return Response({
        'success': validation_errors is None,
        'raw_output': raw_output,
        'parsed_output': parsed_output,
        'validation_errors': validation_errors,
        'error': None,
    })
