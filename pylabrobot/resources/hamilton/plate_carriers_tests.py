import unittest

from pylabrobot.resources.hamilton import PLT_CAR_L4_HHS_ALT_A00


class HeaterShakerCarrierTests(unittest.TestCase):
  def test_every_site_has_its_pedestal(self):
    carrier = PLT_CAR_L4_HHS_ALT_A00("carrier")
    self.assertEqual(len(carrier.sites), 4)
    for i in range(4):
      with self.subTest(site=i):
        self.assertEqual(carrier[i].pedestal_size_z, -2.8)
