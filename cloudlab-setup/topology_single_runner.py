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

node = setup_specs()
portal.context.printRequestRSpec()