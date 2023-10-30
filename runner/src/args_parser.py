import argparse, os 
from dataclasses import dataclass

@dataclass
class Arguments:
    config_yaml: str
    results_dir: str

    @classmethod
    def parse_argument(cls) :
        current_script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(os.path.join(current_script_directory, os.pardir), os.pardir)
            
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--config", type=str, required=True, help="The YAML filename of the config to run. The config file must be in the project root directory (configs/).")
        parser.add_argument("-r", "--results_dir", type=str, required=False, help="The directory to which save the results from the expirement. Default is project root directory (results/).", default=os.path.join(project_root, "results/"))
        
        args = parser.parse_args()

        return Arguments(
            config_yaml = os.path.join( os.path.join(project_root, "configs"), args.config), 
            results_dir = os.path.abspath( args.results_dir )
        )