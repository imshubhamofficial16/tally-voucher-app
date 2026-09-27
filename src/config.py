import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tally:tally@localhost:5432/tally_db")
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
    RAW_FILES_DIR = os.getenv("RAW_FILES_DIR", "./raw_files")

    # Ensure raw files directory exists
    os.makedirs(RAW_FILES_DIR, exist_ok=True)

config = Config()
