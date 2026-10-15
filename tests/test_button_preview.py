import tempfile
import unittest
from pathlib import Path

from PIL import Image

from azaleacore_mpq_studio.blp import rgba_to_blp2
from azaleacore_mpq_studio.button_preview import (
    BUTTON_TEXTURE_PATHS,
    fallback_button_texture,
    load_button_texture_from_client,
    tint_button_texture,
)
from azaleacore_mpq_studio.packer import build_mpq


class ButtonPreviewTests(unittest.TestCase):
    def test_tint_multiplies_texture_and_preserves_alpha(self) -> None:
        source = Image.new("RGBA", (1, 1), (64, 128, 255, 173))

        result = tint_button_texture(source, (0.5, 0.25, 1.0))

        self.assertEqual(result.getpixel((0, 0)), (32, 32, 255, 173))

    def test_texture_is_loaded_from_a_client_mpq(self) -> None:
        payload = rgba_to_blp2(
            Image.new("RGBA", (256, 64), (80, 120, 220, 255)),
            256,
            64,
        )
        with tempfile.TemporaryDirectory() as temporary:
            game_root = Path(temporary)
            locale = game_root / "Data" / "esES"
            locale.mkdir(parents=True)
            build_mpq(
                [(BUTTON_TEXTURE_PATHS[0], payload)],
                locale / "locale-esES.MPQ",
            )

            result = load_button_texture_from_client(game_root)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.size, (256, 64))

    def test_fallback_has_the_real_button_texture_dimensions(self) -> None:
        result = fallback_button_texture()

        self.assertEqual(result.size, (256, 64))
        self.assertEqual(result.mode, "RGBA")
        self.assertGreater(result.getpixel((128, 32))[3], 0)


if __name__ == "__main__":
    unittest.main()
