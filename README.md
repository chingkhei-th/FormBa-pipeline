# FormBa Backend (with testing frontend)

## How to run
1. Change current working directory to backend.
    ```shell
    cd backend
    ```
2. Database initialization:
    ```shell
    python -c "from app.models import Base; from app.database import engine; Base.metadata.create_all(bind=engine)"
    ```
3. Create admin:
    ```shell
    python script/create_admin.py
   ```

2. Run the following command to start the server.
    ```shell
    uvicorn main:app --host localhost --port 8000 --reload
    ```