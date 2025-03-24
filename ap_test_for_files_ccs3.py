#!/usr/bin/env python3
#
# This tests to see if the files are there.

import csv
import paramiko
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from pexpect import pxssh

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def ssh_and_run_commands(host, files):
    """SSH into the host and run the specified commands."""
    try:
        client = pxssh.pxssh()
        username = 'root'
        password = os.getenv('SSH_PASSWORD')
        if not password:
            raise ValueError("No SSH password found. Please set the SSH_PASSWORD environment variable.")

        if not client.login(host, username, password):
            print(f"SSH login failed for {host}")
            return

        sftp = client.sftp()
        for filename in files:
            try:
                sftp.stat(filename)
                print(f"File {filename} found on {host}.")
            except FileNotFoundError:
                print(f"File {filename} not found on {host}.")
        sftp.close()
        client.logout()
    except Exception as e:
        print(f"Failed to SSH into {host}: {e}")

def check_host_reachability(host):
    """Check if the host is reachable."""
    return ping_host(host)

def check_host_file(host):
    """Check if the specific file exists on the host."""
    ssh_and_run_commands(host)

def process_host(host, files):
    """Process a single host: ping and check files."""
    if ping_host(host):
        ssh_and_run_commands(host, files)
        return (host, 'good')
    else:
        return (host, 'bad')

def read_hosts_from_csv(csv_file):
    with open(csv_file, mode='r') as file:
        csv_reader = csv.DictReader(file, delimiter=',')
        return [row['SNMP_Host'] for row in csv_reader]

def process_hosts(hosts, files):
    good_hosts = []
    bad_hosts = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_host = {executor.submit(process_host, host, files): host for host in hosts}
        for future in as_completed(future_to_host):
            host, status = future.result()
            if status == 'good':
                good_hosts.append(host)
            else:
                bad_hosts.append(host)

    return good_hosts, bad_hosts

def print_hosts(good_hosts, bad_hosts):
    print("Good Hosts:")
    for host in good_hosts:
        print(host)
    print("\nBad Hosts:")
    for host in bad_hosts:
        print(host)

def main(csv_file, files):
    hosts = read_hosts_from_csv(csv_file)
    good_hosts, bad_hosts = process_hosts(hosts, files)
    print_hosts(good_hosts, bad_hosts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ping hosts and check for specific files via SSH.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    parser.add_argument('files', nargs='+', help='Path(s) to the file(s) to be checked.')

    args = parser.parse_args()
    main(args.csv_file, args.files)