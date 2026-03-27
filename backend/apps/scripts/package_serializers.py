from rest_framework import serializers
from .package_models import ScriptPackage
from .serializers import ScriptSerializer


class ScriptPackageSerializer(serializers.ModelSerializer):
    # Read: embed full script objects so the editor gets their content.
    collection_script_detail = ScriptSerializer(
        source='collection_script', read_only=True
    )
    parser_script_detail = ScriptSerializer(
        source='parser_script', read_only=True
    )

    class Meta:
        model = ScriptPackage
        fields = '__all__'
