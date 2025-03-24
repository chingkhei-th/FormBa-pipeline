from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Dict, Optional, Any
from datetime import datetime


## 1. Formba main Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class CoursesBase(BaseModel):
    course_name: str
    institute_id: int


class CoursesResponse(CoursesBase):
    id: int

    class Config:
        from_attributes = True


class InstitutesBase(BaseModel):
    institute_names: str


class InstitutesResponse(InstitutesBase):
    id: int
    courses: List[CoursesResponse] = []  # Nested response

    class Config:
        from_attributes = True


class KnowledgeBase(BaseModel):
    knowledge_in: str


class KnowledgeResponse(KnowledgeBase):
    id: int

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    institute_name: int
    course_interested: int
    knowledge_id: Optional[int]
    phone_no: str
    email: EmailStr
    # password: str

    # Individual document fields replacing all_documents
    aadhaar_document: str
    caste_document: Optional[str] = None
    school_cert_document: Optional[str] = None
    school_mark_document: Optional[str] = None
    uni_cert_document: Optional[str] = None
    uni_mark_document: Optional[str] = None

    passport_photo: str
    signature_photo: str

    @field_validator("phone_no")
    def validate_phone_no(cls, v):
        if not str(v).isdigit() or len(str(v)) != 10:
            raise ValueError("Phone number must be 10 digits")
        return v


class UserResponse(UserBase):
    id: int
    documents_uploaded: int
    submission_id: str  # Add submission_id field

    class Config:
        orm_mode = True


class Classification(BaseModel):
    type: str
    confidence: float


class ClassifiedDocumentBase(BaseModel):
    file_name: str
    classifications: List[Classification]


class ClassifiedDocumentResponse(BaseModel):
    id: int
    user_id: int
    file_name: str
    document_type: str
    confidence: float

    class Config:
        from_attributes = True


class ApplicantInfoCreate(BaseModel):
    institute_names: str
    course_name: str
    name: str
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    category: Optional[str] = None
    occupation: Optional[str] = None
    phone: Optional[int] = None
    mobile: Optional[int] = None
    address: Optional[str] = None
    permanent_address: Optional[str] = None
    examination_details: Optional[dict] = None
    aadhaar_number: Optional[str] = None
    email: Optional[str] = None
    computer_knowledge: Optional[str] = None
    signature_filename: Optional[str] = None
    thumb_filename: Optional[str] = None
    photograph_filename: Optional[str] = None
    user_id: int  # This would be the ID of the user associated with the applicant

    class Config:
        orm_mode = True


class ClassifyRequest(BaseModel):
    user_id: int
    urls: List[str]


class ApplicantPartialUpdate(BaseModel):
    examination_details: Optional[dict] = None
    address: Optional[str] = None
    permanent_address: Optional[str] = None


class SubmissionResponse(BaseModel):
    user_id: int
    submission_id: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """
        Custom ORM serializer to handle datetime fields.
        """
        return cls(
            user_id=obj.user_id,
            submission_id=obj.submission_id,
            status=obj.status,
            created_at=obj.created_at.isoformat() if obj.created_at else None,
            updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
        )


## 2. Document Review Schemas
class ReviewUserBase(BaseModel):
    username: str


class ReviewUserCreate(ReviewUserBase):
    password: str


class ReviewUser(ReviewUserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EntryUpdate(BaseModel):
    field_value: str


class DocumentReviewBase(BaseModel):
    field_name: str
    field_value: str
    is_reviewed: bool = False


class DocumentReview(DocumentReviewBase):
    id: int
    doc_id: int
    reviewer_id: int
    original_value: str
    reviewed_value: str
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    name: str


class DocumentEntry(BaseModel):
    id: int
    field_name: str
    field_value: str
    is_reviewed: bool


class DocumentResponse(BaseModel):
    id: int
    file_name: str
    image_url: str
    entries: List[DocumentEntry]


class StatisticsResponse(BaseModel):
    total_documents: int
    reviewed_documents: int
    pending_documents: int


class DocumentUpdate(BaseModel):
    updated_fields: Dict[str, Any]
