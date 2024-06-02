from .models import *
import logging, pathlib, os, subprocess, sys
from termcolor import colored
import tempfile
from datetime import datetime
import string
import random
from typing import List, Callable, Tuple
from .testcases import *
import json
import time
import statistics
import shutil
from collections import defaultdict
import glob
import os
import json
import prettytable
import traceback

current_script_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(os.path.join(current_script_directory, os.pardir), os.pardir))

def random_string(length: int):
    """ Generate a random string of fixed length """
    letters = string .ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))

def get_tests_and_measurements(config: YamlConfig) -> Tuple[List[TestCase], List[TestCase]]:
    tests = [] # Ignored for now as test would be to check if par example a handshake is successful etc. For now we are focused on the measurements
    measurements = []
    for measurement_metric in config.measurement_metrics:
        if measurement_metric not in MEASUREMENTS.keys():
            raise ValueError(f"Unknown measurement metric: {measurement_metric}")
        if measurement_metric == "throughput":
            measurement = MEASUREMENTS[measurement_metric]
            measurement.DURATION = config.duration
            measurement.REPETITIONS = config.repetitions
            measurement.CONCURRENT_CLIENTS = config.concurrent_clients
            measurement.TIMEOUT = config.timeout
            measurements.append(measurement)
    return tests, measurements

class PerfomanceRunner:

    def __init__(
        self, 
        testbed: TestbedConfig, 
        config: YamlConfig, 
        debug=True
    ) -> None:
        self._testbed = testbed
        self._config = config
        self.logger = logging.getLogger()
        self._init_logger(debug)
        self._implementations_directory = os.path.join(
            project_root, 'implementations'
        )
        self.compliant_checks = dict()
        self._venv_dir = "/tmp"
        self._disable_client_aes_offload = False
        self._disable_server_aes_offload = False
        self._save_files = False
        self._start_time = datetime.now()
        self._tests, self._measurements = get_tests_and_measurements(self._config) 
        self._prepared_envs = set()
        self.test_results = {}
        self.measurement_results: dict[MeasurementNames, Dict[str, Dict[int, MeasurementResult]]] = defaultdict(lambda: defaultdict(dict))
        self._continue_on_error = False
        self._log_dir = os.path.join(project_root, "logs", "logs_{:%Y-%m-%dT%H:%M:%S}".format(self._start_time))
        self._built_executables = set()
        self._output = ""

    def _init_logger(self, debug) -> None:
        self.logger.setLevel(logging.DEBUG)
        console = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter(
            '[%(asctime)s][%(levelname)s]: %(message)s'
        )
        console.setFormatter(formatter)
        if debug:
            console.setLevel(logging.DEBUG)
        else:
            console.setLevel(logging.INFO)
        self.logger.addHandler(console)

    def _push_directory_to_remote(self, host: str, src, dst=None, normalize=True) -> bool:
        """Copies a directory <src> from the machine it is executed on
        (management host) to a given host <host> to path <dst> using rsync.
        """
        if normalize:
            src = os.path.normpath(src)

        if not dst:
            dst = str(pathlib.Path(src).parent)
        self.logger.debug(f"Copy {src} to {host}:{dst}")

        cmd = f'rsync -r {src} {host}:{dst}'
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            returned_code = p.wait()
            self.logger.debug(f"The transfer return code : {returned_code}")
            if returned_code != 0:
                self.logger.error(
                    colored(f"Failed to copy {src} to {host}:{dst}", "red")
                )
                self.logger.error(colored(f"{p.stdout.read().decode('utf-8')}", "red"))
                self.logger.error(colored(f"{p.stderr.read().decode('utf-8')}", "red"))
            return returned_code == 0
        except subprocess.TimeoutExpired:
            self.logger.debug(
                f'Timeout when moving files {src} to host {host}')
        return False

    def _generate_cert_chain(self, directory: str, length: int = 1):
        cmd = f"{current_script_directory}/certs.sh " + directory + " " + str(length)
        r = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if r.returncode != 0:
            self.logger.error(colored("Error generating certificates", "red", attrs=["bold"]))
            self.logger.error("%s", r.stdout.decode("utf-8"))
            sys.exit(r.returncode)
        else:
            self.logger.debug("%s", r.stdout.decode("utf-8"))

    def _give_execute_permission(self, host: Host, script: str) -> None:
        self.logger.debug(f"Give execute permission to {script} on {host.hostname}")
        cmd = f'ssh {host.hostname} "chmod +x {script}"'
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            returned_code = p.wait()
            self.logger.debug(f"The command return code : {returned_code}")
        except subprocess.TimeoutExpired:
            self.logger.error(
                colored(f'Timeout when moving files {script} to host {host.hostname}', 'red')
            )
        return
    
    def _copy_implementations(self):
        for implementation in self._config.implementations:
            self._push_directory_to_remote(
                self._testbed.client.hostname,
                os.path.join(
                    self._implementations_directory,
                    implementation,
                    ''  # This prevents that rsync copies the directory into itself, adds trailing slash
                ),
                f"~",
                normalize=True
            )
            self._push_directory_to_remote(
                self._testbed.server.hostname,
                os.path.join(
                    self._implementations_directory,
                    implementation,
                    ''  # This prevents that rsync copies the directory into itself, adds trailing slash
                ),
                f"~",
                normalize=True
            )
            for host in [self._testbed.client, self._testbed.server]:
                shell_scripts = glob.glob(os.path.join(self._implementations_directory, implementation, "*.sh"))
                shell_scripts = [f"~/{implementation}/{os.path.basename(script)}" for script in shell_scripts]
                for script in shell_scripts:
                    self._give_execute_permission(host, script)

    def _does_remote_file_exist(self, host: Host, file: str) -> bool:
        self.logger.debug(f"Checking if {file} exists on {host.hostname}")

        check = subprocess.Popen(
            f'ssh {host.hostname} "test -f {file}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            exit_code = check.wait(timeout=10)
            return exit_code == 0
        except subprocess.TimeoutExpired:
            return False
        
    def _delete_remote_directory(self, host: Host, directory: str) -> None:
        cmd = f'ssh {host.hostname} "rm -rf {directory}"'
        self.logger.debug(f"Deleting {host.hostname}:{directory}")

        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def _run_command_on_remote_host(self, host: Host, command: list) -> None:
        command_string = " ".join(command)
        self.logger.debug(f"Running command \"{command_string}\" on {host.hostname}")
        proc = subprocess.Popen(
            f'ssh {host.hostname} "{command_string}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate()
        self.logger.debug(host.hostname)
        self.logger.debug(colored(f"stdout: {stdout.decode('utf-8')}", "yellow"))
        self.logger.debug(colored(f"stderr: {stderr.decode('utf-8')}", "yellow"))

    def _create_venv_on_remote_host(self, host: Host, venv_dir_path: str) -> None:
        self.logger.debug(f"Venv Setup: Creating venv on host {host.hostname} at {venv_dir_path}")
        self._run_command_on_remote_host(
            host,
            ["python3", "-m", "venv", venv_dir_path]
        )
        self._give_execute_permission(host, f"{venv_dir_path}/bin/activate")
    
    def _get_venv(self, host: Host) -> str:
            """Creates the venv directory for the specified role either locally or
            copied to the host in testbed mode should it not exist.

            Return: the path of the
            with a prepended bash 'source' command.
            """
            venv_dir = os.path.join(self._venv_dir, host.role)
            venv_activate = os.path.join(venv_dir, "bin/activate")

            if not self._does_remote_file_exist(host, venv_activate):
                self._create_venv_on_remote_host(host, venv_dir)
            return venv_activate
    
    def _is_unsupported(self, lines: List[str]) -> bool:
        return any("exited with code 127" in str(line) for line in lines) or any(
            "exit status 127" in str(line) for line in lines
        )

    def _log_process(self, stdout: bytes, stderr: bytes, context: str) -> None:
        self.logger.debug(context)
        self.logger.debug(colored(f"\nstdout: {stdout.decode('utf-8')}", "yellow"))
        self.logger.debug(colored(f"\nstderr: {stderr.decode('utf-8')}", "yellow"))
    
    def _run_script_on_machine(self, host: Host, script_path: str):
        self.logger.debug(f'Running {script_path} on {host.hostname}')
        proc = subprocess.Popen(
            f'cat {script_path} | ssh {host.hostname} "sudo bash -s"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try: 
            stdout, stderr = proc.communicate()
            self._log_process(stdout, stderr, f'host: {host.hostname}')
        except subprocess.TimeoutExpired:
            self.logger.debug(
                colored(f'Timeout when running {script_path} on host {host.hostname}', 'yellow')
            )
            return
        
    def _run_prepost_runscript(self, host: Host, script: PrePostRunScript):
        self.logger.debug(f'Running {script.script} on {host.hostname}')
        proc = subprocess.Popen(
            f'cat {script.script} | ssh {host.hostname} "sudo bash -s"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            if not script.blocking:
                stdout, stderr = proc.communicate()
                self._log_process(stdout, stderr, f'host: {host.hostname}')
        except Exception as e:
            self.logger.error(
                colored(f'Error{e} when running {script.script} on host {host.hostname}', 'red')
            )
        finally:
            return proc
    
    def _is_port_in_use(self, host: Host, port: int) -> None:
        self.logger.debug(f"Checking if port {port} is in use on {host.hostname}")
        check = subprocess.Popen(
            f'ssh {host.hostname} "ss -tupln | grep {port}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = check.communicate(timeout=10)
            self._log_process(stdout, stderr, f'host: {host.hostname}')
            return check.returncode == 0 # 0 means port is in use
        except subprocess.TimeoutExpired:
            return True
    
    def _generate_ports(self, host: Host, nb_ports: int) -> List[int]:
        to_return = []
        for _ in range(nb_ports):
            port = random.randint(4434, 7000)
            while self._is_port_in_use(host, port) or port in to_return:
                port = random.randint(4434, 7000)
            to_return.append(port)
        return to_return
    
    def _create_paths(self, nb_paths: int) -> Tuple[List[IPv4Path], List[IPv4Path]] :
        server_paths = []
        client_paths = []
        if nb_paths < 1:
            raise ValueError("Number of paths must be at least 1")
        servers_provided_ips = len(self._testbed.server.ips)
        clients_provided_ips = len(self._testbed.client.ips)
        server_ports = [4433] + self._generate_ports(self._testbed.server, nb_paths - 1)
        # TODO ensure unique ports
        client_ports = self._generate_ports(self._testbed.client, nb_paths)
        client_ips_idx = 0
        server_ips_idx = 0
        for i in range(nb_paths):
            client_ip = self._testbed.client.ips[client_ips_idx]
            client_port = client_ports[i]
            server_ip = self._testbed.server.ips[server_ips_idx]
            server_port = server_ports[i]
            client_paths.append(IPv4Path(client_ip, client_port))
            server_paths.append(IPv4Path(server_ip, server_port))
            client_ips_idx = (client_ips_idx + 1) % clients_provided_ips
            server_ips_idx = (server_ips_idx + 1) % servers_provided_ips
        return client_paths, server_paths
        
        
    def _setup_hosts(self):
        self._run_script_on_machine(self._testbed.server, os.path.join(current_script_directory, "setup.sh"))
        self._run_script_on_machine(self._testbed.client, os.path.join(current_script_directory, "setup.sh"))

        for implementation in self._config.implementations:
            self._setup_env(self._testbed.client, "~/" + implementation)
            self._setup_env(self._testbed.server, "~/" + implementation)

    def _set_variables_on_machine(self, host: Host, dictionary: dict):
        self.logger.debug(f"Setting the variables:\n{dictionary}\non the host {host.hostname}")

        tmp_file = tempfile.NamedTemporaryFile(dir="/tmp", prefix="interop-temp-data-", mode="w+")
        json.dump(dictionary, tmp_file, ensure_ascii=False, indent=4)
        tmp_file.flush()
        tmp_file.seek(0)

        src = tmp_file.name
        dst = "/tmp/interop-variables.json"
        self.logger.debug(f"Copy {src} to {host.hostname}:{dst}")
        cmd = f'rsync -r {src} {host.hostname}:{dst}'

        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            if p.wait(10) != 0:
                self.logger.error(colored(f"Failed to copy {src} to {host.hostname}:{dst}", "red"))
                self.logger.error(colored(f"{p.stdout.read().decode('utf-8')}", "red"))
                self.logger.error(colored(f"{p.stderr.read().decode('utf-8')}", "red")) 
        except subprocess.TimeoutExpired:
            self.logger.debug(
                f'Timeout when moving variable file to host {host.hostname}')
        finally:
            tmp_file.close()
            return

    def _remove_all_variables_from_machine(self, host: Host):
        self.logger.debug(f"Removing all variables from {host.hostname}")
        prog = subprocess.Popen(
            f'ssh {host.hostname} "rm -rf /tmp/interop-variables.json"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return prog.wait(10)

    def _get_content_of_remote_file(self, host: Host, src: str):
        self.logger.debug(f"Getting content of {src} from {host.hostname}")
        cmd = f'ssh {host.hostname} "cat {src}"'
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = p.communicate(timeout=10)
            return stdout.decode("utf-8")
        except subprocess.TimeoutExpired:
            self.logger.error(
                f'Timeout when reading file {src} from host {host.hostname}')
        return None

    
    def _pull_directory_from_remote(self, host: Host, src: str, dst=None):
        src = os.path.normpath(src)
        if not dst:
            dst = str(pathlib.Path(src).parent)
        self.logger.debug(f"Copy {host.hostname}:{src} to {dst}")

        cmd = f'rsync -r {host.hostname}:{src} {dst}'
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            # large timeout as copied file could be very large
            p.wait(2000)
            
        except subprocess.TimeoutExpired:
            self.logger.debug(
                f'Timeout when copying files {src} from host {host.hostname}')
        return
    
    def _build_impl_executable(self, host: Host, implementation: str) -> None:
        self.logger.debug(f"Building {implementation} on {host.hostname}")
        self._run_command_on_remote_host(host, [f"cd ~/{implementation}; ./{self._config.build_script}"])
        self._give_execute_permission(host, f"~/{implementation}/{implementation}-{host.role}")

    def _run_testcase(self, implementation_name: str, server: Host, client: Host, test: Callable[[], TestCase], nb_paths: int, log_dir_prefix=None) -> None:
        start_time = datetime.now()
        sim_log_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="logs_sim_")
        server_log_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="logs_server_")
        client_log_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="logs_client_")
        log_file = tempfile.NamedTemporaryFile(dir="/tmp", prefix="output_log_")
        log_handler = logging.FileHandler(log_file.name)
        log_handler.setLevel(logging.DEBUG)

        formatter = LogFileFormatter("%(asctime)s %(message)s")
        log_handler.setFormatter(formatter)
        self.logger.addHandler(log_handler)

        client_keylog = os.path.join(client_log_dir.name, 'keys.log')
        server_keylog = os.path.join(server_log_dir.name, 'keys.log')
        client_qlog_dir = os.path.join(client_log_dir.name, 'client_qlog/')
        server_qlog_dir = os.path.join(server_log_dir.name, 'server_qlog/')
        
        client_paths, server_paths = self._create_paths(nb_paths)
        testcase: TestCase = test(
            link_bandwidth=None,
            client_delay=None,
            server_delay=None,
            sim_log_dir=sim_log_dir,
            client_keylog_file=client_keylog,
            server_keylog_file=server_keylog,
            client_log_dir=client_log_dir.name,
            server_log_dir=server_log_dir.name,
            client_qlog_dir=client_qlog_dir,
            server_qlog_dir=server_qlog_dir,
            server_ip=server_paths[0].address,
            server_port=server_paths[0].port,
            server_name=server.role,
            concurrent_clients=self._config.concurrent_clients
        )
        
        created_dirs_on_remote_client = []
        created_dirs_on_remote_server = []

        for dir in [server_log_dir.name, testcase.www_dir(), testcase.certs_dir()]:
            if self._push_directory_to_remote(server.hostname, dir):
                created_dirs_on_remote_server.append(dir)
            else:
                for dir in created_dirs_on_remote_server:
                    self._delete_remote_directory(server, dir)
                server_log_dir.cleanup()
                client_log_dir.cleanup()
                sim_log_dir.cleanup()
                return TestResult.FAILED, None
            
        for dir in [sim_log_dir.name, client_log_dir.name, testcase.download_dir()]:
            if self._push_directory_to_remote(client.hostname, dir):
                created_dirs_on_remote_client.append(dir)
            else:
                for dir in created_dirs_on_remote_server:
                    self._delete_remote_directory(server, dir)
                for dir in created_dirs_on_remote_client:
                    self._delete_remote_directory(client, dir)
                server_log_dir.cleanup()
                client_log_dir.cleanup()
                sim_log_dir.cleanup()
                return TestResult.FAILED, None

        server_params = " ".join([
            f"SSLKEYLOGFILE={server_keylog}",
            f"QLOGDIR={server_qlog_dir}" if testcase.use_qlog() else "",
            f"LOGS={server_log_dir.name}",
            f"TESTCASE={testcase.testname(Perspective.SERVER)}",
            f"WWW={testcase.www_dir()}",
            f"CERTS={testcase.certs_dir()}",
            f"IP={testcase.ip()}",
            f"PORT={testcase.port()}",
            f"SERVERNAME={testcase.servername()}",
        ])
        
        if self._disable_server_aes_offload:
            server_params = " ".join([
                'OPENSSL_ia32cap="~0x200000200000000"',
                server_params
            ])

        clients_params = []
        for client_id in range(0, self._config.concurrent_clients):
            client_params = " ".join([
                f"SSLKEYLOGFILE={client_keylog}",
                f"QLOGDIR={client_qlog_dir}" if testcase.use_qlog() else "",
                f"LOGS={client_log_dir.name}",
                f"TESTCASE={testcase.testname(Perspective.CLIENT)}",
                f"DOWNLOADS={testcase.download_dir()}",
                f"CLIENTSUFFIX={('_'+str(client_id)) if self._config.concurrent_clients > 1 else ''}",
            ])
            if self._disable_client_aes_offload:
                client_params = " ".join([
                    'OPENSSL_ia32cap="~0x200000200000000"',
                    client_params
                ])
            clients_params.append(client_params)

        if implementation_name not in self._built_executables:
            self._build_impl_executable(server, implementation_name)
            self._built_executables.add(implementation_name)
            self._build_impl_executable(client, implementation_name)
            self._built_executables.add(implementation_name)

        server_run_script = "./run-server.sh"
        server_venv_script = self._get_venv(server)
        client_run_script = "./run-client.sh"
        client_venv_script = self._get_venv(client)

        server_cmd = f"{server_venv_script}; {server_params} {server_run_script}"
        client_cmd = f"{client_venv_script}; {client_params} {client_run_script}"
        clients_cmd = []
        for client_params in clients_params:
            clients_cmd.append(f"{client_venv_script}; {client_params} {client_run_script}")

        server_cmd = f'ssh {server.hostname} \'cd ~/{implementation_name}; {server_cmd}\''
        client_cmd = f'ssh {client.hostname} \'cd ~/{implementation_name}; {client_cmd}\''
        clients_cmd = [f'ssh {client.hostname} \'cd ~/{implementation_name}; {client_cmd}\'' for client_cmd in clients_cmd]
        expired = False

        try:
            server_variables: dict = {
                "implementation": implementation_name,
                "interfaces": server.interfaces,
                "hostname": server.hostname,
                "log_dir": server_log_dir.name,
                "www_dir": testcase.www_dir(),
                "certs_dir": testcase.certs_dir(),
                "role": server.role,
                "filesize": testcase.FILESIZE, # in bytes, 
                "duration": testcase.DURATION, # in seconds, 
                "listen_addr": server_paths[0].repr(),
                "extra_server_addrs": [addr.repr() for addr in server_paths[1:]],
            }
            server_variables = {**server_variables, **self._config.server_implementation_params}
            client_variables: dict = {
                "implementation": implementation_name,
                "interfaces": client.interfaces,
                "hostname": client.hostname,
                "log_dir": client_log_dir.name,
                "sim_log_dir": sim_log_dir.name,
                "download_dir": testcase.download_dir(),
                "role": client.role,
                "server_ip_port": f"{testcase.ip()}:{testcase.port()}",
                "connect_to": server_paths[0].repr(),
                "duration": testcase.DURATION, # in seconds, also for client, added to support iperf3
                "extra_server_addrs": [addr.repr() for addr in server_paths[1:]],
                "client_addrs": [addr.repr() for addr in client_paths],
            }
            client_variables = {**client_variables, **self._config.client_implementation_params}

            # TODO add server_implementation_params and client_implementation_params
            self._set_variables_on_machine(
                server,
                server_variables
            )
            self._set_variables_on_machine(
                client,
                client_variables
            )

            server_scripts_run: List[Tuple[PrePostRunScript, subprocess.Popen]] = []
            client_scripts_run: List[Tuple[PrePostRunScript, subprocess.Popen]] = []

            # Execute List of Server Pre Run Scripts if given
            for server_script in self._config.server_prerunscript:
                if not server_script.blocking:
                    self._run_script_on_machine(server, server_script.script)
                else:
                    server_scripts_run.append((server_script, self._run_prepost_runscript(server, server_script)))
            
            # Execute List of Client Pre Run Scripts if given
            for client_script in self._config.client_prerunscript:
                if not client_script.blocking:
                    self._run_script_on_machine(client, client_script.script)
                else:
                    client_scripts_run.append((client_script, self._run_prepost_runscript(client, client_script)))
            
            # Run Server
            self.logger.info(f'Starting server:\n {server_cmd}\n')
            s = subprocess.Popen(
                server_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            time.sleep(2)
            # Run Client
            clients_processes: List[subprocess.Popen[bytes]] = []
            for client_cmd in clients_cmd:
                self.logger.info(f'Starting client:\n {client_cmd}\n')
                c = subprocess.Popen(
                    client_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                clients_processes.append(c)

            min_start_time = None
            max_end_time = None
            for client_id, c in enumerate(clients_processes):
                c_stdout, c_stderr = c.communicate(timeout=testcase.timeout())
                output = (c_stdout.decode("utf-8") if c_stdout else '') + \
                        (c_stderr.decode("utf-8") if c_stderr else '')
                
                self._log_process(c_stdout, c_stderr, 'Client')

                cat_client_time_ssh = self._get_content_of_remote_file(
                    client, 
                    f"{client_log_dir.name}/time{('_'+str(client_id))  if self._config.concurrent_clients > 1 else '' }.json"
                )
                json_data = json.loads(cat_client_time_ssh)                
                run_start_time = datetime.fromtimestamp(int(str(json_data['start'])) / 1e9)
                if min_start_time is None or run_start_time < min_start_time:
                    min_start_time = run_start_time      
                      
                end_time = datetime.fromtimestamp(int(str(json_data['end'])) / 1e9)
                if max_end_time is None or end_time > max_end_time:
                    max_end_time = end_time
            self.logger.debug(f"start time: {min_start_time}")
            self.logger.debug(f"end time: {max_end_time}")

            testcase._start_time = min_start_time
            testcase._end_time = max_end_time

        except subprocess.TimeoutExpired as ex:
            self.logger.error(colored(f"Client expired: {ex}", 'red'))
            expired = True
        except Exception as ex:
            self.logger.error(colored(f"Client or server threw Exception: {ex}", 'red'))
            self.logger.error(colored(str(ex.with_traceback()), 'red'))
            expired = True
        finally:
            # Execute List of Client Post Run Scripts if given
            for client_script in self._config.client_postrunscript:
                self._run_script_on_machine(
                    host = client,
                    script_path = client_script.script, 
                )

            time.sleep(1)
            
            subprocess.Popen(f'ssh {self._testbed.server.hostname} pkill -f server', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            for server_script in self._config.server_postrunscript: # Post run scripts shouldn't be blocking
                self._run_script_on_machine(
                    host = server,
                    script_path = server_script.script, 
                )
            
            self._remove_all_variables_from_machine(
                server
            )

            self._remove_all_variables_from_machine(                    
                client
            )

            if 's' in locals():
                s_output = s.communicate()
                self._log_process(*s_output, 'Server')

            for dir in [server_log_dir.name, testcase.certs_dir()]:
                self._pull_directory_from_remote(server, dir)
            for dir in [sim_log_dir.name, client_log_dir.name]:
                self._pull_directory_from_remote(client, dir)

            if 's' in locals():
                if s.returncode == 127 \
                        or self._is_unsupported(s_output[0].decode("utf-8").splitlines()) \
                        or self._is_unsupported(s_output[1].decode("utf-8").splitlines()):
                    self.logger.error(colored(f"server does not support the test", 'red'))
                    status = TestResult.UNSUPPORTED
                elif not expired:
                    lines = output.splitlines()
                    if c.returncode == 127 or self._is_unsupported(lines):
                        self.logger.error(colored(f"client does not support the test", 'red'))
                        status = TestResult.UNSUPPORTED
                    elif c.returncode == 0 or any("client exited with code 0" in str(line) for line in lines):
                        try:
                            status = testcase.check(client.hostname, server.hostname)
                        except Exception as e:
                            self.logger.error(colored(f"testcase.check() threw Exception: {e}", 'red'))
                            self.logger.error(colored(traceback.format_exc()), 'red')
                            status = TestResult.FAILED
                    else:
                        self.logger.error(colored(f"Client or server failed", 'red'))
                        status = TestResult.FAILED
                else:
                    self.logger.error(colored(f"Client or server expired", 'red'))
                    status = TestResult.FAILED
            else:
                self.logger.error(colored(f"Client or server expired", 'red'))
                status = TestResult.FAILED

            if status == TestResult.SUCCEEDED:
                self.logger.info(colored(f"\u2713 Test successful", 'green'))
            elif status == TestResult.FAILED:
                self.logger.info(colored(f"\u2620 Test failed", 'red'))
            elif status == TestResult.UNSUPPORTED:
                self.logger.info(colored(f"? Test unsupported", 'yellow'))

            # save logs
            self.logger.removeHandler(log_handler)
            log_handler.close()
            if status == TestResult.FAILED or status == TestResult.SUCCEEDED:
                log_dir = self._log_dir + "/" + implementation_name + "_" + implementation_name + "/" + str(testcase)
                if log_dir_prefix:
                    log_dir += "/" + log_dir_prefix
                shutil.copytree(server_log_dir.name, log_dir + "/server")
                shutil.copytree(client_log_dir.name, log_dir + "/client")
                shutil.copytree(sim_log_dir.name, log_dir + "/sim")
                shutil.copyfile(log_file.name, log_dir + "/output.txt")
                if self._save_files and status == TestResult.FAILED:
                    shutil.copytree(testcase.www_dir(), log_dir + "/www")
                    try:
                        shutil.copytree(testcase.download_dir(), log_dir + "/downloads")
                    except Exception as exception:
                        self.logger.info("Could not copy downloaded files: %s", exception)

            if self._testbed:
                self._delete_remote_directory(server, server_log_dir.name)
                self._delete_remote_directory(server, testcase.www_dir())
                self._delete_remote_directory(server, testcase.certs_dir())
                self._delete_remote_directory(client, client_log_dir.name)
                self._delete_remote_directory(client, sim_log_dir.name)
                self._delete_remote_directory(client, testcase.download_dir())

            testcase.cleanup()
            server_log_dir.cleanup()
            client_log_dir.cleanup()
            sim_log_dir.cleanup()
            self.logger.debug("Test took %ss", (datetime.now() - start_time).total_seconds())

            # measurements also have a value
            if hasattr(testcase, "result"):
                value = testcase.result()
            else:
                value = None

            return status, value

    def _setup_env(self, host: Host, path: str) -> None:
        try:
            if host.role in self._prepared_envs:
                return

            venv_command = self._get_venv(host)
            cmd = venv_command + "; ./setup-env.sh"

            cmd = f'ssh {host.hostname} "cd {path}; {cmd}"'

            self.logger.debug(f'Setup:\n {cmd}\n')

            setup_env = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self._log_process(*setup_env.communicate(timeout=120), 'setup_env')
            self._prepared_envs.add(host.role)
        except subprocess.TimeoutExpired as ex:
            self.logger.error(colored(f"Setup environment timeout for {host.hostname} ({host.role})", 'red'))
            return ex
        return
    
    def _run_measurement(self, implementation_name: str, server: Host, client: Host, test: Callable[[], TestCase], nb_paths: int, index_offset: int) -> MeasurementResult:
        values = []
        for i in range(0, test.repetitions()):
            self.logger.info(f"Running repetition {i + 1}/{test.repetitions()}")
            result, value = self._run_testcase(implementation_name, server, client, test, nb_paths, "%d" % (i + 1 + index_offset))
            if result != TestResult.SUCCEEDED:
                if self._continue_on_error:
                    continue
                res = MeasurementResult()
                res.result = result
                res.details = ""
                res.nb_paths = nb_paths
                return res
            values.append(value)

        self.logger.debug(values)
        res = MeasurementResult()
        res.result = TestResult.SUCCEEDED
        res.all_infos = values
        res.details = ""
        res.nb_paths = nb_paths

        if len(values) > 0:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            res.details = "{:.2f} (± {:.2f}) {}".format(
                mean, stdev, test.unit()
            )
        else:
            res.result = TestResult.FAILED
        return res
                
    def _print_results(self) -> None:
        self.logger.info("\n\nRun took %s", datetime.now() - self._start_time)
        for measurement_name, implementations in self.measurement_results.items():
            table = prettytable.PrettyTable()
            table.field_names = ["Implementation", "Number of Paths", "Details"]
            table.title = measurement_name.name()  # Assuming MeasurementNames has a.name() method
            for implementation_name, paths in implementations.items():
                for nb_paths, result in paths.items():
                    table.add_row([implementation_name, nb_paths, result.details])  # Assuming MeasurementResult has a.details attribute
            self.logger.info("\n" + str(table))

    def _get_commit_hash(self) -> str:
        p = subprocess.Popen(
            "git rev-parse HEAD",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = p.communicate(timeout=10)
        return stdout.decode("utf-8").rstrip("\n")
    
    def _export_results(self):
        if not self._output:
            self._output = os.path.join(self._log_dir, 'result.json')
            if not os.path.exists(self._log_dir):
                os.makedirs(self._log_dir)

        self.logger.info(f'Exporting results to {self._output}')

        out = {
            "runner_commit_hash": self._get_commit_hash(),
            "runner_start_time_unix_timestamp": self._start_time.timestamp(),
            "runner_end_time_unix_timestamp": datetime.now().timestamp(),
            "log_dir": self._log_dir,
            "implementations": self._config.implementations,
            "build_script": self._config.build_script,
            "tests": {
                x.abbreviation(): {
                    "name": x.name(),
                    "desc": x.desc(),
                }
                for x in self._tests + self._measurements
            },
            "quic_draft": QUIC_DRAFT,
            "quic_version": QUIC_VERSION,
            "config": self._config.basename, 
            "testbed": self._testbed.basename,
            "results": [],
            "measurements": [],
        }

        measurements = []
        for measurement, implementation_result in self.measurement_results.items():
            for implementation, result in implementation_result.items():
                for _, result in result.items():
                    if measurement.name() == "goodput":
                        measurements.append(
                            {
                                "name": measurement.name(),
                                "implementation": implementation,
                                "abbr": measurement.abbreviation(),
                                "filesize": measurement.FILESIZE,
                                "average": result.details,
                                "details": result.all_infos,
                                "nb_paths": result.nb_paths,
                                "concurrent_clients": measurement.CONCURRENT_CLIENTS,
                            }
                        )
                    elif measurement.name() ==  "throughput":
                        measurements.append(
                            {
                                "name": measurement.name(),
                                "implementation": implementation,
                                "abbr": measurement.abbreviation(),
                                "duration": measurement.DURATION,
                                "average": result.details,
                                "details": result.all_infos,
                                "nb_paths": result.nb_paths,
                                "concurrent_clients": measurement.CONCURRENT_CLIENTS,
                            }
                        )
        out["measurements"].append(measurements)

        f = open(self._output, "w")
        json.dump(out, f)
        f.close()

        # Copy server and client pre- and postscripts into logdir root
        for server_script in self._config.server_prerunscript:
            shutil.copyfile(server_script.script, 
                            os.path.join(self._log_dir, 'spre_' + \
                                         server_script.script.split("/")[1]
                                        )
            )
        for server_script in self._config.server_postrunscript:
            shutil.copyfile(server_script.script, 
                        os.path.join(self._log_dir, 'spost_' + \
                                     server_script.script.split("/")[1]
                                    )
        )
        for client_script in self._config.client_prerunscript:
            shutil.copyfile(client_script.script, 
                            os.path.join(self._log_dir, 'cpre_' + \
                                         client_script.script.split("/")[1]
                                        )
            )
        for client_script in self._config.client_postrunscript:
            shutil.copyfile(client_script.script, 
                        os.path.join(self._log_dir, 'cpost_' + \
                                     client_script.script.split("/")[1]
                                    )
        )
            
    def _iterate_tests(self):
        total_tests = len(self._config.implementations) * self._config.repetitions * len(self._config.nb_paths)
        finished_tests = 0
        
        # run the measurements
        for implementation_name in self._config.implementations:
            for measurement in self._measurements:
                for nb_paths in self._config.nb_paths:
                    self.logger.info(
                        colored(
                            "\n---\n"
                            + f"{finished_tests + 1}/{total_tests}\n"
                            + f"Measurement: {measurement.name()}\n"
                            + f"Implementation: {implementation_name}\n"
                            + f"Server: {self._testbed.server.hostname}  "
                            + f"Client: {self._testbed.client.hostname}\n"
                            + f"Paths: {nb_paths}\n"
                            + "---",
                            'magenta',
                            attrs=['bold']
                        )
                    )

                    res = self._run_measurement(implementation_name, self._testbed.server, self._testbed.client, measurement, nb_paths, finished_tests)
                    if res.result != TestResult.SUCCEEDED:
                        return 1
                        
                    self.measurement_results[measurement][implementation_name][nb_paths] = res
                    finished_tests += self._config.repetitions
        return 0
        
    def run(self):    
        self.logger.info(colored(f"Testbed: {self._testbed.basename}", 'white', attrs=['bold']))
        # Copy implementations to hosts
        self._copy_implementations()
        self._setup_hosts()
        
        nr_failed = self._iterate_tests()
    
        self._print_results()
        self._export_results()
        return nr_failed