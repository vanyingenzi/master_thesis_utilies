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
    ip: str
    role: str
    interfaces: List[str] = field(default_factory=list)

@dataclass
class MeasurementResult:
    result = TestResult
    details = str
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
    filesize: int
    client_prerunscript: List[PrePostRunScript] = field(default_factory=list)
    server_prerunscript: List[PrePostRunScript] = field(default_factory=list)
    client_postrunscript: List[PrePostRunScript] = field(default_factory=list)
    server_postrunscript: List[PrePostRunScript] = field(default_factory=list)
    client_implementation_params: dict = field(default_factory=lambda: {})
    server_implementation_params: dict = field(default_factory=lambda: {})
    build_script: str = None

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
        
        # Create an instance of the TestbedConfig data class
        return YamlConfig(
            implementations=yaml_data['implementations'],
            repetitions=yaml_data['repetitions'],
            measurement_metrics=yaml_data['measurement_metrics'],
            filesize=yaml_data['filesize'] * MB,
            client_prerunscript = cls.parse_postpre_runscript(yaml_data['client_prerunscript']),
            server_prerunscript = cls.parse_postpre_runscript(yaml_data['server_prerunscript']),
            client_postrunscript = cls.parse_postpre_runscript(yaml_data['client_postrunscript']),
            server_postrunscript = cls.parse_postpre_runscript(yaml_data['server_postrunscript']),
            client_implementation_params=yaml_data.get('client_implementaion_params', {}),
            server_implementation_params=yaml_data.get('server_implementaion_params', {}),
            build_script=yaml_data['build_script']
        )
    

class LogFileFormatter(logging.Formatter):
    def format(self, record):
        msg = super(LogFileFormatter, self).format(record)
        # remove color control characters
        return re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]").sub("", msg)
    

class Perspective(Enum):
    SERVER = "server"
    CLIENT = "client"