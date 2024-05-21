import abc
import filecmp
import logging
import os
import random
import re
import string
import subprocess
import sys
import tempfile
from datetime import timedelta, datetime
from enum import Enum, IntEnum
from .trace import Direction, PacketType, TraceAnalyzer
from typing import List

from enum import Enum

current_script_directory = os.path.dirname(os.path.abspath(__file__))


class TestResult(Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"

KB = 1 << 10
MB = 1 << 20
GB = 1 << 30

QUIC_DRAFT = 34  # draft-34
QUIC_VERSION = hex(0x1)


class Perspective(Enum):
    SERVER = "server"
    CLIENT = "client"


class ECN(IntEnum):
    NONE = 0
    ECT1 = 1
    ECT0 = 2
    CE = 3


def random_string(length: int):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def generate_cert_chain(directory: str, length: int = 1):
    cmd = f"{current_script_directory}/certs.sh " + directory + " " + str(length)
    r = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    logging.debug("%s", r.stdout.decode("utf-8"))
    if r.returncode != 0:
        logging.info("Unable to create certificates")
        sys.exit(1)


class TestCase(abc.ABC):
    _files = []
    _www_dir = None
    _client_keylog_file = None
    _server_keylog_file = None
    _download_dir = None
    _sim_log_dir = None
    _cert_dir = None
    _cached_server_trace = None
    _cached_client_trace = None
    _start_time: datetime | None = None
    _end_time: datetime | None = None
    _server_ip = None
    _server_port = None
    _server_name = None
    _link_bandwidth = None
    _client_delay = None
    _server_delay = None
    _concurrent_clients = None

    def __init__(
        self,
        sim_log_dir: tempfile.TemporaryDirectory,
        client_keylog_file: str,
        server_keylog_file: str,
        client_log_dir: str,
        server_log_dir: str,
        client_qlog_dir: str,
        server_qlog_dir: str,
        link_bandwidth: str,
        client_delay: str,
        server_delay: str,
        server_ip: str = "127.0.0.2",
        server_name: str = "server",
        server_port: int = 4433,
        concurrent_clients: int = 1,
    ):
        self._server_keylog_file = server_keylog_file
        self._client_keylog_file = client_keylog_file
        self._server_log_dir = server_log_dir
        self._client_log_dir = client_log_dir
        self._server_qlog_dir = server_qlog_dir
        self._client_qlog_dir = client_qlog_dir
        self._files = []
        self._sim_log_dir = sim_log_dir
        self._server_ip = server_ip
        self._server_port = server_port
        self._server_name = server_name
        self._link_bandwidth = link_bandwidth
        self._client_delay = client_delay
        self._server_delay = server_delay
        self._concurrent_clients = concurrent_clients

    @abc.abstractmethod
    def name(self):
        pass

    @abc.abstractmethod
    def desc(self):
        pass

    def __str__(self):
        return self.name()

    def testname(self, p: Perspective):
        """ The name of testcase presented to the endpoint Docker images"""
        return self.name()

    @staticmethod
    def scenario() -> str:
        """ Scenario for the ns3 simulator """
        return "simple-p2p --delay=15ms --bandwidth=10Mbps --queue=25"

    @staticmethod
    def timeout() -> int:
        """ timeout in s """
        return 60

    @staticmethod
    def additional_envs() -> List[str]:
        return [""]

    @staticmethod
    def additional_containers() -> List[str]:
        return [""]

    @staticmethod
    def use_tcpdump() ->bool:
        return True

    @staticmethod
    def use_ifstat() -> bool:
        return False

    @staticmethod
    def use_qlog() -> bool:
        return True

    def urlprefix(self) -> str:
        """ URL prefix """
        return f"https://{self.ip()}:{self.port()}/"

    def ip(self):
        return self._server_ip

    def port(self):
        return str(self._server_port)

    def servername(self):
        return self._server_name

    def www_dir(self):
        if not self._www_dir:
            self._www_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="www_")
        return self._www_dir.name + "/"

    def download_dir(self):
        if not self._download_dir:
            self._download_dir = tempfile.TemporaryDirectory(
                dir="/tmp", prefix="download_"
            )
        return self._download_dir.name + "/"

    def certs_dir(self):
        if not self._cert_dir:
            self._cert_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="certs_")
            generate_cert_chain(self._cert_dir.name)
        return self._cert_dir.name + "/"

    def _is_valid_keylog(self, filename) -> bool:
        if not os.path.isfile(filename) or os.path.getsize(filename) == 0:
            return False
        with open(filename, "r") as file:
            if not re.search(
                r"^SERVER_HANDSHAKE_TRAFFIC_SECRET", file.read(), re.MULTILINE
            ):
                logging.info("Key log file %s is using incorrect format.", filename)
                return False
        return True

    def _keylog_file(self) -> str:
        if self._is_valid_keylog(self._client_keylog_file):
            logging.debug("Using the client's key log file.")
            return self._client_keylog_file
        elif self._is_valid_keylog(self._server_keylog_file):
            logging.debug("Using the server's key log file.")
            return self._server_keylog_file
        logging.debug("No key log file found.")

    def is_bandwidth_limited(self) -> bool:
        return self._link_bandwidth is not None

    def bandwidth(self) -> str:
        return self._link_bandwidth

    def is_client_delay_added(self) -> bool:
        return self._client_delay is not None

    def client_delay(self) -> str:
        return self._client_delay
    
    def is_server_delay_added(self) -> bool:
        return self._server_delay is not None

    def server_delay(self) -> str:
        return self._server_delay

    def _client_trace(self):
        if self._cached_client_trace is None:
            self._cached_client_trace = TraceAnalyzer(
                self._sim_log_dir.name + "/trace.pcap", self._keylog_file(),
                ip4_server=self._server_ip,
                port_server=self._server_port,
            )
        return self._cached_client_trace

    def _server_trace(self):
        if self._cached_server_trace is None:
            self._cached_server_trace = TraceAnalyzer(
                self._sim_log_dir.name + "/trace.pcap", self._keylog_file(),
                ip4_server=self._server_ip,
                port_server=self._server_port,
            )
        return self._cached_server_trace

    def _generate_random_file(self, size, filename_len=10, host=None) -> str:
        filename = random_string(filename_len)
        path = self.www_dir() + filename

        if host:  # testbed mode
            # https://superuser.com/questions/792427/creating-a-large-file-of-random-bytes-quickly
            cmd = f'ssh {host} \'touch {path} && shred -n 1 -s {size} {path}\''
            logging.debug(cmd)
            p = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = p.communicate()

        else:
            # See https://realpython.com/python-random/ for byte generation
            # with urandom
            random_bytes = os.urandom(size)
            with open(path, "wb") as f:
                f.write(random_bytes)
        logging.debug("Generated random file: %s of size: %d", path, size)
        return filename

    def _retry_sent(self) -> bool:
        return len(self._client_trace().get_retry()) > 0

    def _check_version(self) -> bool:
        versions = [hex(int(v, 0)) for v in self._get_versions()]
        if len(versions) != 1:
            logging.info("Expected exactly one version. Got %s", versions)
            return False
        if QUIC_VERSION not in versions:
            logging.info("Wrong version. Expected %s, got %s", QUIC_VERSION, versions)
            return False
        return True

    def _check_files(self, client=None, server=None) -> bool:
        grep_server_file_cmd = f'ssh {server} \'cat {self.download_dir() + "server.log"} | grep ERROR \''
        logging.debug(grep_server_file_cmd)
        server_p = subprocess.run(
            grep_server_file_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if server_p.returncode == 0:
            logging.info(f'Error found in server log: {server_p.stdout.decode()}')
            return False
        
        grep_client_file_cmd = f'ssh {client} \'cat {self.download_dir() + "client.log"} | grep ERROR \''
        logging.debug(grep_client_file_cmd)
        client_p = subprocess.run(
            grep_client_file_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if client_p.returncode == 0:
            logging.info(f'Error found in client log: {client_p.stdout.decode()}')
            return False
        return True

    def _check_version_and_files(self) -> bool:

        if not self._check_version():
            return False
        return self._check_files()


    def _count_handshakes(self) -> int:
        """ Count the number of QUIC handshakes """
        tr = self._server_trace()
        # Determine the number of handshakes by looking at Initial packets.
        # This is easier, since the SCID of Initial packets doesn't changes.
        return len(set([p.scid for p in tr.get_initial(Direction.FROM_SERVER)]))

    def _get_versions(self) -> set:
        """ Get the QUIC versions """
        tr = self._server_trace()
        return set([p.version for p in tr.get_initial(Direction.FROM_SERVER)])

    def _payload_size(self, packets: List) -> int:
        """ Get the sum of the payload sizes of all packets """
        size = 0
        for p in packets:
            if hasattr(p, "long_packet_type"):
                if hasattr(p, "payload"):  # when keys are available
                    size += len(p.payload.split(":"))
                else:
                    size += len(p.remaining_payload.split(":"))
            else:
                if hasattr(p, "protected_payload"):
                    size += len(p.protected_payload.split(":"))
        return size

    def cleanup(self):
        if self._www_dir:
            self._www_dir.cleanup()
            self._www_dir = None
        if self._download_dir:
            self._download_dir.cleanup()
            self._download_dir = None

    @abc.abstractmethod
    def get_paths(self, max_size=None, host=None):
        pass

    @abc.abstractmethod
    def check(self, client=None, server=None) -> TestResult:
        pass


class Measurement(TestCase):
    REPETITIONS = 20
    DURATION: int = 0

    @abc.abstractmethod
    def result(self) -> float:
        pass

    @staticmethod
    @abc.abstractmethod
    def unit() -> str:
        pass

    @classmethod
    def repetitions(cls) -> int:
        return cls.REPETITIONS

    @staticmethod
    def use_tcpdump() ->bool:
        return False

    @staticmethod
    def use_ifstat() -> bool:
        return False

    @staticmethod
    def use_qlog() -> bool:
        return False

class MeasurementGoodput(Measurement):
    FILESIZE = 1 * GB
    CONCURRENT_CLIENTS = 1
    _result = 0.0

    @staticmethod
    def name():
        return "goodput"

    @staticmethod
    def timeout():
        return 180

    @staticmethod
    def unit() -> str:
        return "Mbps"

    @staticmethod
    def testname(p: Perspective):
        return "goodput"

    @staticmethod
    def abbreviation():
        return "G"

    @staticmethod
    def desc():
        return "Measures connection goodput as baseline."

    def get_paths(self, max_size=None, host=None):
        if max_size and max_size < self.FILESIZE:
            logging.debug(f'Limit filesize for {self.name()} to {max_size}')
            self.FILESIZE = max_size
        self._files = [
        ]
        return self._files

    def check(self, client=None, server=None) -> TestResult:
        if not self._check_files(client=client, server=server):
            return TestResult.FAILED

        time = (self._end_time - self._start_time) / timedelta(seconds=1)
        goodput = (8 * self.FILESIZE * self.CONCURRENT_CLIENTS) / time / 10**6
        logging.info(
            f"Transferring {(self.FILESIZE * self.CONCURRENT_CLIENTS) / 10**6:.2f} MB took {time:.3f} s. With {self.CONCURRENT_CLIENTS} concurrent clients. Goodput: {goodput:.3f} {self.unit()}",
        )
        self._result = goodput

        return TestResult.SUCCEEDED

    def result(self) -> float:
        return self._result

from datetime import datetime
import numpy as np

class MeasurementThroughput(Measurement):
    CONCURRENT_CLIENTS = 1
    FILESIZE=0
    _result = 0.0
    
    @staticmethod
    def name():
        return "throughput"
    
    def timeout(self):
        return self.DURATION + 90 # Transfer time + 90s idle time (cause of strace)
    
    @staticmethod
    def unit() -> str:
        return "Mbps"
    
    @staticmethod
    def testname(p: Perspective):
        return "throughput"
    
    @staticmethod
    def abbreviation():
        return "T"
    
    @staticmethod
    def desc():
        return "Measures connection throughput."
    
    def _is_valid_timestamp(self, timestamp):
        pattern = r"^[0-2][0-9]:[0-5][0-9]:[0-5][0-9]$"
        return bool(re.match(pattern, timestamp))

    def extract_ifstat_data_file(self, filecontent: str) -> List[float]:
        lines = filecontent.splitlines()
        lines = [line.strip() for line in lines if len(line.strip()) != 0]
        data_per_second = []
        for line in lines:
            timestamp = line.split()[0]
            if not self._is_valid_timestamp(timestamp):
                continue
            timestamp_datetime = datetime.strptime(timestamp, '%H:%M:%S')
            timestamp_datetime = timestamp_datetime.replace(year=self._start_time.year, month=self._start_time.month, day=self._start_time.day)
            if not (self._start_time <= timestamp_datetime and timestamp_datetime <= self._end_time):
                continue
            data = sum([float(measurement) for measurement in line.split()[1:]])
            data_per_second.append(data)
        trimed_data = data_per_second[2:-2] # Remove first and last 2 seconds
        sum_data = sum(trimed_data)
        return sum_data * 8 / 1024 # Convert to Mb

    def _get_ifstat_file_throughput(self, client):
        cmd = f'ssh {client} \'cat {self._client_log_dir + "/ifstat_monitor.txt"}\''
        logging.debug(cmd)
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            logging.error(f'Error while getting ifstat file: {stderr.decode()}')
            return None
        return stdout.decode()

    def check(self, client=str | None, server=str | None) -> TestResult:
        if not self._check_files(client=client, server=server):
            return TestResult.FAILED
        
        time = (self._end_time - self._start_time) / timedelta(seconds=1) # Transfer time
        time -= 4 # Remove first and last 2 seconds
        client_ifstat = self._get_ifstat_file_throughput(client)
        total_usage = self.extract_ifstat_data_file(client_ifstat)
        throughput = total_usage / time
        logging.info(
            f"Bandwidth usage (throughput) {throughput:.3f} {self.unit()}, with {self.CONCURRENT_CLIENTS} concurrent clients.",
        )
        self._result = throughput
        return TestResult.SUCCEEDED
    
    def get_paths(self, max_size=None, host=None):
        if max_size and max_size < self.FILESIZE:
            logging.debug(f'Limit filesize for {self.name()} to {max_size}')
            self.FILESIZE = max_size
        self._files = [
        ]
        return self._files
    
    def result(self) -> float:
        return self._result

class MeasurementQlog(Measurement):
    FILESIZE = 200 * MB
    _result = 0.0

    @staticmethod
    def name():
        return "qlog"

    @staticmethod
    def timeout():
        return 80

    @staticmethod
    def unit() -> str:
        return "Mbps"

    @staticmethod
    def testname(p: Perspective):
        return "qlog"

    @staticmethod
    def abbreviation():
        return "Q"

    @staticmethod
    def desc():
        return "Measures connection goodput while running qlog."

    @staticmethod
    def use_qlog() -> bool:
        return True

    def get_paths(self, max_size=None, host=None):
        self._files = [self._generate_random_file(min(self.FILESIZE, max_size) if max_size else self.FILESIZE )]
        return self._files

    def check(self, client=None, server=None) -> TestResult:

        result_status = TestResult.SUCCEEDED

        # Check if qlog file exists
        client_qlogs = [os.path.join(self._client_qlog_dir, name) for name in os.listdir(self._client_qlog_dir)]
        server_qlogs = [os.path.join(self._server_qlog_dir, name) for name in os.listdir(self._server_qlog_dir)]

        if len(client_qlogs) < 1:
            logging.info(f"Expected at least 1 qlog file from client. Got: {len(client_qlogs)}")
            result_status = TestResult.FAILED

        if len(server_qlogs) < 1:
            logging.info(f"Expected at least 1 qlog file from server. Got: {len(server_qlogs)}")
            result_status = TestResult.FAILED

        logging.debug(f"Deleting {len(client_qlogs + server_qlogs)} qlogs")
        for f in client_qlogs + server_qlogs:
            os.remove(f)

        if not self._check_files():
            result_status = TestResult.FAILED

        if result_status == TestResult.FAILED:
            return result_status

        time = (self._end_time - self._start_time) / timedelta(seconds=1)
        goodput = (8 * self.FILESIZE) / time / 10**6
        logging.info(
            f"Transferring {self.FILESIZE / 10**6:.2f} MB took {time:.3f} s. Goodput (with qlog): {goodput:.3f} {self.unit()}",
        )
        self._result = goodput
        return TestResult.SUCCEEDED

    def result(self) -> float:
        return self._result


class MeasurementOptimize(MeasurementGoodput):

    @staticmethod
    def name():
        return "optimize"

    @staticmethod
    def timeout():
        return 80

    @staticmethod
    def testname(p: Perspective):
        return "optimize"

    @staticmethod
    def abbreviation():
        return "Opt"

    @staticmethod
    def desc():
        return "Measures connection goodput with optimizations."


TESTCASES = [
]

MEASUREMENTS = {
    tc.name(): tc for tc in [MeasurementGoodput, MeasurementThroughput]
}

class MeasurementNames(Enum):
    Throughput: str = "throughput"
    Goodput: str = "goodput"