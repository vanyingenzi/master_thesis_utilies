from .args_parser import Arguments
from .models import TestbedConfig
import logging, pathlib, os, subprocess

class PerfomanceRunner:

    def __init__(self, testbed: TestbedConfig, ) -> None:
        self._testbed = testbed
        self.logger = logging.getLogger()

    def _push_directory_to_remote(self, host, src, dst=None, normalize=True):
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
        except subprocess.TimeoutExpired:
            self.logger.debug(
                f'Timeout when moving files {src} to host {host}')
        return

    def _copy_implementations(self):
        if self._testbed and self._:
            for client in self._clients:
                self._push_directory_to_remote(
                    self._testbed_client,
                    os.path.join(
                        self._implementations_directory,
                        self._implementations[client]['path'],
                        ''  # This prevents that rsync copies the directory into itself, adds trailing slash
                    ),
                    self._implementations[client]['path'],
                    normalize=False
                )
            for server in self._servers:
                self._push_directory_to_remote(
                    self._testbed_server,
                    os.path.join(
                        self._implementations_directory,
                        self._implementations[server]['path'],
                        ''
                    ),
                    self._implementations[server]['path'],
                    normalize=False
                )

    def _setup_runner(self, args: Arguments) -> None:
        pass 

    def run(self): 
        # Copy implementations to hosts
        # Run at Server
        # Run at Client
        # Stop server
        # Measurements Collection
        # Clean up Env
        pass 
        