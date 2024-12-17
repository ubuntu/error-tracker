from testtools import TestCase
import unittest
import daisy
import mock
import uuid


class TestSubmitCore(TestCase):
    def test_write_weights(self):
        d = {"local": 0.25, "s1": 0.25, "s2": 0.5}
        result = daisy.gen_write_weight_ranges(d)
        self.assertEqual(result["local"][1] - result["local"][0], 0.25)
        self.assertEqual(result["s1"][1] - result["s1"][0], 0.25)
        self.assertEqual(result["s2"][1] - result["s2"][0], 0.5)

    def test_verify_configuration(self):
        # Existing local configuration gets mapped to a sole storage_provider.
        with mock.patch("daisy.config", autospec=True) as cfg:
            cfg.san_path = "/foo"
            cfg.swift_bucket = ""
            cfg.ec2_bucket = ""
            daisy.validate_and_set_configuration()
            self.assertEqual(cfg.storage_write_weights["local"], 1.0)
            self.assertEqual(cfg.core_storage["default"], "local")
            self.assertEqual(cfg.core_storage["local"]["type"], "local")

        # Existing Swift configuration gets mapped to a sole storage_provider.
        with mock.patch("daisy.config", autospec=True) as cfg:
            cfg.san_path = "/foo"
            cfg.swift_bucket = "cores"
            cfg.ec2_bucket = ""
            daisy.validate_and_set_configuration()
            self.assertEqual(cfg.storage_write_weights["swift"], 1.0)
            self.assertEqual(cfg.core_storage["default"], "swift")
            self.assertEqual(cfg.core_storage["swift"]["type"], "swift")

        # You cannot set both swift_bucket and ec2_bucket.
        with mock.patch("daisy.config", autospec=True) as cfg:
            cfg.swift_bucket = "cores"
            cfg.ec2_bucket = "cores"
            self.assertRaises(ImportError, daisy.validate_and_set_configuration)

    @mock.patch("daisy.submit_core.write_to_swift")
    @mock.patch("daisy.submit_core.write_to_s3")
    @mock.patch("random.randint")
    def test_write_to_storage_provider(self, randint, s3, swift):
        s3.return_value = True
        swift.return_value = True
        randint.return_value = 100
        ranges = {"swift-host1": 0.5, "s3-host1": 0.5}
        cs = {
            "default": "swift-host1",
            "s3-host1": {"type": "s3"},
            "swift-host1": {"type": "swift"},
        }
        ranges = daisy.gen_write_weight_ranges(ranges)
        obj = "daisy.config.write_weight_ranges"
        with mock.patch.dict(obj, ranges, clear=True):
            obj = "daisy.config.core_storage"
            with mock.patch.dict(obj, cs, clear=True):
                u = str(uuid.uuid1())
                result = daisy.submit_core.write_to_storage_provider(None, u)
                if 1.0 in ranges["s3-host1"]:
                    s3.assert_called_with(None, u, cs["s3-host1"])
                    self.assertEqual(result, "%s:s3-host1" % u)
                else:
                    swift.assert_called_with(None, u, cs["swift-host1"])
                    self.assertEqual(result, "%s:swift-host1" % u)


if __name__ == "__main__":
    unittest.main()
