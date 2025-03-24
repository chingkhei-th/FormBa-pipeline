from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    JSON,
    Float,
    DateTime,
)
from sqlalchemy.orm import relationship
from app.routers.auth import pwd_context
from app.database import Base
from datetime import datetime, timezone


class ReviewUser(Base):
    __tablename__ = "review_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    def verify_password(self, password: str):
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def get_password_hash(password: str):
        return pwd_context.hash(password)


class Institutes(Base):
    __tablename__ = "institutes"

    id = Column(Integer, primary_key=True, index=True)
    institute_names = Column(String, index=True)

    courses = relationship("Courses", back_populates="institute")
    users = relationship("Users", back_populates="institute")


class Knowledge(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_in = Column(String, index=True)

    users = relationship("Users", back_populates="knowledge")


class Courses(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    institute_id = Column(Integer, ForeignKey("institutes.id"), nullable=False)
    course_name = Column(String, index=True)

    institute = relationship("Institutes", back_populates="courses")
    users = relationship("Users", back_populates="course")


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    institute_name = Column(Integer, ForeignKey("institutes.id"), nullable=False)
    course_interested = Column(Integer, ForeignKey("courses.id"), nullable=False)
    knowledge_id = Column(Integer, ForeignKey("knowledge.id"), nullable=True)
    phone_no = Column(String, nullable=False)
    email = Column(String, index=True, nullable=False)
    password = Column(String)  # This will store the hashed password

    # Individual document fields replacing all_documents JSON field
    aadhaar_document = Column(String, nullable=True)
    caste_document = Column(String, nullable=True)
    school_cert_document = Column(String, nullable=True)
    school_mark_document = Column(String, nullable=True)
    uni_cert_document = Column(String, nullable=True)
    uni_mark_document = Column(String, nullable=True)

    passport_photo = Column(String, nullable=False)
    signature_photo = Column(String, nullable=False)

    # New relationship for submissions
    submissions = relationship("Submissions", back_populates="user")

    classified_documents = relationship("ClassifiedDocuments", back_populates="user")
    institute = relationship("Institutes", back_populates="users")
    course = relationship("Courses", back_populates="users")
    knowledge = relationship("Knowledge", back_populates="users")
    applicant_documents = relationship("ApplicantDocuments", back_populates="user")
    applicantinfo = relationship("Applicant_Information", back_populates="user")


class ClassifiedDocuments(Base):
    __tablename__ = "classified_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String, index=True)
    document_type = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)

    user = relationship("Users", back_populates="classified_documents")


class ApplicantDocuments(Base):
    __tablename__ = "applicant_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String, index=True)
    doc_type = Column(String, index=True)  # Classification type
    extracted_content = Column(JSON, nullable=False)

    user = relationship("Users", back_populates="applicant_documents")
    is_reviewed = Column(Boolean, default=False)


class Applicant_Information(Base):
    __tablename__ = "applicantinfo"

    id = Column(Integer, primary_key=True, index=True)
    institute_names = Column(String, index=True)
    course_name = Column(String, index=True)
    name = Column(String, index=True)
    father_name = Column(String, index=True)
    mother_name = Column(String, index=True)
    gender = Column(String, index=True)
    dob = Column(String, index=True)
    category = Column(String, index=True)
    occupation = Column(String, index=True)
    phone = Column(String, index=True)
    mobile = Column(String, index=True)
    address = Column(String, index=True)
    permanent_address = Column(String, index=True)
    examination_details = Column(JSON)
    aadhaar_number = Column(String, unique=True, index=True)
    email = Column(String, index=True, nullable=False)
    computer_knowledge = Column(String, index=True)
    signature_filename = Column(String, index=True)
    thumb_filename = Column(String, index=True)
    photograph_filename = Column(String, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("Users", back_populates="applicantinfo")


class Submissions(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_id = Column(String, unique=True, nullable=False)
    status = Column(String, default="started")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("Users", back_populates="submissions")
