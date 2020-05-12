import logging
import time
from fabric import Connection


class SshWorker:
    """
    Wrap operations at work via ssh
    """

    def __init__(self, ip_address, private_key_path, user='root'):
        self.ip = ip_address
        self.logger = logging.getLogger('ssh_worker')
        self.logger.debug(f"Establishing connection to {ip_address}")
        self.connection = Connection(ip_address, user=user,
                                     connect_kwargs={"key_filename": [private_key_path]})

    def __del__(self):
        self.logger.debug("Closing SSH connection")
        self.connection.close()

    def is_alive(self):
        retries = 5
        while retries > 0:
            self.logger.debug(f"Trying to connect to {self.ip} ({retries} left)")
            retries = retries - 1
            try:
                self.connection.open()
                assert self.hostname().ok
            except ConnectionRefusedError:
                self.logger.info(f"Worker {self.ip} refused connection.")
                time.sleep(5)
            except AssertionError:
                self.logger.info(f"Worker {self.ip} returned invalid output.")
                time.sleep(5)
            except NoValidConnectionsError:
                self.logger.info(f"Worker {self.ip} returned NoValidConnectionsError.")
                time.sleep(5)
        return True

    def hostname(self):
        return self.connection.run('hostname ; whoami ; id')

    def bootstrap_host(self):
        return self.connection.run(
            'export DEBIAN_FRONTEND=noninteractive; '
            'apt-get update && '
            'apt-get install --no-install-recommends -yy '
            'masscan nmap;'
        )

    def masscan(self):
        return self.connection.run(
            'export NOBANNER_TCP_PORTS="[80, 443, 8080]"; '
            'masscan -iL /tmp/targets.list'
            ' --open-only'
            ' -oJ /tmp/output.json'
            ' --rate 10000'
            ' -p 1-65535 -p U:1-65535'
        )

