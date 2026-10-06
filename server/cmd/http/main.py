import sys
from pathlib import Path

import uvicorn

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from internal.config import ConfigurationError


def main() -> None:
    try:
        from internal.app.http.app import create_app
    except ConfigurationError as exc:
        # Refuse to start and name the setting; a traceback would bury it.
        sys.exit(str(exc))

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
