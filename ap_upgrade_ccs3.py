#!/usr/bin/env python3
# ap_upgrade_ccs3.py
# This script pushes an upgrade script to a list of hosts.
# The hosts are read from a CSV file.
# The script uses the pexpect library to SSH into the hosts and run the upgrade script.
# The script uses the ThreadPoolExecutor to process multiple hosts concurrently.
# The script also uses the subprocess library to ping the hosts before pushing the upgrade.
# The script prints the list of good and bad hosts at the end.

import csv
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from pexpect import pxssh
import time

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        print(f"Host {host} is not reachable.")
        return False

def push_upgrade(host):
    """Push upgrade script to the host using SSH."""
    try:
        client = pxssh.pxssh(timeout=600)  # Set SSH timeout to 5 minutes (300 seconds)
        username = 'root'
        password = os.getenv('SSHPASS')
        if not password:
            raise ValueError("No SSH password found. Please set the SSHPASS environment variable.")

        if not client.login(host, username, password):
            print(f"SSH login failed for {host}")
            return False

        # Change directory to /tmp
        cd_command = "cd /tmp"
        client.sendline(cd_command)
        client.prompt()
        time.sleep(2) 
        output = client.before.decode('utf-8').splitlines()
        output = [line.strip() for line in output if line.strip()]
        #print(f"Output from cd /tmp: {output}")
        # Verify if the file exists before changing permissions
        web_command = "/onramp/bin/web_ctrl set_tcp_config -t 0 -m 0 -s 192.168.0.1 -p 5051 -h 192.168.30.107"
        client.sendline(web_command)
        client.prompt()
        time.sleep(5)  # Increase delay to ensure the command has enough time to execute
        output = client.before.decode('utf-8').splitlines()
        output = [line.strip() for line in output if line.strip()]
        #print(f"Output before chmod command: {output}")
        # Verify the current directory
        pwd_command = "pwd"
        client.sendline(pwd_command)
        client.prompt()
        output = client.before.decode('utf-8').splitlines()
        output = [line.strip() for line in output if line.strip()]
        #print(f"Output from pwd command: {output}")

        # Verify if the file exists before changing permissions
        verify_command = "ls -l /tmp/yocto_ap6_upgrade.sh"
        client.sendline(verify_command)
        client.prompt()
        time.sleep(5)  # Increase delay to ensure the command has enough time to execute
        output = client.before.decode('utf-8').splitlines()
        output = [line.strip() for line in output if line.strip()]
        #print(f"Output before chmod command: {output}")

        # Check if permissions need to be changed
        if len(output) > 1 and '-rwxr-xr--' not in output[1]:
            # Execute the chmod command
            chmod_command = "chmod 754 /tmp/yocto_ap6_upgrade.sh"
            client.sendline(chmod_command)
            client.prompt()
            time.sleep(2)  # Increase delay to ensure the command has enough time to execute
            output = client.before.decode('utf-8').splitlines()
            output = [line.strip() for line in output if line.strip()]
            #print(f"Output from chmod command: {output}")

            # Verify if the file permissions were changed
            client.sendline(verify_command)
            client.prompt()
            output = client.before.decode('utf-8').splitlines()
            output = [line.strip() for line in output if line.strip()]
            print(f"Output after chmod command: {output}")
        else:
            print(" ")
            #print("Permissions are already set correctly or file does not exist.")

        # Execute the upgrade script with the argument
        command = "echo ./yocto_ap6_upgrade.sh ap5_fw_10_5_5_135352_135354M.dist"
        client.sendline(command)
        client.prompt()
        output = client.before.decode('utf-8').splitlines()
        output = [line.strip() for line in output if line.strip()]
        print(f"Output from command: {output}")

        # Record the time
        print(f"Command executed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        client.logout()
        return True
    except Exception as e:
        print(f"Failed to SSH into {host}: {e}")
        return False

def process_host(host):
    """Process a single host: ping and push upgrade."""
    if ping_host(host):
        if push_upgrade(host):
            return (host, 'good')
        else:
            return (host, 'bad')
    else:
        return (host, 'bad')

def read_hosts_from_csv(csv_file):
    """Read hosts from the CSV file."""
    try:
        print(f"Reading hosts from CSV file: {csv_file}")
        with open(csv_file, mode='r') as file:
            csv_reader = csv.DictReader(file, delimiter=',')
            if 'SNMP_Host' not in csv_reader.fieldnames:
                raise ValueError("CSV file is missing 'SNMP_Host' header.")
            return [row['SNMP_Host'] for row in csv_reader]
    except FileNotFoundError:
        print(f"Error: The file {csv_file} was not found.")
        exit(1)
    except Exception as e:
        print(f"Error reading CSV file {csv_file}: {e}")
        exit(1)

def process_hosts(hosts):
    """Process all hosts concurrently."""
    print("Processing all hosts concurrently.")
    good_hosts = []
    bad_hosts = []

    with ThreadPoolExecutor(max_workers=25) as executor:
        future_to_host = {executor.submit(process_host, host): host for host in hosts}
        for future in as_completed(future_to_host):
            host, status = future.result()
            if status == 'good':
                good_hosts.append(host)
            else:
                bad_hosts.append(host)

    return good_hosts, bad_hosts

def print_hosts(good_hosts, bad_hosts):
    """Print the lists of good and bad hosts."""
    print("Good Hosts:")
    for host in good_hosts:
        print(host)
    print("\nBad Hosts:")
    for host in bad_hosts:
        print(host)

def main(csv_file):
    password = os.getenv('SSHPASS')
    if not password:
        raise ValueError("No SSH password found. Please set the SSHPASS environment variable.")

    print(f"Reading hosts from CSV file: {csv_file}")
    good_hosts = []
    bad_hosts = []

    with open(csv_file, mode='r') as file:
        csv_reader = csv.DictReader(file, delimiter=',')
        hosts = [row['SNMP_Host'] for row in csv_reader]

    print("Starting to process hosts.")
    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_host = {executor.submit(process_host, host): host for host in hosts}
        for future in as_completed(future_to_host):
            host, status = future.result()
            if status == 'good':
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
    parser = argparse.ArgumentParser(description='Push run upgrade script to hosts listed in a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')

    args = parser.parse_args()
    main(args.csv_file)