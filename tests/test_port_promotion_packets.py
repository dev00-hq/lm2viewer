import json
from pathlib import Path
import tempfile
import unittest

from lba2_lm2_viewer.server import read_port_promotion_packets
from lba2_lm2_viewer.viewer import Lm2Error


def write_manifest(root: Path, packets: list[dict]) -> None:
    manifest = root / "docs" / "promotion_packets" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"schema": "promotion-packets-v1", "packets": packets}),
        encoding="utf-8",
    )


class PortPromotionPacketTests(unittest.TestCase):
    def test_read_port_promotion_packets_preserves_fixture_scene_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "tools" / "fixtures" / "promotion_packets" / "scene_live_positive.json"
            fixture.parent.mkdir(parents=True)
            fixture.write_text(
                json.dumps(
                    {
                        "schema": "promotion-packet-evidence-v1",
                        "packet_id": "scene_packet",
                        "status": "live_positive",
                        "evidence_class": "zone_transition",
                        "source": {"scene": 2, "background": 1, "active_cube": 0},
                    }
                ),
                encoding="utf-8",
            )
            write_manifest(
                root,
                [
                    {
                        "id": "scene_packet",
                        "status": "live_positive",
                        "evidence_class": "zone_transition",
                        "packet": "docs/promotion_packets/phase5/scene_packet.md",
                        "fixture": "tools/fixtures/promotion_packets/scene_live_positive.json",
                        "runtime_contracts": ["scene_contract"],
                        "canonical_runtime": True,
                    }
                ],
            )

            payload = read_port_promotion_packets(root)

        packet = payload["packets"][0]
        self.assertEqual(packet["id"], "scene_packet")
        self.assertEqual(packet["status"], "live_positive")
        self.assertIs(packet["canonical_runtime"], True)
        self.assertEqual(packet["runtime_contracts"], ["scene_contract"])
        self.assertEqual(packet["fixture_source"]["scene"], 2)
        self.assertEqual(packet["fixture_source"]["background"], 1)

    def test_read_port_promotion_packets_rejects_canonical_runtime_without_promotable_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [
                    {
                        "id": "bad_packet",
                        "status": "live_negative",
                        "evidence_class": "zone_transition",
                        "packet": "docs/promotion_packets/phase5/bad_packet.md",
                        "fixture": None,
                        "runtime_contracts": [],
                        "canonical_runtime": True,
                    }
                ],
            )

            with self.assertRaisesRegex(Lm2Error, "canonical_runtime=true requires"):
                read_port_promotion_packets(root)
