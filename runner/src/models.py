from dataclasses import dataclass, field
import json
from typing import List
import yaml

@dataclass
class Host:
    hostname: str
    ip: str
    interface: str

@dataclass
class TestbedConfig:
    server: Host
    client: Host

    @classmethod
    def parse_json_file(cls, testbed_json: str):
        with open(testbed_json, 'r') as json_file:
            json_data = json.load(json_file)

        # Parse JSON data into the TestbedConfig structure
        return TestbedConfig(
            server=Host(**json_data['server']),
            client=Host(**json_data['client'])
        )
    

@dataclass
class YamlConfig:

    testbed: str
    implementations: List[str]
    repetitions: int
    filesize: int
    client_prerunscript: List[str] = field(default_factory=list)
    server_prerunscript: List[str] = field(default_factory=list)
    client_postrunscript: List[str] = field(default_factory=list)
    server_postrunscript: List[str] = field(default_factory=list)

    @classmethod
    def parse_yaml(cls, yaml_file: str):

        with open(yaml_file, 'r') as yaml_file:
            yaml_data = yaml.safe_load(yaml_file)

        # Create an instance of the TestbedConfig data class
        return YamlConfig(
            testbed=yaml_data['testbed'],
            implementations=yaml_data['implementations'],
            repetitions=yaml_data['repetitions'],
            filesize=yaml_data['filesize'],
            client_prerunscript=yaml_data['client_prerunscript'],
            server_prerunscript=yaml_data['server_prerunscript'],
            client_postrunscript=yaml_data['client_postrunscript'],
            server_postrunscript=yaml_data['server_postrunscript']
        )