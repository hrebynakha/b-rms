from django.test import TestCase
from django.urls import reverse

from apps.main.models import Brewery, Controller, Vessel, ManualControl


class EquipmentSettingsTests(TestCase):
    def setUp(self):
        self.brewery = Brewery.objects.create(name="First")
        self.other = Brewery.objects.create(name="Second")
        self.controller = Controller.objects.create(brewery=self.brewery, name="ESP", mac_address="esp-settings")
        self.url = reverse("controller-settings", args=[self.controller.pk])

    def data(self, **changes):
        values = {"controller-name": "Mash ESP", "controller-brewery": self.other.pk,
                  "vessel-name": "Mash tun", "vessel-volume_liters": "30"}
        return {**values, **changes}

    def test_multiple_vessels_can_belong_to_one_brewery(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(Vessel.objects.get(controller=self.controller).volume_liters, 20)
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.controller.refresh_from_db()
        self.assertEqual(self.controller.brewery, self.other)
        self.assertEqual(self.controller.mac_address, "esp-settings")
        self.assertEqual(self.controller.vessel.name, "Mash tun")
        self.assertEqual(self.controller.vessel.volume_liters, 30)
        status = self.client.get(reverse("manual-status", args=[self.controller.pk])).json()
        self.assertEqual(status["volume_liters"], 30)
        self.assertEqual(status["vessel_name"], "Mash tun")
        response = self.client.post(reverse("bootstrap"), {
            "mac_address": self.controller.mac_address, "sensors": [],
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.controller.refresh_from_db()
        self.assertEqual(self.controller.brewery, self.other)
        self.assertEqual(self.controller.vessel.volume_liters, 30)
        second = Controller.objects.create(brewery=self.other, name="Boil ESP", mac_address="esp-second")
        self.client.get(reverse("controller-settings", args=[second.pk]))
        self.assertEqual(self.other.controllers.count(), 2)

    def test_invalid_volume_does_not_move_controller(self):
        response = self.client.post(self.url, self.data(**{"vessel-volume_liters": "0"}))
        self.assertEqual(response.status_code, 200)
        self.controller.refresh_from_db()
        self.assertEqual(self.controller.brewery, self.brewery)

    def test_active_manual_control_blocks_reassignment(self):
        ManualControl.objects.create(controller=self.controller, active=True)
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 200)
        self.controller.refresh_from_db()
        self.assertEqual(self.controller.brewery, self.brewery)

    def test_create_and_rename_brewery_with_location(self):
        response = self.client.post(reverse("brewery-create"), {"name": "Моя броварня", "location": "Kyiv", "description": ""})
        self.assertEqual(response.status_code, 302)
        brewery = Brewery.objects.get(name="Моя броварня")
        self.assertTrue(brewery.slug)
        self.assertEqual(brewery.location, "Kyiv")
        old_slug = brewery.slug
        response = self.client.post(reverse("brewery-settings", args=[brewery.pk]), {"name": "Home brewery", "location": "Lviv", "description": ""})
        self.assertEqual(response.status_code, 302)
        brewery.refresh_from_db()
        self.assertEqual(brewery.name, "Home brewery")
        self.assertEqual(brewery.slug, old_slug)
