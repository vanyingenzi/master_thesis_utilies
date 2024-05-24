import re
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime

colors_impl_mapping = {
    "mpquic": "#E69F00",
    "mcmpquic": "#56B4E9",
    "quic": "#009E73",
    "mcmpquic-aff": "#F0E442",
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