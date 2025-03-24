from io import BytesIO
from PIL import Image
from .src.document_loader import load_documents
from .src.pipeline import DocumentProcessingPipeline
import json
import os
import logging


logger = logging.getLogger(__name__)


def extract_data(file_stream: BytesIO, doc_type: str):
    """
    Extract entities from a document file stream using OCR and NER.

    Args:
        file_stream (BytesIO): The file stream containing the document image.
        doc_type (str): The type of document (e.g., 'school_cert', 'aadhaar').

    Returns:
        dict: Extracted entities, or a dict with an 'error' key if processing fails.
    """
    # Load the image from the file stream
    image = Image.open(file_stream)

    # Create a document dictionary
    document = {
        "path": "stream",  # Identifier for stream-based input
        "image": image,
        "doc_type": doc_type,
    }

    # Resolve config path relative to the ocr_ner package
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")

    # Initialize the pipeline
    pipeline = DocumentProcessingPipeline(config_path)

    try:
        # Process the document without saving OCR output
        result = pipeline.process_document(document, output_dir=None)
        # Verify the result is a dictionary
        if not isinstance(result, dict):
            logger.error(f"Expected a dictionary, but got {type(result)}")
            return {"error": f"Invalid result type: {type(result)}"}
        # Check for the 'entities' key
        entities = result.get("entities")
        if entities is None:
            logger.error("'entities' key not found in result")
            return {"error": "'entities' key missing"}
        # Ensure entities is in the expected format (e.g., dict or list)
        if not isinstance(entities, (dict, list)):
            logger.error(f"Invalid entities format: {type(entities)}")
            return {"error": "Invalid entities format"}
        logger.info(f"Extracted entities: {entities}")
        return entities
    except Exception as e:
        logger.error(f"Error in extract_data: {str(e)}")
        return {"error": str(e)}

    # Return the extracted entities
    # return result["entities"]


def main():
    pipeline = DocumentProcessingPipeline("config/config.yaml")
    documents = load_documents(pipeline.config["paths"]["input_dir"])

    # Define output directory and filename
    output_dir = "./data/output"
    os.makedirs(
        output_dir, exist_ok=True
    )  # Create output directory if it doesn't exist
    output_file = os.path.join(output_dir, "extracted_data.json")

    # TODO: Add document classification here
    # For now, hardcode document type
    for doc in documents:
        doc["doc_type"] = "school_certificate"  # Example

        result = pipeline.process_document(doc)
        print(f"Processed {doc['path']}:")
        # print(result["entities"])

        # Print the JSON representation for debugging
        extracted_data = result["entities"]  # Extract entities from the result
        print(json.dumps(extracted_data, indent=4, ensure_ascii=False))

    # Save extracted JSON to output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)
    print(f"Output saved to {output_file}")


if __name__ == "__main__":
    main()
