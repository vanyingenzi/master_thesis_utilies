from dataclasses import dataclass, field
import json
import os
import logging
from typing import List, Dict
import yaml
import re
from enum import Enum
from .testcases import TestResult, MB

current_script_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(os.path.join(current_script_directory, os.pardir), os.pardir))

@dataclass
class Host:
    hostname: str
    role: str
    ips: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)

@dataclass
class MeasurementResult:
    result = TestResult
    details = str
    nb_paths = int
    all_infos: List[float] = field(default_factory=list)

@dataclass
class TestbedConfig:
    server: Host
    client: Host
    basename: str

    @classmethod
    def parse_json(cls, testbed_json: str):
        with open(testbed_json, 'r') as json_file:
            json_data = json.load(json_file)

        # Parse JSON data into the TestbedConfig structure
        return TestbedConfig(
            server=Host(**json_data['server'], role='server'),
            client=Host(**json_data['client'], role='client'), 
            basename=os.path.basename(testbed_json)
        )        
    
@dataclass
class PrePostRunScript:
    script: str
    blocking: bool = False

@dataclass
class YamlConfig:
    implementations: List[str]
    repetitions: int
    measurement_metrics: List[str]
    nb_paths: List[str]
    filesize: int = None
    duration: int = None
    client_prerunscript: List[PrePostRunScript] = field(default_factory=list)
    server_prerunscript: List[PrePostRunScript] = field(default_factory=list)
    client_postrunscript: List[PrePostRunScript] = field(default_factory=list)
    server_postrunscript: List[PrePostRunScript] = field(default_factory=list)
    client_implementation_params: dict = field(default_factory=lambda: {})
    server_implementation_params: dict = field(default_factory=lambda: {})
    build_script: str = None, 
    concurrent_clients: int = 1

    @classmethod
    def parse_postpre_runscript(cls, script_data: List[dict]):
        scripts = []
        for script in script_data:
            scripts.append(
                PrePostRunScript(os.path.join(project_root, script['path']), blocking=script.get('blocking', False))
            )
        return scripts

    @classmethod
    def parse_yaml(cls, yaml_file: str):

        with open(yaml_file, 'r') as yaml_file:
            yaml_data = yaml.safe_load(yaml_file)
        
        if next((x for x in yaml_data["nb_paths"] if x <= 0), None) != None:
            raise ValueError("Number of paths must be greater than 0")
        
        # Create an instance of the TestbedConfig data class
        return YamlConfig(
            implementations=yaml_data['implementations'],
            repetitions=yaml_data['repetitions'],
            measurement_metrics=yaml_data['measurement_metrics'],
            nb_paths=yaml_data['nb_paths'],
            filesize=yaml_data['filesize'] * MB if 'filesize' in yaml_data else None,
            duration=yaml_data['duration'] if 'duration' in yaml_data else None,
            client_prerunscript = cls.parse_postpre_runscript(yaml_data['client_prerunscript']),
            server_prerunscript = cls.parse_postpre_runscript(yaml_data['server_prerunscript']),
            client_postrunscript = cls.parse_postpre_runscript(yaml_data['client_postrunscript']),
            server_postrunscript = cls.parse_postpre_runscript(yaml_data['server_postrunscript']),
            client_implementation_params=yaml_data.get('client_implementation_params', {}),
            server_implementation_params=yaml_data.get('server_implementation_params', {}),
            build_script=yaml_data['build_script'], 
            concurrent_clients=yaml_data.get('concurrent_clients', 1)
        )
    

class LogFileFormatter(logging.Formatter):
    def format(self, record):
        msg = super(LogFileFormatter, self).format(record)
        # remove color control characters
        return re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]").sub("", msg)

class Perspective(Enum):
    SERVER = "server"
    CLIENT = "client"

@dataclass
class IPv4Path:
    address: str 
    port: int
    
    def __str__(self):
        return f"{self.address}:{self.port}"
    
    def repr(self):
        return f"{self.address}:{self.port}"