"""`make openapi` — print the OpenAPI document without starting a server.
`sort_keys` keeps the CI drift check (`git diff --exit-code`) stable."""

import json
import sys

from app.main import create_app


def main() -> None:
    sys.stdout.write(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
