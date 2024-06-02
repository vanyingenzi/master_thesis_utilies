import re
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime
import colorsys

colors_impl_mapping = {
    "mpquic": "#E69F00",
    "mcmpquic": "#56B4E9",
    "mcmpquic-aff": "#009E73",
    "mcmpquic-rfs": "#CC79A7",
}

def get_color_for_impl(impl: str):
    return colors_impl_mapping.get(impl, "black")

def mcmpquic_extract_nb_paths(filepath: str) -> int:
    """ Extract path information from the logs of a mcMPQUIC endpoint. Idealy from the server as it is the one
    that validates a path lastly. [MPQUIC detail]
    """
    pattern = re.compile(r".*(p|P)ath.*is now validated")
    nb_paths = 0
    with open(filepath) as f:
        for line in f: 
            if pattern.match(line):
                nb_paths += 1
    return nb_paths + 1 # +1 for the default path

def get_test_start_end_time(time_json_file) -> Tuple[int, int]:
    with open(time_json_file) as f:
        data = json.load(f)
        return data["start"], data["end"]
    
def get_transfer_time_client(time_json_file) -> float:
    with open(time_json_file) as f:
        data = json.load(f)
    start = datetime.fromtimestamp(int(data["start"]) / 1e9)
    end = datetime.fromtimestamp(int(data["end"]) / 1e9)
    diff = end - start
    return diff.total_seconds()

def hex_to_rgb(hex_value):
    hex_value = hex_value.lstrip('#')
    return tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))

def get_color_for_impl_n_path(impl: str, nb_paths: int, max_nb_paths: int = 16) -> Tuple[float, float, float]:
    base_color_hex = get_color_for_impl(impl)
    base_color_rgb = hex_to_rgb(base_color_hex)
    base_color_rgb_normalized = [x / 255 for x in base_color_rgb]
    h, s, _ = colorsys.rgb_to_hsv(*base_color_rgb_normalized)
    step = 100 / max_nb_paths
    v = step * nb_paths
    v = v / 100
    return colorsys.hsv_to_rgb(h, s, v)