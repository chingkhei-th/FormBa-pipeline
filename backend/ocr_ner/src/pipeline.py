from .preprocessor import DocumentPreprocessor
from .ocr_engine import OCREngine
from .ner_processor import NERProcessor
import yaml
import os


class DocumentProcessingPipeline:
    def __init__(self, config_path):
        # Determine the directory of the config file
        self.config_dir = os.path.dirname(config_path)

        # Load the configuration file
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Update prompt paths to be absolute based on config_dir
        for doc_type in self.config["doc_types"]:
            prompt_rel_path = self.config["doc_types"][doc_type]["prompt"]
            self.config["doc_types"][doc_type]["prompt"] = os.path.join(
                self.config_dir, prompt_rel_path
            )

        # Initialize pipeline components
        self.preprocessor = DocumentPreprocessor()
        self.ocr = OCREngine(self.config["ocr"]["paddleocr_params"])
        self.ner = NERProcessor(self.config)

    def process_document(self, document, output_dir=None):
        # Preprocess image
        processed_img = self.preprocessor.process(document["image"])

        # OCR Processing with optional output_dir
        text = self.ocr.extract_text(processed_img, output_dir)

        # Entity Extraction
        entities = self.ner.extract_entities(text, document["doc_type"])

        return {"text": text, "entities": entities, "metadata": document}
