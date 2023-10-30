from src.args_parser import Arguments
from src.perfomance_runner import PerfomanceRunner
from src.models import TestbedConfig

def main():
    args = Arguments.parse_argument()
    runner = PerfomanceRunner(
        TestbedConfig.parse_json_file(args.testbed_json)
    )
    runner.run()

    
if __name__ == "__main__":
    main()