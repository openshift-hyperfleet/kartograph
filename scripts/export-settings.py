import json
import sys
from pathlib import Path
from typing import Type
from pydantic import SecretStr
from pydantic_settings import BaseSettings

root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path / "src" / "api"))

# Import your settings classes
from infrastructure.settings import (  # noqa: E402
    DatabaseSettings,
    CORSSettings,
    SpiceDBSettings,
    OutboxWorkerSettings,
    IAMSettings,
    OIDCSettings,
)


def get_model_metadata(settings_class: Type[BaseSettings]):
    prefix = settings_class.model_config.get("env_prefix", "")
    properties = []

    for name, field in settings_class.model_fields.items():
        type_name = getattr(field.annotation, "__name__", str(field.annotation))
        default = field.get_default()

        # 1. Logic for determining "Required"
        # A field is effectively required if:
        # - It has no default (PydanticUndefined)
        # - OR it's a Secret that is currently an empty string (common Pydantic pattern)
        is_required = (
            default is None
            or "PydanticUndefined" in str(default)
            or (
                isinstance(default, SecretStr) and str(default.get_secret_value()) == ""
            )
        )

        # 2. Logic for displaying the default
        if isinstance(default, SecretStr):
            display_default = "********" if not is_required else None
        elif is_required:
            display_default = None
        else:
            display_default = str(default)

        properties.append(
            {
                "env_var": f"{prefix}{name.upper()}",
                "type": "Secret" if "Secret" in type_name else type_name,
                "default": display_default,
                "required": is_required,
                "description": field.description or "",
            }
        )

    return {
        "class_name": settings_class.__name__,
        "prefix": prefix,
        "doc": settings_class.__doc__ or "",
        "properties": properties,
    }


def export_settings():
    classes = [
        DatabaseSettings,
        OIDCSettings,
        SpiceDBSettings,
        CORSSettings,
        IAMSettings,
        OutboxWorkerSettings,
    ]

    data = {cls.__name__: get_model_metadata(cls) for cls in classes}

    output_path = root_path / "website" / "src" / "data" / "env-vars.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Exported settings to {output_path}")


if __name__ == "__main__":
    export_settings()
