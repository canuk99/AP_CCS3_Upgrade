#!/usr/bin/env python3
#
# This tests to see if the files are there.
import csv
import subprocess
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pexpect import pxssh
import os
import re
import platform

def ping_host(host):
    """Ping the host to check if it is reachable."""
    try:
        ping_flag = '-n' if platform.system().lower() == 'windows' else '-c'
        subprocess.check_output(['ping', ping_flag, '1', host], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False
    
def ssh_and_run_commands(host):
    """SSH into the host, run the specified command, and report the NTP server information."""
    try:
        client = pxssh.pxssh()
        username = 'root'
        password = os.getenv('SSH_PASSWORD')
        if not password:
            raise ValueError("No SSH password found. Please set the SSH_PASSWORD environment variable (e.g., export SSH_PASSWORD=your_password).")
        if not client.login(host, username, password):
            logging.error(f"SSH login failed for {host}")
            return

        # Run the command "web_ctrl request_nu_config"
        client.sendline('web_ctrl request_nu_config')
        client.prompt()
        output = client.before.decode('utf-8')
        #print(output)

        # Extract the content of the <ntpServers> line
        ntp_line = None
        for line in output.splitlines():
            if '<ntpServers>' in line:
                ntp_line = line.strip()
                break

        # Print the IP and the extracted NTP server content
        if ntp_line:
            # Extract only the content inside <ntpServers>...</ntpServers>
            ntp_content = ntp_line.replace('<ntpServers>', '').replace('</ntpServers>', '').strip()

            # Split the content by commas to handle multiple IPs
            ntp_servers = ntp_content.split(',')
            #print(ntp_content.split(','))

            # Validate each IP address
            valid_ips = []
            invalid_ips = []
            for ntp_server in ntp_servers:
                ntp_server = ntp_server.strip()
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ntp_server):
                    valid_ips.append(ntp_server)
                    #print(ntp_server)  # Print each valid IP as it is identified
                else:
                    invalid_ips.append(ntp_server)

            # Print the host and the list of valid IPs before the conditional block
            print(f"{host}, {', '.join(valid_ips)}")

            # Print valid and invalid IPs
            if valid_ips:
                logging.info(f"{host}, Valid NTP server IP(s): {', '.join(valid_ips)}")
            if invalid_ips:
                logging.warning(f"{host}, Invalid NTP server IP(s): {', '.join(invalid_ips)}")
        else:
            logging.warning(f"{host}, <ntpServers> not found")

        client.logout()
    except pxssh.ExceptionPxssh as e:
        logging.error(f"Failed to SSH into {host}: {e}")
    except ValueError as e:
        print(f"Value error for {host}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for {host}: {e}")

def process_host(host):
    """Process a single host: ping and run the command."""
    if ping_host(host):
        ssh_and_run_commands(host)
        return (host, 'good')
    else:
        return (host, 'bad')

def read_hosts_from_csv(csv_file):
    """Read hosts from the CSV file."""
    try:
        with open(csv_file, mode='r') as file:
            csv_reader = csv.DictReader(file, delimiter=',')
            for row in csv_reader:
                if 'SNMP_Host' not in row:
                    raise ValueError(f"The CSV file {csv_file} does not contain the required 'SNMP_Host' column.")
                return [row['SNMP_Host'] for row in csv_reader]
    except FileNotFoundError:
            logging.error(f"Error: The file {csv_file} was not found.")
            print(f"Error: The file {csv_file} was not found.")
            exit(1)
    except Exception as e:
            logging.error(f"Error reading CSV file {csv_file}: {e}")
            print(f"Error reading CSV file {csv_file}: {e}")
            exit(1)
    except Exception as e:
        print(f"Error reading CSV file {csv_file}: {e}")
        exit(1)

def process_hosts(hosts):
    """Process all hosts concurrently."""
    good_hosts = []
    bad_hosts = []
    with ThreadPoolExecutor(max_workers=40) as executor:
        future_to_host = {executor.submit(process_host, host): host for host in hosts}
        for future in as_completed(future_to_host):
            host, status = future.result()
            if status == 'good':
                good_hosts.append(host)
            else:
                bad_hosts.append(host)
    return good_hosts, bad_hosts

def print_hosts(good_hosts, bad_hosts):
    """Print the good and bad hosts."""
    logging.info("Good Hosts:")
    print("Good Hosts:")
    
    for host in good_hosts:
        logging.info(host)
        print(host)  # Only one print statement
    logging.info("\nBad Hosts:")
    
    print("\nBad Hosts:")
    for host in bad_hosts:
        logging.info(host)
        print(host)  # Only one print statement

def main(csv_file):
    """Main function to process the hosts."""
    # Disable logging by setting the level to CRITICAL
    logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s')
    
    password = os.getenv('SSH_PASSWORD')
    if not password:
        raise ValueError("No SSH password found. Please set the SSH_PASSWORD environment variable.")
    hosts = read_hosts_from_csv(csv_file)
    good_hosts, bad_hosts = process_hosts(hosts)
    print_hosts(good_hosts, bad_hosts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ping hosts and extract NTP server information via SSH.')
    parser.add_argument('csv_file', help='Path to the CSV file containing host information.')
    args = parser.parse_args()
    main(args.csv_file)
