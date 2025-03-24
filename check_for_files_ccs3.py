import csv
import paramiko
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        subprocess.check_output(['ping', '-c', '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def check_remote_files(hostname, username, password, files):
    """Check if the specified files exist on the remote server."""
    try:
        # Set up the SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, username=username, password=password)

        # Open SFTP session
        sftp = client.open_sftp()

        # Check the files
        results = []
        for file in files:
            try:
                sftp.stat(file)
                results.append(f"File '{file}' exists on {hostname}.")
            except FileNotFoundError:
                results.append(f"File '{file}' does not exist on {hostname}.")

        # Close the SFTP session and SSH client
        sftp.close()
        client.close()
        return hostname, 'good' if all("exists" in result for result in results) else 'bad'
    except Exception as e:
        return hostname, f"An error occurred: {e}"

def read_hosts_from_csv(csv_file):
    """Read hosts from the CSV file."""
    with open(csv_file, mode='r') as file:
        csv_reader = csv.DictReader(file, delimiter=',')
        if 'SNMP_Host' not in csv_reader.fieldnames:
            raise ValueError("CSV file is missing 'SNMP_Host' header.")
        return [row['SNMP_Host'] for row in csv_reader]

def process_host(host, username, password, files):
    """Process each host: ping and check files."""
    if ping_host(host):
        return check_remote_files(host, username, password, files)
    else:
        return host, 'bad'

def process_hosts(hosts, username, password, files):
    """Process all hosts concurrently."""
    good_hosts = []
    bad_hosts = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_host = {executor.submit(process_host, host, username, password, files): host for host in hosts}
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

def main(csv_file, file_path1, file_path2):
    
    # Specify the remote server details
    username = 'your_username'
    password = os.getenv('SSH_PASSWORD')  # Ensure SSH_PASSWORD is set in your environment

    # Specify the file paths on the remote server
    files = ['/path/to/your/first/file.txt', '/path/to/your/second/file.txt']

    # Read hosts from CSV file
    hosts = read_hosts_from_csv(csv_file)

    # Process hosts and get lists of good and bad hosts
    good_hosts, bad_hosts = process_hosts(hosts, username, password, files)

    # Print the results
    print_hosts(good_hosts, bad_hosts)

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description='Ping hosts and check for specific files via SSH.')
    # parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    # parsed_args = parser.parse_args()
    # main(parsed_args.csv_file)
    import argparse

    parser = argparse.ArgumentParser(description='test to confirm the files exist.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    parser.add_argument('file_path1', help='Path to the file to be copied.')
    parser.add_argument('file_path2', help='Path to the file to be copied.')

    args = parser.parse_args()
    main(args.csv_file)