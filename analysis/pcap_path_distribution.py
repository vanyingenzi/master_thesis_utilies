import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from scapy.all import sniff
from scapy.layers.inet import IP, UDP
from typing import List, Set, Tuple, Dict
from pprint import pprint


@dataclass
class TransportConnection:
    src_addr:       str
    dest_addr:      str
    src_port:       int
    dest_port:      int

    def __hash__(self) -> int:
        list_arg = [self.src_addr, self.src_port, self.dest_addr, self.dest_port]
        list_arg.sort()
        return hash(tuple(list_arg))
    
    def __eq__(self, __value: object) -> bool:
        if type(__value) is not TransportConnection:
            return False 
        return self.__hash__() == __value.__hash__()

    def get_addresses(self) -> Tuple[str, str]:
        list_arg = [self.src_addr, self.dest_addr]
        list_arg.sort()
        return tuple(list_arg)
    
    def get_endpoints(self) -> Tuple[str, str]:
        list_arg = [f"{self.src_addr}:{self.src_port}", f"{self.dest_addr}:{self.dest_port}"]
        list_arg.sort()
        return tuple(list_arg)

@dataclass
class ProcessingPacket(TransportConnection):
    timestamp:      float
    payload_len:    int

@dataclass
class ConnectionData(TransportConnection):
    addresses:      Tuple[str, str]
    timestamps:     List[int]
    payload_len:    List[int]

ConnectionDataDict = lambda: defaultdict(ConnectionData)

def process_pcap(file_name: str, endpoints_to_filter: List[str]) -> List[ProcessingPacket]:
    packets: List[ProcessingPacket] = []       
    def per_packet_process(packet):
        ip_pkt  = packet[IP]
        udp_pkt = ip_pkt[UDP]
        process_packet      = ProcessingPacket(     
                                                ip_pkt.src, ip_pkt.dst, 
                                                udp_pkt.sport, udp_pkt.dport, 
                                                packet.time * 1e6, ip_pkt.len * 8 # To convert to bits
                                            )
        packets.append(process_packet)

    def per_packet_process_with_filter(packet):
        ip_pkt  = packet[IP]
        udp_pkt = ip_pkt[UDP]
        # TODO Better comparison of IP address 
        if not (f"{ip_pkt.src}:{udp_pkt.sport}" in endpoints_to_filter or f"{ip_pkt.dst}:{udp_pkt.dport}" in endpoints_to_filter):
            return
        process_packet      = ProcessingPacket(     
                                                ip_pkt.src, ip_pkt.dst, 
                                                udp_pkt.sport, udp_pkt.dport, 
                                                packet.time * 1e6, ip_pkt.len * 8 # To convert to bits
                                            )
        packets.append(process_packet)

    sniff(offline=file_name, prn=per_packet_process if len(endpoints_to_filter) == 0 else per_packet_process_with_filter, filter="ip")
    packets.sort(key=lambda x: x.timestamp)
    return packets

def per_connection_data(filename: str, endpoints_to_filter) -> Set[ConnectionData]:
    packets     = process_pcap(filename, endpoints_to_filter)
    connections : Dict[Tuple[str, str], ConnectionData] = defaultdict()
    for packet in packets:
        addresses = packet.get_endpoints()
        if addresses not in connections:
            connections[addresses] = ConnectionData( packet.src_addr, packet.dest_addr, packet.src_port, packet.dest_port, addresses, [], [])
        connections[addresses].timestamps.append(packet.timestamp)
        connections[addresses].payload_len.append(packet.payload_len)
    return connections.values()

def resample_data_by_interval(timestamps, payload_lens, interval=1000000):
    new_timestamps, new_payload_lens = [], []
    curr_index      = 0
    sum_before      = sum(payload_lens) 
    start_timestamp = timestamps[0]
    while (curr_index < len(timestamps)):
        timestamp   = timestamps[curr_index]
        next_index  = curr_index
        data        = 0
        while (next_index < len(timestamps) and timestamps[next_index] <= timestamp + interval):
            data        += payload_lens[next_index]
            next_index  += 1
        new_timestamps.append((timestamps[next_index-1] - start_timestamp)/interval)
        #new_timestamps.append(timestamps[next_index-1]/interval)
        new_payload_lens.append(data)
        curr_index  = next_index
    assert sum(new_payload_lens) == sum_before
    return new_timestamps, new_payload_lens

def calculate_the_plot(pcap_file: str, endpoints_to_filter: List[str]):
    per_subflow : Dict[Tuple[str, str], Dict[str, List]] = defaultdict(lambda: {"timestamps": [], "payloads_len": []})
    data = per_connection_data(pcap_file, endpoints_to_filter)
    for idx, dataset in enumerate(data):
        new_timestamps, new_data = resample_data_by_interval(  dataset.timestamps, dataset.payload_len )
        per_subflow[dataset.addresses]["payloads_len"].append(new_data)
        per_subflow[dataset.addresses]["timestamps"] = new_timestamps
    to_return = {}
    for key, value in per_subflow.items():
        to_return[key] = {
                            "mean": np.average(value["payloads_len"], axis=0), 
                            "median": np.median(value["payloads_len"], axis=0),
                            "timestamps": value["timestamps"]
                        }
    return to_return

def handle_subplot(ax: plt.Axes, pcap_file: str, endpoints_to_filter: List[str]):
    data = calculate_the_plot(pcap_file, endpoints_to_filter)
    sum_data = 0
    max_data = 0
    for data_key, data_value in data.items():
        for calculation in ["median"]:
            subflow_label = "<->".join(data_key)
            sum_data += np.sum(data_value[calculation])
            max_data = max(max_data, np.max(data_value[calculation]) )
            latest, = ax.plot(
                data_value["timestamps"], data_value[calculation], 
                label=f"{calculation[0].upper()}{calculation[1:]} {subflow_label}", 
                marker="*", markersize=5, linewidth=1, linestyle="--"
            )
    print(f"Total sum: {sum_data/1e9} Gbits")
    ax.legend()
    ax.set(xlabel="Time [s]", ylabel="UDP Traffic [bits/sec]", title="PCAP UDP packet bandwidth usage per path")
    #ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: datetime.utcfromtimestamp(x).strftime("%H:%M:%S")))
    ax.set_ylim(bottom=1, top=max_data * 1.5)
    ax.grid(which='major', color='#CCCCCC', linewidth=1) # Show the major grid
    ax.grid(which='minor', color='#DDDDDD', linestyle=':', linewidth=0.8) # Show the minor grid
    ax.minorticks_on() # Make the minor ticks and gridlines show
    return ax.get_legend_handles_labels()


def main(pcap_file: str, directory: str, endpoints: List[str] = []):
    fig, ax = plt.subplots(1, 1, sharex=True, sharey=True, figsize=(18, 6), dpi=80)
    handle_subplot(ax, pcap_file, endpoints)
    plt.tight_layout()
    plt.yscale("log")

    plt.show()

if __name__ == "__main__":
    argparse = argparse.ArgumentParser()
    argparse.add_argument("-d", "--directory", help="The directory to save the plot.", required=True)
    argparse.add_argument("-p", "--pcap_file", help="The pcap file to analyse.", required=True)
    argparse.add_argument("-e", "--endpoints", nargs='+', help="An array of endpoints to only consider. ex: 127.0.0.1:7493 127.0.0.1:8888", required=False, default=[])
    args = argparse.parse_args()
    main(args.pcap_file, args.directory, args.endpoints)