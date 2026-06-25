from fastapi import APIRouter
from configs.verticals import VERTICALS

router = APIRouter(prefix="/verticals", tags=["verticals"])


@router.get("")
def list_verticals():
    return [
        {
            "key": key,
            "display_name": cfg["display_name"],
            "description": cfg["description"],
            "icon": cfg["icon"],
            "input_schema": cfg["input_schema"],
            "default_format": cfg["default_format"],
            "output_sections": cfg["output_sections"],
            "task_type": cfg["task_type"],
        }
        for key, cfg in VERTICALS.items()
    ]
