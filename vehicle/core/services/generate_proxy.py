import sys
from google.protobuf import descriptor_pb2
import os
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RPCMethod:
    name: str
    streaming: bool

def generate_proxy(service_name, service_filename, channel_addr):
    '''
    Builds a proxy file given a service name, and writes it to the
    given output path.
    '''
    # Jinja context variables
    context = {
        'methods': [],
        'service_name': service_name,
        'service_filename': service_filename,
        'channel': channel_addr
    }
    # Populat methods from descriptor file
    fds = descriptor_pb2.FileDescriptorSet()
    with open(os.getenv('DESCPATH'), "rb") as f:
        fds.MergeFromString(f.read())
        for file in fds.file:
            if file.name != f'services/{service_filename}.proto':
                continue
            for service in file.service:
                if service.name != service_name:
                    continue
                # Generate proxy methods for each of the methods in the service
                for method in service.method:
                    rpc_name = method.name
                    if method.client_streaming and method.server_streaming:
                        raise NotImplemented("No proxy generation method for method type: bidirectional stream!")
                    elif method.client_streaming:
                        raise NotImplemented("No proxy generation method for method type: client stream!")
                    rpc = RPCMethod(method.name, method.server_streaming)
                    context['methods'].append(rpc)
    
    # Get the Jinja template
    template_path = Path(__file__).parent / 'templates/'
    environment = Environment(loader=FileSystemLoader(str(template_path)))
    template = environment.get_template('proxy_service.py')
    output_path = Path(__file__).parent / f'_gen_{service_filename}_proxy.py'
    with open(str(output_path), 'w') as f:
        f.write(template.render(context))
