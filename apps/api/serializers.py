from rest_framework import serializers

class BootstrapSensorSerializer(serializers.Serializer):
    key = serializers.CharField()
    kind = serializers.CharField()
    unit = serializers.CharField(required=False)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass



class BootstrapSerializer(serializers.Serializer):
    mac_address = serializers.CharField()
    firmware_version = serializers.CharField(required=False)

    sensors = BootstrapSensorSerializer(many=True)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

class TelemetrySerializer(serializers.Serializer):
    mac_address = serializers.CharField()

    metrics = serializers.DictField(
        child=serializers.FloatField()
    )

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass
