from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
import json
import re
from apps.main.models import Brewery, Controller, ManualControl, Sensor, Telemetry
from apps.main.services.manual_control import update_from_telemetry


class DirectControlTests(TestCase):
    def setUp(self):
        brewery = Brewery.objects.create(name='Test')
        self.controller = Controller.objects.create(brewery=brewery, name='ESP', mac_address='direct-test')
        self.control = ManualControl.objects.create(controller=self.controller)
        sensor = Sensor.objects.create(controller=self.controller, key='mash_temperature_sensor', name='Temperature', kind='temperature')
        self.reading = Telemetry.objects.create(sensor=sensor, value=30)
        self.url = reverse('direct-action', args=[self.controller.pk])

    def command(self, output, on):
        return self.client.post(self.url, {'output': output, 'on': 'true' if on else 'false'})

    def test_independent_outputs_and_stop_all(self):
        self.assertEqual(self.command('heater', True).status_code, 200)
        state = self.command('pump', True).json()
        self.assertTrue(state['active'])
        self.assertTrue(state['pump_on'])
        self.assertIsNone(state['ssr_on'])
        state = self.command('heater', False).json()
        self.assertFalse(state['active'])
        self.assertTrue(state['pump_on'])
        state = self.command('all', False).json()
        self.assertFalse(state['pump_on'])

    def test_pid_and_direct_are_exclusive(self):
        self.control.active = True
        self.control.save()
        self.assertEqual(self.command('pump', True).status_code, 409)
        self.control.active = False
        self.control.save()
        self.command('pump', True)
        response = self.client.post(reverse('manual-action', args=[self.controller.pk]), {'action': 'start'})
        self.assertEqual(response.status_code, 409)

    def test_pump_only_stops_on_stale_data(self):
        self.command('pump', True)
        Telemetry.objects.filter(pk=self.reading.pk).update(created_at=timezone.now() - timedelta(seconds=20))
        state = self.client.get(reverse('direct-status', args=[self.controller.pk])).json()
        self.assertFalse(state['pump_on'])
        self.assertEqual(self.command('pump', True).status_code, 409)
        self.assertEqual(self.command('all', False).status_code, 200)

    def test_direct_report_confirms_actual_outputs(self):
        state = self.command('pump', True).json()
        report = {'revision': state['revision'], 'output_mode': 'direct', 'power_percent': 0,
                  'ssr_on': False, 'pump_on': True, 'enabled': False,
                  'window_ms': 2000, 'on_time_ms': 0, 'fault': False}
        response = self.client.post(reverse('telemetry'), {'mac_address': 'direct-test',
            'metrics': {'mash_temperature_sensor': 30}, 'manual_control': report}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        state = self.client.get(reverse('direct-status', args=[self.controller.pk])).json()
        self.assertTrue(state['output_confirmed'])
        self.assertTrue(state['reported_pump_on'])
        self.assertEqual(state['signal_voltage'], 0)
        report['fault'] = True
        report['pump_on'] = False
        update_from_telemetry(self.controller, report)
        self.control.refresh_from_db()
        self.assertFalse(self.control.pump_on)

    def test_page_and_csrf(self):
        response = self.client.get(reverse('direct-control', args=[self.controller.pk]))
        self.assertContains(response, 'role="switch"', count=2)
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post(self.url, {'output': 'pump', 'on': 'true'})
        self.assertEqual(response.status_code, 403)

    def test_measured_voltage_and_current_are_not_inferred_from_relay(self):
        state = self.command('pump', True).json()
        report = {'revision': state['revision'], 'output_mode': 'direct', 'power_percent': 0,
                  'ssr_on': False, 'pump_on': True, 'enabled': False,
                  'window_ms': 2000, 'on_time_ms': 0, 'pump_voltage': 23.84, 'pump_current': 0.327}
        url = reverse('telemetry')
        payload = {'mac_address': 'direct-test', 'metrics': {'mash_temperature_sensor': 30}, 'manual_control': report}
        self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 200)
        status = reverse('direct-status', args=[self.controller.pk])
        state = self.client.get(status).json()
        self.assertEqual(state['pump_voltage'], 23.84)
        self.assertEqual(state['pump_current'], 0.327)
        ManualControl.objects.filter(pk=self.control.pk).update(reported_at=timezone.now()-timedelta(seconds=20))
        self.assertIsNone(self.client.get(status).json()['pump_voltage'])
        report.update(pump_voltage=None, pump_current=None)
        self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 200)
        self.assertIsNone(self.client.get(status).json()['pump_current'])
        for voltage, current in [(27, 1), (float('nan'), 1), (24, float('inf'))]:
            report.update(pump_voltage=voltage, pump_current=current)
            self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 400)

    def test_direct_page_and_messages_follow_language(self):
        url = reverse('direct-control', args=[self.controller.pk])
        for language, heading, waiting in [('uk', 'Повне ручне керування', 'Очікуємо підтвердження ESP32…'),
                                          ('en', 'Full manual control', 'Waiting for ESP32 confirmation…')]:
            with override(language):
                response = self.client.get(url, HTTP_ACCEPT_LANGUAGE=language)
                self.assertContains(response, heading)
                script = re.search(r'<script id="direct-messages" type="application/json">(.*?)</script>', response.content.decode(), re.S)
                self.assertEqual(json.loads(script.group(1))['waiting'], waiting)

    def test_homepage_uses_actual_outputs_and_marks_stale_reports_unknown(self):
        self.control.reported_output_mode = 'direct'
        self.control.reported_at = timezone.now()
        self.control.reported_ssr_on = False
        self.control.reported_pump_on = True
        self.control.save()
        response = self.client.get(reverse('brewery-list'))
        controller = list(response.context['breweries'])[0].controllers.all()[0]
        self.assertEqual([output['on'] for output in controller.output_statuses], [False, True])
        self.assertContains(response, 'data-poll-active="true"')
        self.assertContains(response, 'output-status-on')
        self.control.reported_at = timezone.now() - timedelta(seconds=20)
        self.control.save()
        response = self.client.get(reverse('brewery-list'))
        controller = list(response.context['breweries'])[0].controllers.all()[0]
        self.assertEqual([output['on'] for output in controller.output_statuses], [None, None])

    def test_homepage_without_output_report(self):
        self.control.delete()
        response = self.client.get(reverse('brewery-list'))
        controller = list(response.context['breweries'])[0].controllers.all()[0]
        self.assertEqual([output['on'] for output in controller.output_statuses], [None, None])
