import os
from pathlib import Path


TEST_DATA_DIR = Path(__file__).resolve().parent / '.data'

os.environ.setdefault('UPLOAD_DIR', str(TEST_DATA_DIR / 'uploads'))
os.environ.setdefault('FAISS_DIR', str(TEST_DATA_DIR / 'faiss'))
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
