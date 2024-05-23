"""A profile with three nodes. (Client - Server ).

Instructions:
Not much for now.
"""
# Import the Portal object.
import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.emulab as emulab

# Create a Request object to start building the RSpec.
request = portal.context.makeRequestRSpec()

def setup_client_server_specs():
    server = request.RawPC("server")
    client = request.RawPC("client")

    link_router_client_1 = request.Link(members = [server, client])
    link_router_client_1.link_multiplexing = False
    link_router_client_1.best_effort = True

    link_router_client_2 = request.Link(members = [server, client])
    link_router_client_2.link_multiplexing = False
    link_router_client_2.best_effort = True

    for node in [client, server]:
        node.hardware_type = "d6515"
    return (client, server)

client, server = setup_client_server_specs()
portal.context.printRequestRSpec()