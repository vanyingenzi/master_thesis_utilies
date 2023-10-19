from src.args_parser import Arguments, parse_argument
from src.perfomance_runner import PerfomanceRunner

def main():
    args = parse_argument()
    PerfomanceRunner(args)
    
if __name__ == "__main__":
    main()