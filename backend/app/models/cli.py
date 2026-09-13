"""Usage: python -m app.models.cli list | download ROLE | download all"""

import argparse
import json

from ..config import Settings
from .hub import ModelHub, ModelNotReady


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "download"])
    parser.add_argument("role", nargs="?")
    args = parser.parse_args()
    settings = Settings()
    hub = ModelHub(settings.cache_dir)
    if args.command == "download" and not args.role:
        parser.error("download requires a model role or all")
    roles = (
        settings.models.models
        if args.role in (None, "all")
        else {args.role: settings.models.models.get(args.role)}
    )
    for role, spec in roles.items():
        if spec is None:
            parser.error(f"Unknown model role: {role}")
        if (
            args.role == "all"
            and role == settings.models.routes.get("assets")
            and not settings.models.images_enabled
        ):
            continue
        if args.command == "download":
            print(json.dumps({"role": role, **hub.download(spec)}, indent=2))
        else:
            try:
                manifest = hub.resolve(spec)
                status = manifest["revision"]
            except ModelNotReady:
                status = "not downloaded"
            print(f"{role}: {spec.repo_id} ({spec.runtime}, {spec.device}) — {status}")


if __name__ == "__main__":
    main()
