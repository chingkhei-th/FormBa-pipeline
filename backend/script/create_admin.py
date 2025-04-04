from database import SessionLocal
from models import Admin, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database URL (same as in database.py)
DATABASE_URL = "postgresql+psycopg://postgres:hello@localhost:5432/apply_course"

# Create the database engine
engine = create_engine(DATABASE_URL)

# Create all tables (if they don't exist)
Base.metadata.create_all(bind=engine)

# Create a session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()


# Function to create an admin user
def create_admin(username: str, email: str, password: str):
    # Check if the admin already exists
    existing_admin = db.query(Admin).filter(Admin.username == username).first()
    if existing_admin:
        print(f"Admin with username '{username}' already exists.")
        return

    # Hash the password
    hashed_password = Admin.get_password_hash(password)

    # Create the admin user
    admin = Admin(username=username, email=email, hashed_password=hashed_password)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Admin user '{username}' created successfully.")


# Create an admin user
create_admin(username="admin", email="admin@example.com", password="admin123")

# Close the session
db.close()
