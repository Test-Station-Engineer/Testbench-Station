# Stores a reference to general_settings.yaml

# Allows the program to be launched from anywhere,
# AKA Makes file references relative to this file instead of literal directory.
from pathlib import Path
import yaml

try:
    CONFIG_PATH = Path(__file__).parent / "config" / "general_settings.yaml" # NOTE This needs to change if I move this file

    with CONFIG_PATH.open() as f:
        config = yaml.safe_load(f)
        print("CONFIG LOADED SUCCESSFULLY")
except:
    raise RuntimeError("Target config file not found")