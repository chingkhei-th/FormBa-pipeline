import os
from PIL import Image


def load_documents(input_dir: str):
    """Load document images from directory"""
    supported_ext = [".png", ".jpg", ".jpeg", ".pdf"]
    documents = []

    for filename in os.listdir(input_dir):
        if any(filename.lower().endswith(ext) for ext in supported_ext):
            img_path = os.path.join(input_dir, filename)
            documents.append(
                {
                    "path": img_path,
                    "image": Image.open(img_path),
                    "doc_type": None,  # To be filled by classifier
                }
            )
    return documents
