from PIL import Image

from scraper import _normalize_png


def test_normalize_png_upscales_and_preserves_transparency(tmp_path):
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "output.png"
    source = Image.new("RGBA", (128, 64), (255, 0, 0, 128))
    source.save(source_path)

    _normalize_png(source_path, output_path)

    with Image.open(output_path) as normalized:
        assert normalized.size == (128, 128)
        assert normalized.mode == "P"
        rgba = normalized.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((64, 64))[3] > 0
        assert output_path.stat().st_size < 10_000
