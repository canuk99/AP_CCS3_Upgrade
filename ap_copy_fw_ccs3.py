#!/usr/bin/env python3

import csv
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        output = subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

# def scp_file(host, file_path, destination):
#     """SCP the file to the destination on the host without host key validation."""
#     try:
#         subprocess.check_output([
#             'sshpass', '-e', 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
#             file_path, f'{host}:{destination}'
#         ], stderr=subprocess.STDOUT)
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"Error copying file to {host}: {e.output.decode()}")
#         return False
    
def scp_files(host, file_path1, file_path2, destination):
    """SCP two files to the destination on the host without host key validation."""
    try:
        subprocess.check_output([
            'sshpass', '-e', 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            file_path1, f'{host}:{destination}'
        ], stderr=subprocess.STDOUT)
        subprocess.check_output([
            'sshpass', '-e', 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            file_path2, f'{host}:{destination}'
        ], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error copying files to {host}: {e.output.decode()}")
        return False    

def process_host(host, file_path1,file_path2):
    """Process a single host: ping and SCP file."""
    if ping_host(host):
        if scp_files(host, file_path1, file_path2, '/tmp'):
            return (host, 'good')
        else:
            return (host, 'bad')
    else:
        return (host, 'bad')

def read_hosts_from_csv(csv_file):
    """Read hosts from the CSV file."""
    try:
        with open(csv_file, mode='r') as file:
            csv_reader = csv.DictReader(file, delimiter=',')
            return [row['SNMP_Host'] for row in csv_reader]
    except FileNotFoundError:
        print(f"Error: The file {csv_file} was not found.")
        exit(1)
    except Exception as e:
        print(f"Error reading CSV file {csv_file}: {e}")
        exit(1)

def main(csv_file, file_path1, file_path2):
    good_hosts = []
    bad_hosts = []

    hosts = read_hosts_from_csv(csv_file)

    with ThreadPoolExecutor(max_workers=40) as executor:
        future_to_host = {executor.submit(process_host, host, file_path1, file_path2): host for host in hosts}
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
    import argparse

    parser = argparse.ArgumentParser(description='SCP files to hosts listed in a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    parser.add_argument('file_path1', help='Path to the file to be copied.')
    parser.add_argument('file_path2', help='Path to the file to be copied.')

    args = parser.parse_args()
    main(args.csv_file, args.file_path1, args.file_path2)

