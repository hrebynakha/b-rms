import math

from rest_framework import serializers
from django.utils.translation import gettext as _


class BootstrapSensorSerializer(serializers.Serializer):
    name = serializers.CharField()
    key = serializers.CharField()
    kind = serializers.CharField()
    unit = serializers.CharField(required=False)


class BootstrapSerializer(serializers.Serializer):
    mac_address = serializers.CharField()
    firmware_version = serializers.CharField(required=False)
    ip = serializers.CharField(required=False)

    sensors = BootstrapSensorSerializer(many=True)


class TelemetrySerializer(serializers.Serializer):
    mac_address = serializers.CharField()

    metrics = serializers.DictField(child=serializers.FloatField())
    manual_control = serializers.DictField(required=False)

    def validate_manual_control(self, value):
        serializer = ManualReportSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def validate_metrics(self, value):
        if any(not math.isfinite(reading) for reading in value.values()):
            raise serializers.ValidationError(_("A finite value is required."))
        return value


class ManualReportSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    power_percent = serializers.FloatField(min_value=0, max_value=100)
    output_mode = serializers.ChoiceField(choices=["pwm", "time_pwm"], required=False)
    ssr_on = serializers.BooleanField(required=False)
    window_ms = serializers.IntegerField(min_value=1000, max_value=10000, required=False)
    on_time_ms = serializers.IntegerField(min_value=0, max_value=10000, required=False)
    enabled = serializers.BooleanField(required=False)
    fault = serializers.BooleanField(required=False, default=False)
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

    def validate(self, attrs):
        if attrs.get("output_mode") == "time_pwm":
            required = ("ssr_on", "window_ms", "on_time_ms", "enabled")
            if any(key not in attrs for key in required):
                raise serializers.ValidationError(_("Time PWM telemetry requires the output state and window timing."))
            if attrs["on_time_ms"] > attrs["window_ms"]:
                raise serializers.ValidationError(_("ON time cannot exceed the control window."))
            if abs(attrs["on_time_ms"] - attrs["power_percent"] * attrs["window_ms"] / 100) > 1:
                raise serializers.ValidationError(_("Duty and ON time do not match."))
            if not attrs["enabled"] and (attrs["ssr_on"] or attrs["on_time_ms"]):
                raise serializers.ValidationError(_("A disabled output must be OFF."))
        return attrs
