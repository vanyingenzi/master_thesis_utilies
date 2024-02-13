from src.args_parser import Arguments
from src.perfomance_runner import PerfomanceRunner
from src.models import TestbedConfig, YamlConfig

def main():
    args = Arguments.parse_argument()
    runner = PerfomanceRunner(
        TestbedConfig.parse_json(args.testbed_json),
        YamlConfig.parse_yaml(args.config_yaml)
    )
    runner.run()
    
if __name__ == "__main__":
    main()