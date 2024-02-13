from dataclasses import dataclass, field
import json
import os
import logging
from typing import List
import yaml
import re
from enum import Enum
from .testcases import TestResult, MB

@dataclass
class Host:
    hostname: str
    ip: str
    interface: str
    role: str


class MeasurementResult:
    result = TestResult
    details = str
    all_infos: [float] = []


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
class YamlConfig:
    implementations: List[str]
    repetitions: int
    measurement_metrics: List[str]
    filesize: int
    client_prerunscript: List[str] = field(default_factory=list)
    server_prerunscript: List[str] = field(default_factory=list)
    client_postrunscript: List[str] = field(default_factory=list)
    server_postrunscript: List[str] = field(default_factory=list)
    build_script: str = None

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
            client_prerunscript=yaml_data['client_prerunscript'],
            server_prerunscript=yaml_data['server_prerunscript'],
            client_postrunscript=yaml_data['client_postrunscript'],
            server_postrunscript=yaml_data['server_postrunscript'], 
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