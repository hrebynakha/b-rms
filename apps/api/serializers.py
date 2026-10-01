import math

from rest_framework import serializers
from django.utils.translation import gettext as _


class BootstrapSensorSerializer(serializers.Serializer):
    name = serializers.CharField()
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
    ip = serializers.CharField(required=False)

    sensors = BootstrapSensorSerializer(many=True)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass


class TelemetrySerializer(serializers.Serializer):
    mac_address = serializers.CharField()

    metrics = serializers.DictField(child=serializers.FloatField())
    manual_control = serializers.DictField(required=False)

    def validate_manual_control(self, value):
        serializer = ManualReportSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass


class ManualReportSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    power_percent = serializers.FloatField(min_value=0, max_value=100)
    output_mode = serializers.ChoiceField(choices=["pwm"], required=False)
    feedback_enabled = serializers.BooleanField(required=False, default=False)
    measured_voltage = serializers.FloatField(min_value=0, max_value=3.6, required=False, allow_null=True)

    def validate_measured_voltage(self, value):
        if value is not None and not math.isfinite(value):
            raise serializers.ValidationError(_("A finite value is required."))
        return value

    def validate_power_percent(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError(_("A finite value is required."))
        return value
