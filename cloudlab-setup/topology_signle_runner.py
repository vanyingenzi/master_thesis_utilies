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

def setup_specs():
    server = request.RawPC("runner")
    server.hardware_type = "c6525-25g"
    return server


def specify_os_setup_scripts(nodes):
    for node in nodes:
        # Defalt OS is ubuntu 20.64 node.disk_image = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU20-64-STD"
        node.addService(pg.Install(url="https://raw.githubusercontent.com/vanyingenzi/master_thesis_utilities/main/cloudlab-setup/install_scripts/setup.sh", path="/local"))
        node.addService(pg.Execute(shell="bash", command="/local/setup.sh"))

node = setup_specs()
specify_os_setup_scripts([node])
portal.context.printRequestRSpec()