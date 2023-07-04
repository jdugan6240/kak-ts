import json
import logging
from pathlib import Path
import xdg_utils as xdg


def load_config():
    config_home = xdg.xdg_config_home()
    config_path = Path(config_home + "/kak-tree-sitter/config.json")

    config_data = config_path.read_text()
    try:
        config = json.loads(config_data)
    except json.JSONDecodeError as e:
        return None
    logging.debug(f"Config: {config}")
    return config
