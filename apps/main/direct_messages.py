from django.utils.translation import gettext as _


def direct_messages():
    return {
        'unknown': _('Output state unknown'),
        'on': _('ON · enabled'),
        'off': _('OFF · disabled'),
        'adc_missing': _('ADC: no measurement'),
        'adc': _('Measured ADC: %(voltage)s V'),
        'pid': _('Stop PID control first.'),
        'confirmed': _('Command confirmed by ESP32.'),
        'waiting': _('Waiting for ESP32 confirmation…'),
        'status_error': _('Could not retrieve controller status.'),
        'rejected': _('Command rejected.'),
        'network': _('Connection failed. Check the controller connection.'),
        'monitor_live': _('INA226 · live voltage and current'),
        'monitor_missing': _('INA226 unavailable or readings are stale'),
    }
