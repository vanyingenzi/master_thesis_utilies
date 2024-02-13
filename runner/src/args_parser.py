import argparse, os 
from dataclasses import dataclass
import json
import yaml

@dataclass
class Arguments:
    config_yaml: str
    results_dir: str
    testbed_json: str = None

    @classmethod
    def parse_argument(cls) :
        current_script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(os.path.join(current_script_directory, os.pardir), os.pardir)
            
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--config", type=str, required=True, help="The YAML filename of the config to run. The config file must be in the project root directory (configs/).")
        parser.add_argument("-t", "--testbed_json", type=str, required=False, help="The JSON filename of the testbed to run. The testbed file must be in the current directory (testbeds/).", default=os.path.join(project_root, "testbeds/testbed_cloudlab.json"))
        parser.add_argument("-r", "--results_dir", type=str, required=False, help="The directory to which save the results from the expirement. Default is project root directory (results/).", default=os.path.join(project_root, "results/"))
        
        args = parser.parse_args()

        return Arguments(
            config_yaml = os.path.join( os.path.join(project_root, "configs"), args.config), 
            results_dir = os.path.abspath( os.path.join( os.path.join(project_root, "results"), args.results_dir) ), 
            testbed_json = os.path.abspath( os.path.join( os.path.join(project_root, "testbeds"), args.testbed_json) )
        )
    
def parse_json_file(file_path):
    with open(file_path) as file:
        data = json.load(file)
    return data

def parse_yaml_file(file_path):
    with open(file_path) as file:
        data = yaml.safe_load(file)
    return data

