from paddleocr import PaddleOCR
import numpy as np
import os


class OCREngine:
    def __init__(self, config):
        # Access parameters through paddleocr_params key
        self.ocr = PaddleOCR(
            lang=config.get("lang", "en"),
            use_gpu=config.get("use_gpu", False),
            layout_analysis=config.get("layout_analysis", True),
            enable_mkldnn=config.get("enable_mkldnn", False),
        )

    def extract_text(self, image, output_dir=None):
        result = self.ocr.ocr(np.array(image), cls=True)
        text = self._format_output(result)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, "extracted.txt"), "w") as f:
                f.write(text)
        return text

    def _format_output(self, result):
        return "\n".join(
            [" ".join([word_info[-1][0] for word_info in line]) for line in result]
        )
