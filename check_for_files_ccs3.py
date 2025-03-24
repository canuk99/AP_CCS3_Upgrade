#!/usr/bin/env python3
#check_for_filess_ccs3.py
#This script checks if a list of files exist on a list of hosts.
#The hosts are read from a CSV file and the files are passed as arguments.
#The script uses the pexpect library to SSH into the hosts and check for the files.
#The script uses the ThreadPoolExecutor to process multiple hosts concurrently.
#The script also uses the subprocess library to ping the hosts before checking for the files.
#The script prints the list of good and bad hosts at the end.
    
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
        #print(f"Pinging host: {host}")
        subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        print(f"Host {host} is not reachable.")
        return False

def check_files_exist(host, files):
    """Check if multiple files exist on the host using SSH."""
    try:
        #print(f"Connecting to host: {host} via SSH")
        client = pxssh.pxssh()
        username = 'root'
        password = os.getenv('SSHPASS')
        if not password:
            raise ValueError("No SSH password found. Please set the SSHPASS environment variable.")

        if not client.login(host, username, password):
            print(f"SSH login failed for {host}")
            return False

        all_files_exist = True
        for file_path in files:
            command = f"test -f /tmp/{file_path} && echo 'File exists' || echo 'File does not exist'"
            #print(f"Executing command on {host}: {command}")
            client.sendline(command)
            time.sleep(3)  # Add a delay of 3 seconds
            client.prompt()
            output = client.before.decode('utf-8').splitlines()
            output = [line.strip() for line in output if line.strip()]
            #print(f"Raw output: {output}")
            if 'File does not exist' in output:
                #print(f"File /tmp/{file_path} does not exist on {host}.")
                all_files_exist = False
            elif 'File exists' in output:
                print(f"File {file_path} exists on {host}.")
            else:
                #print(f"Unexpected output for {file_path} on {host}: {output}")
                all_files_exist = False
            #print(f"Decision for {file_path} on {host}: {'exists' if all_files_exist else 'does not exist'}")
        
        client.logout()
        return all_files_exist
    except Exception as e:
        print(f"Failed to SSH into {host}: {e}")
        return False

def process_host(host, files):
    """Process a single host: ping and check files."""
    #print(f"Processing host: {host}")
    if ping_host(host):
        if check_files_exist(host, files):
            #print(f"Host {host} is good.")
            return (host, 'good')
        else:
            #print(f"Host {host} is bad.")
            return (host, 'bad')
    else:
        #print(f"Host {host} is bad.")
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

def process_hosts(hosts, files):
    """Process all hosts concurrently."""
    print("Processing all hosts concurrently.")
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
    """Print the lists of good and bad hosts."""
    print("Good Hosts:")
    for host in good_hosts:
        print(host)
    print("\nBad Hosts:")
    for host in bad_hosts:
        print(host)

def main(csv_file, files):
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
        future_to_host = {executor.submit(process_host, host, files): host for host in hosts}
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
    parser = argparse.ArgumentParser(description='Check if files exist on hosts listed in a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    parser.add_argument('files', nargs='+', help='Path(s) to the file(s) to be checked.')

    args = parser.parse_args()
    main(args.csv_file, args.files)