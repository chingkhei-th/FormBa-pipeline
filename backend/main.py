import os
import aiohttp
import json
import requests
import boto3
import uuid
import mimetypes
import random
import string
import logging
from datetime import timedelta, datetime
from io import BytesIO
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from typing import Annotated, Union, List, Optional
from fastapi import (
    FastAPI,
    Form,
    UploadFile,
    File,
    HTTPException,
    Depends,
    BackgroundTasks,
    status,
    Query,
)
from fastapi.responses import Response, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import joinedload, Session
from sqlalchemy import distinct
from cryptography.fernet import Fernet
from app.database import engine, get_db
from app import models
from app.models import (
    Admin,
    Institutes,
    Knowledge,
    Courses,
    Users,
    ClassifiedDocuments,
    ApplicantDocuments,
    Submissions,
    ReviewUser,
)
from app.routers.auth import (
    create_access_token,
    get_password_hash,
    verify_password,
    authenticate_user,
    get_current_admin,
    get_current_user,
    oauth2_scheme,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.schemas import (
    Token,
    CoursesBase,
    CoursesResponse,
    InstitutesBase,
    InstitutesResponse,
    KnowledgeBase,
    KnowledgeResponse,
    UserResponse,
    ClassifiedDocumentBase,
    ClassifiedDocumentResponse,
    ApplicantInfoCreate,
    ClassifyRequest,
    SubmissionResponse,
    ApplicantPartialUpdate,
)
from post_processing.post_processing import process_extracted_data
from ocr_ner.data_extractor import extract_data as data_extractor

models.Base.metadata.create_all(bind=engine)

# AWS S3 Configuration
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION,
)

# Encryption configuration
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())

cipher = Fernet(ENCRYPTION_KEY)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            "app.log", maxBytes=1024 * 1024 * 5, backupCount=5
        ),  # 5 MB per file, 5 backups
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# Load environment variables from .env file
load_dotenv()

app = FastAPI()
models.Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with the exact URL of your frontend in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_ENDPOINT = "http://localhost:8000"
# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

# Mount additional static directories for css and js
app.mount("/css", StaticFiles(directory="../frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="../frontend/js"), name="js")

db_dependency = Annotated[Session, Depends(get_db)]


# Functiion for encrypting and decrypting fields
def encrypt_field(value: str) -> str:
    return cipher.encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    return cipher.decrypt(value.encode()).decode()


# Utility functions for encryption and decryption
def encrypt_applicant_info_data(data: dict) -> dict:
    """
    Encrypt sensitive applicant fields before saving to the database.
    """
    sensitive_fields = [
        "dob",
        "phone",
        "mobile",
        "address",
        "permanent_address",
        "aadhaar_number",
        "email",
    ]
    for field in sensitive_fields:
        if field in data and data[field]:
            # Ensure encrypting a string
            data[field] = encrypt_field(str(data[field]))
    return data


def decrypt_applicant_info_data(data: dict) -> dict:
    """
    Decrypt sensitive applicant fields before returning to the client.
    Also, convert fields like phone and mobile back to int.
    """
    sensitive_fields = [
        "dob",
        "phone",
        "mobile",
        "address",
        "permanent_address",
        "aadhaar_number",
        "email",
    ]
    for field in sensitive_fields:
        if field in data and data[field]:
            decrypted = decrypt_field(data[field])
            if field in ["phone", "mobile"]:
                try:
                    data[field] = str(decrypted)
                except Exception:
                    data[field] = decrypted
            else:
                data[field] = decrypted
    return data


# Function to authenticate admin
def authenticate_admin(username: str, password: str, db: Session):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.verify_password(password):
        return None
    return admin


# Endpoint for the reviewer interface
@app.get("/reviewer", response_class=FileResponse)
async def serve_reviewer():
    return FileResponse("../frontend/review_index.html")


# Login endpoint
@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # First try to authenticate as a user
    user = authenticate_user(form_data.username, form_data.password, db)
    if user:
        access_token = create_access_token(
            data={"sub": user.email, "type": "user"},
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # If not a user, try to authenticate as an admin
    admin = authenticate_admin(form_data.username, form_data.password, db)
    if admin:
        access_token = create_access_token(
            data={"sub": admin.username, "type": "admin"},
        )
        logger.info(
            f"Admin login successful, token payload: {{'sub': {admin.username}, 'type': 'admin'}}"
        )

        return {"access_token": access_token, "token_type": "bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/", response_class=FileResponse)
async def serve_root():
    # This will serve static/login.html when the root URL is accessed.
    return FileResponse("../frontend/static/login.html")


@app.get("/{page_name}", response_class=FileResponse)
async def serve_html(page_name: str):
    valid_pages = {"login.html", "register.html", "dashboard.html"}
    if page_name not in valid_pages:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(f"../frontend/static/{page_name}")


# CRUD APIs for Institutes
@app.post("/institutes/", response_model=InstitutesResponse)
def create_institute(
    institute: InstitutesBase,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    db_institute = Institutes(**institute.dict())
    db.add(db_institute)
    db.commit()
    db.refresh(db_institute)
    return db_institute


@app.get("/institutes/all", response_model=List[InstitutesResponse])
def get_all_institutes(db: Session = Depends(get_db)):
    return db.query(Institutes).options(joinedload(Institutes.courses)).all()


@app.get("/institutes/", response_model=List[InstitutesResponse])
def read_institutes(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    return (
        db.query(Institutes)
        .options(joinedload(Institutes.courses))  # Preload courses
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get("/institutes/{institute_id}", response_model=InstitutesResponse)
def read_institute(
    institute_id: int,
    db: Session = Depends(get_db),
):
    db_institute = (
        db.query(Institutes)
        .filter(Institutes.id == institute_id)
        .options(joinedload(Institutes.courses))
        .first()
    )
    if not db_institute:
        raise HTTPException(status_code=404, detail="Institute not found")
    return db_institute


# CRUD APIs for Knowledge
@app.post("/knowledge/", response_model=KnowledgeResponse)
def create_knowledge(
    knowledge: KnowledgeBase,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    db_knowledge = Knowledge(**knowledge.dict())
    db.add(db_knowledge)
    db.commit()
    db.refresh(db_knowledge)
    return db_knowledge


@app.get("/knowledge/", response_model=List[KnowledgeResponse])
def read_knowledge(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    return db.query(Knowledge).offset(skip).limit(limit).all()


@app.get("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
def read_knowledge_by_id(
    knowledge_id: int,
    db: Session = Depends(get_db),
):
    db_knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not db_knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return db_knowledge


@app.delete("/knowledge/{knowledge_id}")
def delete_knowledge(
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    db_knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
    if not db_knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    db.delete(db_knowledge)
    db.commit()
    return {"message": "Knowledge deleted successfully"}


# CRUD APIs for Courses
@app.post("/courses/", response_model=CoursesResponse)
def create_course(
    course: CoursesBase,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    institute = (
        db.query(Institutes).filter(Institutes.id == course.institute_id).first()
    )
    if not institute:
        raise HTTPException(status_code=400, detail="Invalid institute ID")

    db_course = Courses(**course.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


@app.get("/courses/", response_model=List[CoursesResponse])
def read_courses(institute_id: int = Query(None), db: Session = Depends(get_db)):
    query = db.query(Courses)
    if institute_id:
        query = query.filter(Courses.institute_id == institute_id)
    return query.all()


@app.get("/courses/{course_id}", response_model=CoursesResponse)
def read_course_by_id(
    course_id: int,
    db: Session = Depends(get_db),
):
    db_course = db.query(Courses).filter(Courses.id == course_id).first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course


@app.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    db_course = db.query(Courses).filter(Courses.id == course_id).first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(db_course)
    db.commit()
    return {"message": "Course deleted successfully"}


# Function to generate a random 6-character string
def generate_random_string(length=4):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@app.post("/users/", response_model=UserResponse)
async def create_user(
    background_tasks: BackgroundTasks,  # Moved to the beginning
    institute_name: int = Form(...),
    course_interested: int = Form(...),
    knowledge_id: Optional[Union[int, str]] = Form(None),
    phone_no: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    aadhaar_document: UploadFile = File(...),
    caste_document: UploadFile = File(...),
    school_cert_document: UploadFile = File(...),
    school_mark_document: UploadFile = File(...),
    passport_photo: UploadFile = File(...),
    signature_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    uni_cert_document: Optional[UploadFile] = File(None),
    uni_mark_document: Optional[UploadFile] = File(None),
):
    """
    Create a user, generate a submission ID, upload their documents to S3,
    and return the document count along with the user data.
    """
    # Convert empty string to None
    if knowledge_id == "":
        knowledge_id = None
    else:
        # Ensure valid integer if provided
        knowledge_id = int(knowledge_id) if knowledge_id is not None else None
    try:
        # Validate phone number
        if not str(phone_no).isdigit() or len(str(phone_no)) != 10:
            raise CustomException(
                message="Phone number must be 10 digits",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Generate a unique username and submission ID
        username = f"{phone_no}_{uuid.uuid4()}"
        submission_id = f"{phone_no}_{generate_random_string()}"  # Unique identifier for this submission

        # Upload each document if provided – using the same pattern as for passport_photo/signature_photo.
        async def upload_file(file: Optional[UploadFile], label: str) -> str:
            if file:
                content = await file.read()
                file_key = f"{username}/{uuid.uuid4()}-{file.filename}"
                s3_client.upload_fileobj(BytesIO(content), S3_BUCKET_NAME, file_key)
                return (
                    f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_key}"
                )
            return ""  # Return empty string if file not provided

        aadhaar_url = await upload_file(aadhaar_document, "aadhaar")
        caste_url = await upload_file(caste_document, "caste")
        school_cert_url = await upload_file(school_cert_document, "school_cert")
        school_mark_url = await upload_file(school_mark_document, "school_mark")
        uni_cert_url = await upload_file(uni_cert_document, "uni_cert")
        uni_mark_url = await upload_file(uni_mark_document, "uni_mark")
        passport_photo_url = await upload_file(passport_photo, "passport")
        signature_photo_url = await upload_file(signature_photo, "signature")

        # Validate institute exists
        institute = db.query(Institutes).filter(Institutes.id == institute_name).first()
        if not institute:
            raise CustomException(
                message="Invalid institute_name",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate course exists
        course = db.query(Courses).filter(Courses.id == course_interested).first()
        if not course:
            raise CustomException(
                message="Invalid course_interested",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate knowledge_id if provided
        if knowledge_id:
            knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
            if not knowledge:
                raise CustomException(
                    message="Invalid knowledge_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Hash password
        hashed_password = get_password_hash(password)

        # Create user in database
        try:
            user_data = {
                "username": username,
                "institute_name": institute_name,
                "course_interested": course_interested,
                "knowledge_id": knowledge_id,
                "phone_no": str(phone_no),  # Store as string for encryption
                "email": email,
                "password": hashed_password,
                "aadhaar_document": aadhaar_url,
                "caste_document": caste_url,
                "school_cert_document": school_cert_url,
                "school_mark_document": school_mark_url,
                "uni_cert_document": uni_cert_url,
                "uni_mark_document": uni_mark_url,
                "passport_photo": passport_photo_url,
                "signature_photo": signature_photo_url,
            }

            # Apply encryption to sensitive fields
            sensitive_data = {
                "phone": user_data.pop("phone_no"),
                "email": user_data.pop("email"),
            }
            encrypted_data = encrypt_applicant_info_data(sensitive_data)

            # Add back encrypted fields with correct keys
            user_data["phone_no"] = encrypted_data["phone"]
            user_data["email"] = encrypted_data["email"]

            # Print the user data for debugging
            logger.info(f"Attempting to create user with data: {user_data}")

            db_user = Users(**user_data)
            db.add(db_user)
            db.flush()  # Flush to get the user ID before committing

            # Create submission
            db_submission = Submissions(
                user_id=db_user.id, submission_id=submission_id, status="user created"
            )
            db.add(db_submission)

            # Commit both user and submission
            db.commit()
            db.refresh(db_user)
            db.refresh(db_submission)

            logger.info(f"Successfully created user with ID: {db_user.id}")

            # Dynamically count only the non-empty document URLs (six separate document fields)
            # uploaded_docs = [
            #     url for url in [
            #         db_user.aadhaar_document,
            #         db_user.caste_document,
            #         db_user.school_cert_document,
            #         db_user.school_mark_document,
            #         db_user.uni_cert_document,
            #         db_user.uni_mark_document,
            #     ] if url and url.strip() != ""
            # ]
            document_fields = {
                "aadhaar_document": "aadhaar",
                "caste_document": "caste",
                "school_cert_document": "school_cert",
                "school_mark_document": "school_mark",
                "uni_cert_document": "uni_cert",
                "uni_mark_document": "uni_mark",
            }

            uploaded_docs = []
            for field, doc_type in document_fields.items():
                url = getattr(db_user, field)
                if url and url.strip():
                    uploaded_docs.append(
                        (url, doc_type)
                    )  # Store as (URL, doc_type) tuples

            documents_uploaded = len(uploaded_docs)

            # Schedule extraction for each uploaded document (if any)
            if documents_uploaded > 0:
                background_tasks.add_task(
                    process_extraction, uploaded_docs, db_user.id, db_submission.id, db
                )

            # Build the response dictionary
            user_response_data = {
                "id": db_user.id,
                "username": db_user.username,
                "institute_name": db_user.institute_name,
                "course_interested": db_user.course_interested,
                "knowledge_id": db_user.knowledge_id,
                "phone_no": db_user.phone_no,  # Still encrypted at this point
                "email": db_user.email,  # Still encrypted
                "aadhaar_document": db_user.aadhaar_document,
                "caste_document": db_user.caste_document,
                "school_cert_document": db_user.school_cert_document,
                "school_mark_document": db_user.school_mark_document,
                "uni_cert_document": db_user.uni_cert_document,
                "uni_mark_document": db_user.uni_mark_document,
                "passport_photo": db_user.passport_photo,
                "signature_photo": db_user.signature_photo,
                "documents_uploaded": documents_uploaded,
                "submission_id": submission_id,
            }

            # Decrypt sensitive fields for response
            sensitive_response_fields = {
                "phone": user_response_data.pop("phone_no"),
                "email": user_response_data.pop("email"),
            }
            decrypted_fields = decrypt_applicant_info_data(sensitive_response_fields)

            # Add back decrypted fields with correct keys
            user_response_data["phone_no"] = decrypted_fields["phone"]
            user_response_data["email"] = decrypted_fields["email"]

            # Create response
            return UserResponse(**user_response_data)

        except Exception as e:
            db.rollback()
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise CustomException(
                message=f"Failed to create user in database: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    except CustomException as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise CustomException(
            message=f"Unexpected error occurred: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/users/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    # Query users with pagination
    users = db.query(Users).offset(skip).limit(limit).all()

    user_responses = []
    for user in users:
        # Fetch the related submission
        submission = (
            db.query(Submissions).filter(Submissions.user_id == user.id).first()
        )

        # Dynamically compute the count of uploaded document fields
        uploaded_docs = [
            doc
            for doc in [
                user.aadhaar_document,
                user.caste_document,
                user.school_cert_document,
                user.school_mark_document,
                user.uni_cert_document,
                user.uni_mark_document,
            ]
            if doc and doc.strip() != ""
        ]
        documents_uploaded = len(uploaded_docs)

        # Prepare user data for response
        user_data = {
            "id": user.id,
            "username": user.username,
            "institute_name": user.institute_name,
            "course_interested": user.course_interested,
            "knowledge_id": user.knowledge_id,
            "phone_no": user.phone_no,  # Still encrypted
            "email": user.email,  # Still encrypted
            # Individual document fields
            "aadhaar_document": user.aadhaar_document,
            "caste_document": user.caste_document,
            "school_cert_document": user.school_cert_document,
            "school_mark_document": user.school_mark_document,
            "uni_cert_document": user.uni_cert_document,
            "uni_mark_document": user.uni_mark_document,
            "passport_photo": user.passport_photo,
            "signature_photo": user.signature_photo,
            "documents_uploaded": documents_uploaded,
            "submission_id": submission.submission_id if submission else None,
        }

        # Decrypt sensitive fields
        sensitive_fields = {
            "phone": user_data.pop("phone_no"),
            "email": user_data.pop("email"),
        }
        decrypted_fields = decrypt_applicant_info_data(sensitive_fields)

        # Add back decrypted fields with correct keys
        user_data["phone_no"] = decrypted_fields["phone"]
        user_data["email"] = decrypted_fields["email"]

        # Construct each UserResponse
        user_responses.append(UserResponse(**user_data))

    return user_responses


@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    # Query the user
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Query the related submission
    submission = db.query(Submissions).filter(Submissions.user_id == user.id).first()

    # Dynamically compute the count of uploaded document fields
    uploaded_docs = [
        doc
        for doc in [
            user.aadhaar_document,
            user.caste_document,
            user.school_cert_document,
            user.school_mark_document,
            user.uni_cert_document,
            user.uni_mark_document,
        ]
        if doc and doc.strip() != ""
    ]
    documents_uploaded = len(uploaded_docs)

    # Prepare user data for response
    user_data = {
        "id": user.id,
        "username": user.username,
        "institute_name": user.institute_name,
        "course_interested": user.course_interested,
        "knowledge_id": user.knowledge_id,
        "phone_no": user.phone_no,  # Still encrypted
        "email": user.email,  # Still encrypted
        # Individual document fields
        "aadhaar_document": user.aadhaar_document,
        "caste_document": user.caste_document,
        "school_cert_document": user.school_cert_document,
        "school_mark_document": user.school_mark_document,
        "uni_cert_document": user.uni_cert_document,
        "uni_mark_document": user.uni_mark_document,
        "passport_photo": user.passport_photo,
        "signature_photo": user.signature_photo,
        "documents_uploaded": documents_uploaded,
        "submission_id": submission.submission_id if submission else None,
    }

    # Decrypt sensitive fields
    sensitive_fields = {
        "phone": user_data.pop("phone_no"),
        "email": user_data.pop("email"),
    }
    decrypted_fields = decrypt_applicant_info_data(sensitive_fields)

    # Add back decrypted fields with correct keys
    user_data["phone_no"] = decrypted_fields["phone"]
    user_data["email"] = decrypted_fields["email"]

    # Construct the response
    return UserResponse(**user_data)


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}


@app.get("/users/me", response_model=UserResponse)
def read_current_user(current_user: Users = Depends(get_current_user)):
    submission_id = (
        current_user.submissions[0].submission_id if current_user.submissions else None
    )
    return {
        "id": current_user.id,
        "username": current_user.username,
        "institute_name": current_user.institute_name,
        "course_interested": current_user.course_interested,
        "knowledge_id": current_user.knowledge_id,
        "phone_no": decrypt_field(current_user.phone_no),
        "email": decrypt_field(current_user.email),
        "aadhaar_document": current_user.aadhaar_document,
        "caste_document": current_user.caste_document,
        "school_cert_document": current_user.school_cert_document,
        "school_mark_document": current_user.school_mark_document,
        "uni_cert_document": current_user.uni_cert_document,
        "uni_mark_document": current_user.uni_mark_document,
        "passport_photo": current_user.passport_photo,
        "signature_photo": current_user.signature_photo,
        "submission_id": submission_id,
    }


@app.put("/users/me")
def update_current_user(
    phone_no: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if phone_no:
        current_user.phone_no = encrypt_field(phone_no)
    if email:
        current_user.email = encrypt_field(email)

    db.commit()
    db.refresh(current_user)

    return {"message": "User info updated successfully"}


@app.put("/users/{user_id}/update-photos", response_model=UserResponse)
async def update_user_photos(
    user_id: int,
    passport_photo: Optional[UploadFile] = File(None),
    signature_photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Update or reupload passport photo and signature photo for a given user.
    """
    # Fetch the existing user
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    username = db_user.username  # Keep the same folder structure in S3

    try:
        # Upload new passport photo if provided
        if passport_photo:
            passport_photo_content = await passport_photo.read()
            passport_photo_key = f"{username}/{uuid.uuid4()}-{passport_photo.filename}"
            s3_client.upload_fileobj(
                BytesIO(passport_photo_content), S3_BUCKET_NAME, passport_photo_key
            )
            passport_photo_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{passport_photo_key}"
            db_user.passport_photo = passport_photo_url  # Update in DB

        # Upload new signature photo if provided
        if signature_photo:
            signature_photo_content = await signature_photo.read()
            signature_photo_key = (
                f"{username}/{uuid.uuid4()}-{signature_photo.filename}"
            )
            s3_client.upload_fileobj(
                BytesIO(signature_photo_content), S3_BUCKET_NAME, signature_photo_key
            )
            signature_photo_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{signature_photo_key}"
            db_user.signature_photo = signature_photo_url  # Update in DB

        # Commit the updates to the database
        db.commit()
        db.refresh(db_user)

        # Dynamically compute the count of uploaded document fields
        uploaded_docs = [
            doc
            for doc in [
                db_user.aadhaar_document,
                db_user.caste_document,
                db_user.school_cert_document,
                db_user.school_mark_document,
                db_user.uni_cert_document,
                db_user.uni_mark_document,
            ]
            if doc and doc.strip() != ""
        ]
        documents_uploaded = len(uploaded_docs)

        # Get user data for response
        user_response_data = {
            "id": db_user.id,
            "username": db_user.username,
            "institute_name": db_user.institute_name,
            "course_interested": db_user.course_interested,
            "knowledge_id": db_user.knowledge_id,
            "phone_no": db_user.phone_no,  # Still encrypted
            "email": db_user.email,  # Still encrypted
            # Individual document fields
            "aadhaar_document": db_user.aadhaar_document,
            "caste_document": db_user.caste_document,
            "school_cert_document": db_user.school_cert_document,
            "school_mark_document": db_user.school_mark_document,
            "uni_cert_document": db_user.uni_cert_document,
            "uni_mark_document": db_user.uni_mark_document,
            "passport_photo": db_user.passport_photo,
            "signature_photo": db_user.signature_photo,
            "documents_uploaded": documents_uploaded,
            "submission_id": (
                db_user.submissions.submission_id if db_user.submissions else None
            ),
        }
        # Decrypt sensitive fields for response
        sensitive_response_fields = {
            "phone": user_response_data.pop("phone_no"),
            "email": user_response_data.pop("email"),
        }
        decrypted_fields = decrypt_applicant_info_data(sensitive_response_fields)
        # Add back decrypted fields with correct keys
        user_response_data["phone_no"] = decrypted_fields["phone"]
        user_response_data["email"] = decrypted_fields["email"]
        # Create response
        return UserResponse(**user_response_data)

    except Exception as e:
        print(f"Error updating photos: {e}")
        raise HTTPException(status_code=500, detail="Error updating user photos")


@app.post("/classifieddocuments/", response_model=ClassifiedDocumentResponse)
def create_classified_document(
    classified_document: ClassifiedDocumentBase, db: Session = Depends(get_db)
):
    # # Assuming the user ID is passed with the request (e.g., in headers or as part of the body)
    # user_id = classified_document.user_id  # Ensure you validate this input before use

    # Ensure the user exists
    db_user = db.query(Users).filter(Users.id == classified_document.user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create new ClassifiedDocument object using 'document_type'
    db_classified_document = ClassifiedDocuments(
        user_id=classified_document.user_id,
        file_name=classified_document.file_name,
        document_type=classified_document.document_type,  # renamed field
        confidence=classified_document.confidence,
    )
    db.add(db_classified_document)
    db.commit()
    db.refresh(db_classified_document)
    print("data is added")
    return db_classified_document


# FastAPI endpoint to fetch classified documents
@app.get("/classifieddocuments/", response_model=List[ClassifiedDocumentResponse])
def get_classified_documents_by_user(user_id: int, db: Session = Depends(get_db)):
    """
    Endpoint to retrieve classified documents (now with document_type) for a specific user.
    """
    # Fetch documents associated with the provided user_id
    classified_docs = (
        db.query(ClassifiedDocuments)
        .filter(ClassifiedDocuments.user_id == user_id)
        .all()
    )

    if not classified_docs:
        raise HTTPException(
            status_code=404, detail="No classified documents found for the given user."
        )

    # Return classified documents with required fields in response model format
    return [
        ClassifiedDocumentResponse(
            id=doc.id,
            user_id=doc.user_id,
            file_name=doc.file_name,
            document_type=doc.document_type,
            confidence=doc.confidence,
        )
        for doc in classified_docs
    ]


@app.post("/classify/")
async def classify_files(
    request: ClassifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Endpoint to extract data from documents using the custom data_extractor module.
    For each URL provided, the endpoint downloads the file, determines the document type,
    extracts and processes its data, and stores the result.
    """
    urls = request.urls
    user_id = request.user_id

    if not urls:
        raise HTTPException(status_code=400, detail="No URLs provided.")

    # Validate that the user exists
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch or create a submission entry
    db_submission = db.query(Submissions).filter(Submissions.user_id == user_id).first()
    if not db_submission:
        db_submission = Submissions(user_id=user_id, status="pending")
        db.add(db_submission)
        db.commit()
        db.refresh(db_submission)

    # Schedule the extraction process as a background task
    background_tasks.add_task(process_extraction, urls, user_id, db_submission.id, db)

    return {
        "message": "Extraction scheduled successfully.",
        "submission_id": db_submission.id,
    }


def process_applicant_info(user_id: int, db: Session):
    """
    Create an applicantinfo entry using data from Users and ApplicantDocuments.
    """
    try:
        # Fetch the user
        user = db.query(models.Users).filter(models.Users.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Decrypt user data
        user_data = {
            "phone_no": decrypt_field(user.phone_no),
            "email": decrypt_field(user.email),
            "passport_photo": user.passport_photo,
            "signature_photo": user.signature_photo,
        }

        # Fetch institute and course names
        institute = (
            db.query(models.Institutes)
            .filter(models.Institutes.id == user.institute_name)
            .first()
        )
        course = (
            db.query(models.Courses)
            .filter(models.Courses.id == user.course_interested)
            .first()
        )
        knowledge = (
            db.query(models.Knowledge)
            .filter(models.Knowledge.id == user.knowledge_id)
            .first()
        )

        # Fetch and aggregate data from ApplicantDocuments
        applicant_docs = (
            db.query(models.ApplicantDocuments)
            .filter(models.ApplicantDocuments.user_id == user_id)
            .all()
        )

        applicant_details = {}
        academic_records = {
            "class_ten": {},
            "class_twelve": {},
            "graduation": {},
        }

        for doc in applicant_docs:
            doc_type = doc.doc_type
            extracted_content = doc.extracted_content.get("data", {})
            # Decrypt extracted data if encrypted
            extracted_data = decrypt_applicant_info_data(extracted_content)

            if doc_type in ["class10cbse", "class10board"]:
                applicant_details.update(
                    {
                        "father_name": extracted_data.get("father_name", ""),
                        "mother_name": extracted_data.get("mother_name", ""),
                    }
                )
                academic_records["class_ten"] = {
                    "board": extracted_data.get("board", ""),
                    "examination_name": extracted_data.get("exam_name", ""),
                    "marks_obtained": extracted_data.get("marks", ""),
                    "division": extracted_data.get("division", ""),
                    "passout": extracted_data.get("passout", ""),
                }
            elif doc_type in ["class12cbse", "class12board"]:
                academic_records["class_twelve"] = {
                    "board": extracted_data.get("board", ""),
                    "examination_name": extracted_data.get("exam_name", ""),
                    "marks_obtained": extracted_data.get("marks", ""),
                    "division": extracted_data.get("division", ""),
                    "passout": extracted_data.get("passout", ""),
                }
            elif doc_type == "graduatemarksheet":
                academic_records["graduation"] = {
                    "university_name": extracted_data.get("university_name", ""),
                    "degree": extracted_data.get("degree", ""),
                    "passout": extracted_data.get("passout", ""),
                    "division": extracted_data.get("division", ""),
                    "obtained_marks": extracted_data.get("obtained_mark", ""),
                }
            elif doc_type == "aadhaar":
                applicant_details.update(
                    {
                        "name": extracted_data.get("name", ""),
                        "gender": extracted_data.get("gender", ""),
                        "dob": extracted_data.get("dob", ""),
                        "address": extracted_data.get("address", ""),
                        "aadhaar_number": extracted_data.get("aadhaarno", ""),
                        "permanent_address": extracted_data.get("address", ""),
                    }
                )

        # Prepare the payload
        applicant_info_payload = {
            "user_id": user_id,
            "institute_names": institute.institute_names if institute else "",
            "course_name": course.course_name if course else "",
            "name": applicant_details.get("name", ""),
            "father_name": applicant_details.get("father_name", ""),
            "mother_name": applicant_details.get("mother_name", ""),
            "gender": applicant_details.get("gender", ""),
            "dob": applicant_details.get("dob", ""),
            "category": applicant_details.get("category", ""),
            "occupation": None,
            "address": applicant_details.get("address", ""),
            "permanent_address": applicant_details.get("permanent_address", ""),
            "phone": (
                int(user_data["phone_no"]) if user_data["phone_no"].isdigit() else None
            ),
            "mobile": (
                int(user_data["phone_no"]) if user_data["phone_no"].isdigit() else None
            ),
            "examination_details": academic_records,
            "aadhaar_number": applicant_details.get("aadhaar_number") or None,
            "email": user_data["email"],
            "computer_knowledge": knowledge.knowledge_in if knowledge else "",
            "signature_filename": user_data["signature_photo"],
            "thumb_filename": None,
            "photograph_filename": user_data["passport_photo"],
        }

        # Encrypt sensitive fields
        encrypted_payload = encrypt_applicant_info_data(applicant_info_payload)

        # Create the applicant info entry directly
        db_applicant_info = models.Applicant_Information(**encrypted_payload)
        db.add(db_applicant_info)
        db.commit()
        db.refresh(db_applicant_info)

        # Update submission status
        db_submission = (
            db.query(models.Submissions)
            .filter(models.Submissions.user_id == user_id)
            .first()
        )
        if db_submission:
            db_submission.status = "Completed creating applicant info."
            db.commit()

        logger.info(f"Applicant info successfully created for user_id: {user_id}")

    except Exception as e:
        logger.error(f"Error in process_applicant_info: {str(e)}")
        raise


def process_extraction(urls, user_id, submission_id, db: Session):
    """
    Process extraction tasks in the background using the custom data_extractor.
    For each URL, download the file, determine the document type, extract and post-process the data,
    then save the result in ApplicantDocuments.
    """
    try:
        db_submission = (
            db.query(Submissions).filter(Submissions.id == submission_id).first()
        )
        db_submission.status = "extracting..."
        db.commit()
        db.refresh(db_submission)

        for url, doc_type in urls:
            try:
                # Fetch the file content from the URL
                response = requests.get(url)
                if response.status_code != 200:
                    raise ValueError(f"Failed to fetch the file from {url}")

                file_content = response.content
                file_stream = BytesIO(file_content)

                # Determine document type from the URL filename (simple heuristic)
                # lower_url = url.lower()
                # if "aadhaar" in lower_url:
                #     document_type = "aadhaar"
                # elif "caste" in lower_url:
                #     document_type = "caste"
                # elif "school_cert" in lower_url:
                #     document_type = "school_cert"
                # elif "school_mark" in lower_url:
                #     document_type = "school_mark"
                # elif "uni_cert" in lower_url:
                #     document_type = "uni_cert"
                # elif "uni_mark" in lower_url:
                #     document_type = "uni_mark"
                # else:
                #     document_type = "unknown"

                # Use the custom data_extractor module instead of Azure extraction
                extracted_data = data_extractor(file_stream, doc_type)
                # Check for extraction errors
                if "error" in extracted_data:
                    logger.error(
                        f"Extraction failed for {url}: {extracted_data['error']}"
                    )
                    continue

                # Run post-processing as before
                processed_data = process_extracted_data(extracted_data, doc_type)

                # *** Encrypt sensitive fields before saving ***
                encrypted_data = encrypt_applicant_info_data(processed_data)

                formatted_data = {
                    "document_type": doc_type,
                    "data": encrypted_data,
                    "metadata": {"file_url": url, "user_id": user_id},
                }

                # Save extracted data into ApplicantDocuments
                new_entry = ApplicantDocuments(
                    user_id=user_id,
                    file_name=url,
                    doc_type=doc_type,
                    extracted_content=formatted_data,
                )
                db.add(new_entry)
                db.commit()
                db.refresh(new_entry)

                db_submission.status = f"Extracted data for {doc_type}"
                db.commit()
                db.refresh(db_submission)

                # Store unencrypted data for the applicant info API
                # Note: We'll encrypt it just before sending
                # extracted_applicant_data.update(processed_data)

                logger.info(f"Completed extraction for {doc_type}: {processed_data}")

            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}")

        db_submission.status = "Completed Extracting for all documents"
        db.commit()
        db.refresh(db_submission)

        try:
            process_applicant_info(user_id=user_id, db=db)
            logger.info("Applicant info successfully updated.")

        except Exception as e:
            logger.error(f"Error calling applicant info API: {str(e)}")

    except Exception as e:
        logger.error(f"Error in background classification task: {str(e)}")

        if db_submission:
            db_submission.status = f"Failed: {str(e)}"
            db.commit()
            db.refresh(db_submission)


@app.post("/applicantinfo/", response_model=ApplicantInfoCreate)
def create_applicant_info(
    applicant: ApplicantInfoCreate, db: Session = Depends(get_db)
):
    # Check if the user exists before saving the applicant info
    user = db.query(models.Users).filter(models.Users.id == applicant.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert Pydantic model to dict and encrypt sensitive fields
    applicant_data = encrypt_applicant_info_data(applicant.dict())

    # Create the new Applicant Information
    db_applicant_info = models.Applicant_Information(**applicant_data)

    # Add the new applicant info to the session and commit
    db.add(db_applicant_info)
    db.commit()
    db.refresh(db_applicant_info)

    # Fetch or create a submission entry
    db_submission = db.query(Submissions).filter(Submissions.user_id == user.id).first()
    if not db_submission:
        db_submission = Submissions(
            user_id=user.id, status="Applicant Information sucessfully updated"
        )
        db.add(db_submission)
        db.commit()
        db.refresh(db_submission)

    # Convert the db object to a dict and then decrypt sensitive fields for the response.
    response_data = {
        col.name: getattr(db_applicant_info, col.name)
        for col in db_applicant_info.__table__.columns
    }
    response_data = decrypt_applicant_info_data(response_data)

    return response_data


@app.put("/applicantinfo/{user_id}/", response_model=ApplicantInfoCreate)
def update_applicant_info(
    user_id: int, applicant: ApplicantInfoCreate, db: Session = Depends(get_db)
):
    """
    Update applicant information for a given user and mark submission status as updated.
    """
    # Fetch the existing applicant information
    db_applicant_info = (
        db.query(models.Applicant_Information)
        .filter(models.Applicant_Information.user_id == user_id)
        .first()
    )

    if not db_applicant_info:
        raise HTTPException(status_code=404, detail="Applicant information not found")

    # Encrypt sensitive fields before updating
    update_data = encrypt_applicant_info_data(applicant.dict(exclude_unset=True))

    # Update fields with the new values
    update_fields = [
        "institute_names",
        "course_name",
        "name",
        "father_name",
        "mother_name",
        "gender",
        "dob",
        "category",
        "occupation",
        "phone",
        "mobile",
        "address",
        "permanent_address",
        "examination_details",
        "aadhaar_number",
        "email",
        "computer_knowledge",
        "signature_filename",
        "thumb_filename",
        "photograph_filename",
    ]

    for field in update_fields:
        if field in update_data:
            setattr(db_applicant_info, field, update_data[field])

    # Commit the updates
    db.commit()
    db.refresh(db_applicant_info)

    # Update the submission status
    db_submission = db.query(Submissions).filter(Submissions.user_id == user_id).first()
    if not db_submission:
        # If no submission exists, create a new one
        db_submission = models.Submissions(
            user_id=user_id, status="Application information updated"
        )
        db.add(db_submission)
    else:
        # Update the status of the existing submission
        db_submission.status = "Application information updated"

    db.commit()
    db.refresh(db_submission)

    # Prepare response by decrypting sensitive fields
    response_data = {
        col.name: getattr(db_applicant_info, col.name)
        for col in db_applicant_info.__table__.columns
    }
    response_data = decrypt_applicant_info_data(response_data)

    # Return the updated applicant information
    return response_data


@app.put("/applicantinfo/{user_id}/partial-update", response_model=dict)
def update_applicant_partial_info(
    user_id: int, applicant: ApplicantPartialUpdate, db: Session = Depends(get_db)
):
    """
    Update only examination details and address for a given user and mark submission status as updated.
    Show previous values before updating.
    """
    # Fetch the existing applicant information
    db_applicant_info = (
        db.query(models.Applicant_Information)
        .filter(models.Applicant_Information.user_id == user_id)
        .first()
    )

    if not db_applicant_info:
        raise HTTPException(status_code=404, detail="Applicant information not found")

    # Store previous values for reference
    previous_values = {
        "examination_details": db_applicant_info.examination_details,
        "address": db_applicant_info.address,
        "permanent_address": db_applicant_info.permanent_address,
    }
    # Decrypt for previous values
    previous_values = decrypt_applicant_info_data(previous_values)

    # Update only the required fields
    if applicant.examination_details is not None:
        db_applicant_info.examination_details = encrypt_field(
            str(applicant.examination_details)
        )
    if applicant.address is not None:
        db_applicant_info.address = encrypt_field(applicant.address)
    if applicant.permanent_address is not None:
        db_applicant_info.permanent_address = encrypt_field(applicant.permanent_address)

    # Commit the updates
    db.commit()
    db.refresh(db_applicant_info)

    # Update the submission status
    db_submission = (
        db.query(models.Submissions)
        .filter(models.Submissions.user_id == user_id)
        .first()
    )
    if not db_submission:
        db_submission = models.Submissions(
            user_id=user_id, status="Examination details and address updated"
        )
        db.add(db_submission)
    else:
        db_submission.status = "Examination details and address updated"

    db.commit()
    db.refresh(db_submission)

    # Get updated values (decrypted)
    updated_values = {
        "examination_details": db_applicant_info.examination_details,
        "address": db_applicant_info.address,
        "permanent_address": db_applicant_info.permanent_address,
    }
    updated_values = decrypt_applicant_info_data(updated_values)

    # Return both previous and updated values
    return {
        "previous_values": previous_values,
        "updated_values": updated_values,
    }


def format_user_response(user):
    # Initialize applicant details and academic records
    applicant_details = {}

    academic_records = {
        "class_ten": {},
        "class_twelve": {},
        "graduation": {},
    }

    # Process applicant documents and extract details
    for doc in user.applicant_documents:
        doc_type = doc.doc_type
        extracted_content = doc.extracted_content

        # Extract Class 10 data
        if doc_type in ["class10cbse", "class10board"]:
            extracted = extracted_content.get("data", {})
            applicant_details.update(
                {
                    "father_name": extracted.get("father_name"),
                    "mother_name": extracted.get("mother_name"),
                }
            )
            academic_records["class_ten"] = {
                "board": extracted.get("board"),
                "examination_name": extracted.get("exam_name"),
                "marks_obtained": extracted.get("marks"),
                "division": extracted.get("division"),
                "passout": extracted.get("passout"),
            }

        # Extract Class 12 data
        elif doc_type in ["class12cbse", "class12board"]:
            extracted = extracted_content.get("data", {})
            academic_records["class_twelve"] = {
                "board": extracted.get("board"),
                "examination_name": extracted.get("exam_name"),
                "marks_obtained": extracted.get("marks"),
                "division": extracted.get("division"),
                "passout": extracted.get("passout"),
            }

        # Extract Graduation data
        elif doc_type == "graduatemarksheet":
            extracted = extracted_content.get("data", {})
            academic_records["graduation"] = {
                "university_name": extracted.get("university_name"),
                "degree": extracted.get("degree"),
                "passout": extracted.get("passout"),
                "division": extracted.get("division"),
                "obtained_marks": extracted.get("obtained_mark"),
            }

        # Extract Aadhaar data
        elif doc_type == "aadhaar":
            aadhaar_content = extracted_content.get("data", {})
            applicant_details.update(
                {
                    "name": aadhaar_content.get("name"),
                    "gender": aadhaar_content.get("gender"),
                    "dob": aadhaar_content.get("dob"),
                    "phone": user.phone_no,
                    "address": aadhaar_content.get("address"),
                    "aadhaar_number": aadhaar_content.get("aadhaarno"),
                    "permanent_address": aadhaar_content.get("address"),
                    "category": None,  # Assuming no category is available
                }
            )

    # Prepare the docs field with count
    docs = [
        {
            "doc_type": doc.document_type,
            "url": doc.file_name,
        }
        for doc in user.classified_documents
    ]

    docs_count = len(docs)  # Calculate the count of documents

    # Build documents from separate fields instead of a generic all_documents field
    documents = {
        "aadhaar_document": user.aadhaar_document,
        "caste_document": user.caste_document,
        "school_cert_document": user.school_cert_document,
        "school_mark_document": user.school_mark_document,
        "uni_cert_document": user.uni_cert_document,
        "uni_mark_document": user.uni_mark_document,
    }

    # Build the final formatted response
    formatted_response = {
        "applicant_details": applicant_details,
        "email": user.email,
        "mobile": user.phone_no,
        "passport_photo": user.passport_photo,
        "signature_photo": user.signature_photo,
        "institute_name": user.institute.institute_names if user.institute else None,
        "course_interested": user.course.course_name if user.course else None,
        "knowledge": user.knowledge.knowledge_in if user.knowledge else None,
        "academic_records": academic_records,
        "all_documents": {
            "docs": docs,  # Docs array
            "count": docs_count,  # Count field
        },
        "documents": documents,
    }

    return formatted_response


@app.get("/get_all_applicants/", response_model=List[dict])
def get_all_applicants(db: Session = Depends(get_db)):
    """
    Retrieve the first 20 applicant records along with related documents.
    """

    # Query the first 20 applicants
    applicants = db.query(models.Applicant_Information).limit(20).all()

    if not applicants:
        raise HTTPException(status_code=404, detail="No applicants found")

    response_list = []

    for applicant_info in applicants:
        user = (
            db.query(models.Users)
            .filter(models.Users.id == applicant_info.user_id)
            .first()
        )
        if not user:
            continue  # Skip if user record not found

        documents = {
            "aadhaar_document": user.aadhaar_document,
            "caste_document": user.caste_document,
            "school_cert_document": user.school_cert_document,
            "school_mark_document": user.school_mark_document,
            "uni_cert_document": user.uni_cert_document,
            "uni_mark_document": user.uni_mark_document,
        }

        # Get applicant info as dict
        applicant_dict = {
            col.name: getattr(applicant_info, col.name)
            for col in applicant_info.__table__.columns
        }
        # Decrypt sensitive fields
        applicant_dict = decrypt_applicant_info_data(applicant_dict)

        response_list.append(
            {
                "applicant_info": applicant_dict,
                "documents": documents,
            }
        )

    return response_list


@app.get("/applicant_details/{user_id}", response_model=ApplicantInfoCreate)
def get_applicant_details(user_id: int, db: Session = Depends(get_db)):
    applicant = (
        db.query(models.Applicant_Information)
        .filter(models.Applicant_Information.user_id == user_id)
        .first()
    )
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant information not found")

    response_data = {
        col.name: getattr(applicant, col.name) for col in applicant.__table__.columns
    }
    return decrypt_applicant_info_data(response_data)


@app.get("/get_applicant_info/{user_id}/", response_model=dict)
def get_applicant_info(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieve applicant information and related documents for a given user ID.
    """
    # Query the Applicant_Information table
    applicant_info = (
        db.query(models.Applicant_Information)
        .filter(models.Applicant_Information.user_id == user_id)
        .first()
    )

    if not applicant_info:
        raise HTTPException(status_code=404, detail="Applicant information not found")

    # Get applicant info as dict and decrypt sensitive fields
    applicant_dict = {
        col.name: getattr(applicant_info, col.name)
        for col in applicant_info.__table__.columns
    }
    applicant_dict = decrypt_applicant_info_data(applicant_dict)

    # Query the ApplicantDocuments table
    applicant_documents = (
        db.query(models.ApplicantDocuments)
        .filter(models.ApplicantDocuments.user_id == user_id)
        .all()
    )

    # Build the JSON response
    response = {
        "applicant_info": applicant_dict,
        "documents": [
            {
                "id": doc.id,
                "file_name": doc.file_name,
                "doc_type": doc.doc_type,
            }
            for doc in applicant_documents
        ],
    }

    return response


@app.get("/get_applicant_info_by_course/{course_name}", response_model=list)
def read_applicant_info(course_name: str, db: Session = Depends(get_db)):
    """
    Retrieve all applicants for a given course name.
    """
    db_applicant_info = (
        db.query(models.Applicant_Information)
        .filter(models.Applicant_Information.course_name == course_name)
        .all()
    )

    if not db_applicant_info:
        raise HTTPException(
            status_code=404, detail="No applicants found for the given course name"
        )

    result = []
    for applicant in db_applicant_info:
        # Get as dict and decrypt sensitive fields
        applicant_dict = {
            col.name: getattr(applicant, col.name)
            for col in applicant.__table__.columns
        }
        applicant_dict = decrypt_applicant_info_data(applicant_dict)
        result.append(applicant_dict)

    return result


@app.get("/submission/by-user/{user_id}/", response_model=SubmissionResponse)
def get_submission_by_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get the submission status for a given user ID.
    """
    db.expire_all()  # Force SQLAlchemy to load fresh data from the database
    db_submission = db.query(Submissions).filter(Submissions.user_id == user_id).first()

    if not db_submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return SubmissionResponse.from_orm(db_submission)


@app.get("/submission/by-id/{submission_id}/", response_model=SubmissionResponse)
def get_submission_by_id(submission_id: str, db: Session = Depends(get_db)):
    """
    Get the submission status for a given submission ID.
    """
    db_submission = (
        db.query(Submissions).filter(Submissions.submission_id == submission_id).first()
    )

    if not db_submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return SubmissionResponse.from_orm(db_submission)


@app.get("/submissions/{submission_id}/status")
async def get_submission_status(submission_id: str, db: Session = Depends(get_db)):
    submission = (
        db.query(Submissions).filter(Submissions.submission_id == submission_id).first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"status": submission.status}


# ===== Text Review System Endpoints =====#


# initialize admin (onlu on first time running)
@app.post("/initialize-data")
async def initialize_data(db: Session = Depends(get_db)):
    # Create default user if not exists
    if not db.query(ReviewUser).first():
        default_user = ReviewUser(
            username=os.getenv("REVIEWER_USER_NAME"),
            hashed_password=get_password_hash(os.getenv("REVIEWER_USER_PASSWORD")),
        )
        db.add(default_user)
        db.commit()
    return {"message": "Initial data created"}


# --- Auth Endpoints ---
@app.post("/reviewer-token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = (
        db.query(ReviewUser).filter(ReviewUser.username == form_data.username).first()
    )
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# --- Categories Endpoints ---
@app.get("/categories/")
async def get_categories(
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    """Get unique document types from ApplicantDocuments"""
    categories = db.query(distinct(models.ApplicantDocuments.doc_type)).all()
    return [{"name": cat[0]} for cat in categories]


# Update reviewed field
@app.put("/review/document/{doc_id}/update")
async def update_fields(
    doc_id: int,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    document = (
        db.query(models.ApplicantDocuments)
        .filter(models.ApplicantDocuments.id == doc_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Get current content
        content = (
            document.extracted_content
            if isinstance(document.extracted_content, dict)
            else json.loads(document.extracted_content)
        )

        # Ensure 'data' exists in content
        if "data" not in content:
            content["data"] = {}

        # Get existing data and decrypt if needed
        existing_data = content.get("data", {})
        decrypted_data = decrypt_applicant_info_data(existing_data)

        # Apply updates to decrypted data
        decrypted_data.update(updates)

        # Re-encrypt updated data
        encrypted_data = encrypt_applicant_info_data(decrypted_data)

        # Update content with encrypted data
        content["data"] = encrypted_data

        # Update the document
        document.extracted_content = content
        document.is_reviewed = True

        db.commit()
        db.refresh(document)

        return {"message": "Fields updated successfully", "updated_content": content}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating fields: {str(e)}")


# --- Documents Endpoints ---
@app.get("/documents/{doc_type}")
async def get_documents(
    doc_type: str,
    reviewed: bool = False,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    query = db.query(models.ApplicantDocuments).filter(
        models.ApplicantDocuments.doc_type == doc_type,
        models.ApplicantDocuments.is_reviewed == reviewed,
    )

    docs = query.all()

    result = []
    for doc in docs:
        try:
            content = (
                doc.extracted_content
                if isinstance(doc.extracted_content, dict)
                else json.loads(doc.extracted_content)
            )
            image_url = content.get("metadata", {}).get("file_url", doc.file_name)

            # Decrypt data if present
            data = content.get("data", {})
            if data:
                data = decrypt_applicant_info_data(data)

            entries = [
                {"field_name": key, "field_value": value} for key, value in data.items()
            ]

            result.append(
                {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "image_url": image_url,
                    "entries": entries,
                    "is_reviewed": doc.is_reviewed,
                }
            )
        except Exception as e:
            print(f"Error processing document {doc.id}: {str(e)}")
            continue

    return result


@app.get("/document/{document_id}/entries")
async def get_document_entries(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    """Get entries for a specific document from its extracted_content."""
    document = (
        db.query(models.ApplicantDocuments)
        .filter(models.ApplicantDocuments.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Parse the extracted_content (which are stored as a JSON string)
    try:
        content = (
            json.loads(document.extracted_content)
            if isinstance(document.extracted_content, str)
            else document.extracted_content
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in extracted_content")

    # Get the 'data' dictionary and decrypt if present
    data = content.get("data", {})
    if data:
        data = decrypt_applicant_info_data(data)

    # Build entries array
    entries = [{"field_name": key, "field_value": value} for key, value in data.items()]

    return entries


@app.get("/document/{document_id}/next")
async def get_next_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    """Get next document of the same type"""
    current_doc = db.query(models.ApplicantDocuments).get(document_id)
    if not current_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    next_doc = (
        db.query(models.ApplicantDocuments)
        .filter(
            models.ApplicantDocuments.doc_type == current_doc.doc_type,
            models.ApplicantDocuments.id > document_id,
        )
        .order_by(models.ApplicantDocuments.id)
        .first()
    )

    if not next_doc:
        return {"message": "No more documents", "document": None}
    # Use extracted_content for image_url and assume reviews if available (or empty list otherwise)
    image_url = (
        next_doc.extracted_content.get("metadata", {}).get("file_url")
        if isinstance(next_doc.extracted_content, dict)
        else next_doc.file_name
    )
    reviews = next_doc.reviews if hasattr(next_doc, "reviews") else []

    return {
        "document": {
            "id": next_doc.id,
            "file_name": next_doc.file_name,
            "image_url": image_url,
            "entries": [
                {
                    "id": review.id,
                    "field_name": review.field_name,
                    "field_value": review.reviewed_value,
                    "is_reviewed": review.is_reviewed,
                }
                for review in reviews
            ],
        }
    }


@app.get("/document/{document_id}/previous")
async def get_previous_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    """Get previous document of the same type"""
    current_doc = db.query(models.ApplicantDocuments).get(document_id)
    if not current_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    prev_doc = (
        db.query(models.ApplicantDocuments)
        .filter(
            models.ApplicantDocuments.doc_type == current_doc.doc_type,
            models.ApplicantDocuments.id < document_id,
        )
        .order_by(models.ApplicantDocuments.id.desc())
        .first()
    )

    if not prev_doc:
        return {"message": "No previous documents", "document": None}

    image_url = (
        prev_doc.extracted_content.get("metadata", {}).get("file_url")
        if isinstance(prev_doc.extracted_content, dict)
        else prev_doc.file_name
    )
    reviews = prev_doc.reviews if hasattr(prev_doc, "reviews") else []
    return {
        "document": {
            "id": prev_doc.id,
            "file_name": prev_doc.file_name,
            "image_url": image_url,
            "entries": [
                {
                    "id": review.id,
                    "field_name": review.field_name,
                    "field_value": review.reviewed_value,
                    "is_reviewed": review.is_reviewed,
                }
                for review in reviews
            ],
        }
    }


# Download Reviewed Data
@app.get("/download-category/{category_id}")
async def download_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: ReviewUser = Depends(get_current_user),
):
    try:
        from app.download_utils import create_category_zip

        # Generate zip file
        zip_data = create_category_zip(category_id, db)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{category_id}_reviewed_{timestamp}.zip"

        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


## ========================================================== ##


# Custom Exception handling and GLobal Exception handling
class CustomException(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code


@app.exception_handler(CustomException)
async def custom_exception_handler(request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message, "detail": exc.message},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "An unexpected error occurred",
            "detail": str(exc) if str(exc) else "Unknown error",
        },
    )
