import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings

if __name__ == "__main__":
    print(settings.langchain_api_key)