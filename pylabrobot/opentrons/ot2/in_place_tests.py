"""OT-2 commands where the pipette stands, with mocked run operations."""

import unittest
from unittest.mock import AsyncMock, create_autospec

from pylabrobot.io.http import HTTP
from pylabrobot.opentrons import OT2, OT2SingleChannelPipette
from pylabrobot.opentrons.labware import LabwareRegistry
from pylabrobot.opentrons.run import COMMAND_POLL_HEADROOM, OpentronsRun
from pylabrobot.resources import Coordinate
from pylabrobot.resources.opentrons import OTDeck, opentrons_96_filtertiprack_20ul


class OT2InPlaceTests(unittest.IsolatedAsyncioTestCase):
  def setUp(self) -> None:
    """A single-channel pipette with a tip on, without hardware."""
    self.protocol_run = create_autospec(OpentronsRun, instance=True, spec_set=True)
    self.protocol_run.active = True
    self.protocol_run.get_position.return_value = Coordinate(30.25, 40.5, 20)
    self.deck = OTDeck()
    self.robot = OT2("ot2.local", deck=self.deck, io=AsyncMock(spec_set=HTTP))
    self.robot._run = self.protocol_run
    self.robot._labware = LabwareRegistry(self.protocol_run)
    self.pipette = OT2SingleChannelPipette(self.robot, "left", "p20_single_gen2", "pipette-id")
    self.rack = opentrons_96_filtertiprack_20ul("tips")
    self.deck.assign_child_at_slot(self.rack, 1)

  async def _with_tip(self) -> None:
    await self.pipette.pick_up_tip(self.rack.get_item("A1"))
    self.protocol_run.reset_mock()

  async def test_a_move_without_retract_stays_for_commands_in_place(self) -> None:
    await self._with_tip()
    here = Coordinate(100, 100, 5)

    await self.pipette.move_to(here, force_direct=True, retract=False)
    await self.pipette.aspirate_in_place(5, flow_rate=3)
    await self.pipette.dispense_in_place(5)
    await self.pipette.blow_out(flow_rate=20)
    await self.pipette.prepare_to_aspirate()
    await self.pipette.move_to_safe_z()

    self.protocol_run.move_to.assert_any_await(
      "pipette-id", here, speed=None, minimum_z_height=None, force_direct=True
    )
    self.protocol_run.aspirate_in_place.assert_awaited_once_with("pipette-id", 5.0, 3.0)
    self.protocol_run.dispense_in_place.assert_awaited_once_with("pipette-id", 5.0, 7.56)
    self.assertEqual(
      [c.args for c in self.protocol_run.execute.await_args_list],
      [
        ("blowOutInPlace", {"pipetteId": "pipette-id", "flowRate": 20.0}),
        ("prepareToAspirate", {"pipetteId": "pipette-id"}),
      ],
    )
    names = [c[0] for c in self.protocol_run.mock_calls]
    self.assertEqual(names.count("move_to"), 2)
    self.assertEqual(names[-1], "move_to")

  async def test_in_place_commands_need_a_tip_and_a_volume(self) -> None:
    with self.assertRaisesRegex(RuntimeError, "does not have a tip"):
      await self.pipette.aspirate_in_place(5)
    await self._with_tip()
    for volume in (0, -1, float("nan")):
      with self.subTest(volume=volume), self.assertRaisesRegex(ValueError, "volume"):
        await self.pipette.dispense_in_place(volume)
    with self.assertRaisesRegex(ValueError, "flow_rate"):
      await self.pipette.blow_out(flow_rate=0)
    self.assertEqual(self.protocol_run.mock_calls, [])

  async def test_a_volume_under_the_pipettes_minimum_goes_in_place(self) -> None:
    await self._with_tip()
    await self.pipette.aspirate_in_place(0.5)
    self.protocol_run.aspirate_in_place.assert_awaited_once_with("pipette-id", 0.5, 3.78)

  async def test_request_position_reads_the_robot(self) -> None:
    self.assertEqual(await self.pipette.request_position(), Coordinate(30.25, 40.5, 20))

  async def test_the_robot_waits_in_step_with_its_run(self) -> None:
    await self.robot.wait_for_duration(2.5, "dispense delay")
    await self.robot.wait_for_duration(1)
    self.assertEqual(
      [(c.args, c.kwargs) for c in self.protocol_run.execute.await_args_list],
      [
        (
          ("waitForDuration", {"seconds": 2.5, "message": "dispense delay"}),
          {"timeout": 2.5 + COMMAND_POLL_HEADROOM},
        ),
        (("waitForDuration", {"seconds": 1}), {"timeout": 1 + COMMAND_POLL_HEADROOM}),
      ],
    )
    with self.assertRaises(ValueError):
      await self.robot.wait_for_duration(-1)


if __name__ == "__main__":
  unittest.main()
