import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from scapy.all import sniff
from scapy.layers.inet import IP, UDP
from typing import List, Set, Tuple, Dict

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
    timestamp: float
    payload_len: int


@dataclass
class ConnectionData(TransportConnection):
    addresses:      Tuple[str, str]
    timestamps:     List[int]
    payload_len:    List[int]

ConnectionDataDict = lambda: defaultdict(ConnectionData)

def process_pcap(file_name: str, endpoints_to_filter: Set[str]) -> List[ProcessingPacket]:
    packets = []
    for packet in sniff(offline=file_name, filter="ip", store=False):
        if not packet.haslayer(UDP):
            continue
        ip_pkt = packet[IP]
        udp_pkt = packet[UDP]
        connection = TransportConnection(ip_pkt.src, ip_pkt.dst, udp_pkt.sport, udp_pkt.dport)
        if not endpoints_to_filter or connection in endpoints_to_filter:
            packets.append(ProcessingPacket(ip_pkt.src, ip_pkt.dst, udp_pkt.sport, udp_pkt.dport, packet.time * 1e6, ip_pkt.len * 8))
    packets.sort(key=lambda x: x.timestamp)
    return packets

def per_connection_data(filename: str, endpoints_to_filter: Set[str]) -> List[ConnectionData]:
    packets = process_pcap(filename, endpoints_to_filter)
    connections = defaultdict(ConnectionData)
    for packet in packets:
        addresses = tuple(sorted((packet.src_addr, packet.dest_addr)))
        connections[addresses].addresses = addresses
        connections[addresses].timestamps.append(packet.timestamp)
        connections[addresses].payload_len.append(packet.payload_len)
    return list(connections.values())

def resample_data_by_interval(timestamps, payload_lens, interval=1000000):
    new_timestamps, new_payload_lens = [], []
    start_timestamp = timestamps[0]
    for i in range(0, len(timestamps), interval):
        new_timestamps.append((timestamps[i] - start_timestamp) / interval)
        new_payload_lens.append(sum(payload_lens[i:i+interval]))
    return new_timestamps, new_payload_lens

def calculate_the_plot(pcap_file: str, endpoints_to_filter: Set[str]):
    per_subflow = defaultdict(lambda: {"timestamps": [], "payloads_len": []})
    data = per_connection_data(pcap_file, endpoints_to_filter)
    for dataset in data:
        new_timestamps, new_data = resample_data_by_interval(dataset.timestamps, dataset.payload_len)
        per_subflow[dataset.addresses]["payloads_len"].append(new_data)
        per_subflow[dataset.addresses]["timestamps"] = new_timestamps
    return per_subflow

def handle_subplot(ax: plt.Axes, pcap_file: str, endpoints_to_filter: Set[str]):
    data = calculate_the_plot(pcap_file, endpoints_to_filter)
    sum_data = 0
    max_data = 0
    for data_key, data_value in data.items():
        for calculation in ["median"]:
            subflow_label = "<->".join(data_key)
            sum_data += sum(np.concatenate(data_value["payloads_len"]))
            max_data = max(max_data, np.max(data_value[calculation]))
            latest, = ax.plot(
                data_value["timestamps"], np.median(data_value["payloads_len"], axis=0), 
                label=f"{calculation[0].upper()}{calculation[1:]} {subflow_label}", 
                marker="*", markersize=5, linewidth=1, linestyle="--"
            )
    print(f"Total sum: {sum_data/1e9} Gbits")
    ax.legend(
        loc='upper center', 
        bbox_to_anchor=(0.5, 1.35),
        ncol=3, 
    )
    ax.set(xlabel="Time [s]", ylabel="UDP Traffic [bits/sec]", title="PCAP UDP packet bandwidth usage per path")
    ax.set_ylim(bottom=1, top=max_data * 1.5)
    ax.grid(which='major', color='#CCCCCC', linewidth=1)
    ax.grid(which='minor', color='#DDDDDD', linestyle=':', linewidth=0.8)
    ax.minorticks_on()
    return ax.get_legend_handles_labels()

def main(pcap_file: str, directory: str, endpoints: List[str] = []):
    fig, ax = plt.subplots(1, 1, sharex=True, sharey=True, figsize=(18, 6), dpi=80)
    fig.patch.set_facecolor('white')
    handle_subplot(ax, pcap_file, set(endpoints))
    plt.tight_layout()
    plt.yscale("log")
    plt.savefig(f"{directory}/pcap_path_distribution.png")
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", help="The directory to save the plot.", required=True)
    parser.add_argument("-p", "--pcap_file", help="The pcap file to analyse.", required=True)
    parser.add_argument("-e", "--endpoints", nargs='+', help="An array of endpoints to only consider. ex: 127.0.0.1:7493 127.0.0.1:8888", required=False, default=[])
    args = parser.parse_args()
    main(args.pcap_file, args.directory, args.endpoints)
