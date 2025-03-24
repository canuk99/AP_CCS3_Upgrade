#!/usr/bin/env python3

import csv
from pexpect import pxssh
import os
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def ssh_and_run_commands(host):
    """SSH into the host and run the specified commands."""
    try:
        s = pxssh.pxssh(options={
            "StrictHostKeyChecking": "no",
            "UserKnownHostsFile": "/dev/null"
        })
        s.sync_multiplier = 8
        s.timeout = 60
        hostname = host
        username = 'root'
        password = os.getenv('SSH_PASSWORD')
        if not password:
            raise ValueError("SSH_PASSWORD environment variable not set")

        s.login(hostname, username, password)
        filename = "/tmp/ap5_fw_10_5_5_135352_135354M.dist"
        s.sendline(f"ls {filename}")
        s.prompt()  # Match the prompt

        output = s.before.decode("utf-8")  # Decode the output to a string

        if f"ls: cannot access '{filename}': No such file or directory" in output:
            print(f"File {filename} not found on {host}")
        else:
            print(f"File {filename} found.")
            s.sendline(f"apua.py -v install full {filename}")
            try:
                s.expect("ap upgrade process finished", timeout=360)
                print("Upgrade process finished message received.")
                time.sleep(5)
                s.sendline("")
                s.sendline("")
                s.sendline("")
                s.sendline("/bin/reboot")
                s.prompt()
                time.sleep(10)  # Wait for 2 seconds to ensure the command is processed
                print(f"Reboot command sent to {host}")
            except pexpect.exceptions.TIMEOUT:
                print("Timeout waiting for upgrade process to finish.")

        return True

    except pexpect.exceptions.ExceptionPxssh as e:
        print("pxssh failed on login.")
        print(host)
        print(e)
        return False

def process_host(host):
    """Process a single host: ping and SSH."""
    if ssh_and_run_commands(host):
        return (host, True)
    else:
        return (host, False)

def main(csv_file):
    good_hosts = []
    bad_hosts = []

    with open(csv_file, mode='r') as file:
        csv_reader = csv.DictReader(file, delimiter=',')
        hosts = [row['SNMP_Host'] for row in csv_reader]

    with ThreadPoolExecutor(max_workers=80) as executor:
        future_to_host = {executor.submit(process_host, host): host for host in hosts}
        for future in as_completed(future_to_host):
            host, success = future.result()
            if success:
                good_hosts.append(host)
            else:
                bad_hosts.append(host)

    print("Good Hosts:")
    for host in good_hosts:
        print(host)

    print("\nBad Hosts:")
    for host in bad_hosts:
        print(host)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SSH into hosts listed in a CSV file and run commands.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    args = parser.parse_args()
    main(args.csv_file)

