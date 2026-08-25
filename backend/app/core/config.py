import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-a-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_TTL_MINUTES", "60"))
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCKOUT_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "15"))
AUTH_USERS_FILE = os.getenv(
	"AUTH_USERS_FILE",
	str(Path(__file__).resolve().parents[3] / "instance" / "users.json"),
)
CHARTS_FILE = os.getenv(
	"CHARTS_FILE",
	str(Path(__file__).resolve().parents[3] / "instance" / "charts.json"),
)
CMS_MODELS_FILE = os.getenv(
	"CMS_MODELS_FILE",
	str(Path(__file__).resolve().parents[3] / "instance" / "cms_models.json"),
)
CMS_MODEL_FAMILY = os.getenv("CMS_MODEL_FAMILY", "CMS-HCC")
CMS_MODEL_VERSION = os.getenv("CMS_MODEL_VERSION", "V28")
ICD_DIAGNOSIS_FILE = os.getenv("ICD_DIAGNOSIS_FILE", "")
