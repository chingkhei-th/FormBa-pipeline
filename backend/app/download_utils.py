import os
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy.orm import Session
from app import models


def create_category_zip(category_id: str, db: Session) -> bytes:
    """
    Creates a zip file containing JSON files for all reviewed documents in a category.
    Each JSON file contains only the 'data' portion of the document.
    """
    category = (
        db.query(models.ApplicantDocuments)
        .filter(models.ApplicantDocuments.doc_type == category_id)
        .first()
    )

    if not category:
        raise ValueError("Category not found")

    with TemporaryDirectory() as temp_dir:
        category_dir = Path(temp_dir) / category.doc_type
        json_dir = category_dir / "json_files"

        os.makedirs(json_dir)

        # Get all reviewed documents for this category
        documents = (
            db.query(models.ApplicantDocuments)
            .filter(
                models.ApplicantDocuments.doc_type == category_id,
                models.ApplicantDocuments.is_reviewed == True,
            )
            .all()
        )

        if not documents:
            raise ValueError("No reviewed documents found in this category")

        for doc in documents:
            try:
                # Parse the extracted_content
                content = (
                    doc.extracted_content
                    if isinstance(doc.extracted_content, dict)
                    else json.loads(doc.extracted_content)
                )

                # Get only the 'data' portion
                data = content.get("data", {})

                # Create JSON file for the document
                json_filename = f"{Path(doc.file_name).stem}.json"
                json_path = json_dir / json_filename

                # Write the data to JSON file
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

            except Exception as e:
                print(f"Error processing document {doc.id}: {str(e)}")
                continue

        # Create zip file
        zip_path = Path(temp_dir) / f"{category.doc_type}_reviewed.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(json_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(category_dir)
                    zipf.write(file_path, arcname)

        # Read and return the zip file content
        with open(zip_path, "rb") as f:
            return f.read()
