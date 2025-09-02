from enum import Enum
import asyncio
import grpc
import json
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.message_factory import GetMessages
from google.protobuf.json_format import ParseDict, MessageToDict
from google.protobuf import any_pb2
import toml
import os
from fnmatch import fnmatch
import aiorwlock
# Utility import
from util.log import get_logger
from util.config import query_config
from util.rpc import reflective_grpc_call, generate_response, generate_request

logger = get_logger('core/laws/authority')

# Failsafe classifications
class Failsafe(Enum):
    DC_SERVER = 0
    DC_DRIVER = 1
    DC_MISSION = 2
    DC_REMOTE_COMPUTE = 3
    DC_LOCAL_COMPUTE = 4
    CORE_ERROR = 5

class LawAuthority:
    '''
    Maintains a unified state of the current control law. Other entities
    can query to get the up-to-date law, or request a change. The
    remote control handler derives from this class and thus manages
    the law for all entities.
    '''
    def __init__(self):
        # Load in laws from the provided path
        path = os.getenv('LAWPATH')
        if not path:
            path = '.laws.toml'
        with open(path, 'r') as laws:
            self._spec = toml.load(laws)
            self._base = self._spec['__BASE__']
        self._state = None
        self._law = None
        self._lock = aiorwlock.RWLock()
        # Open a channel to connect to core services 
        self._channel = grpc.aio.insecure_channel(query_config('internal.services.core'))
        # Create a descriptor pool which can look up services by name from
        # generated .desc file
        self._desc_pool = DescriptorPool()
        self._name_table = {}
        root = os.getenv('ROOTPATH')
        if not root:
            root = '../'
        with open(f"{root}protocol/protocol.desc", 'rb') as f:
            data = f.read()
            descriptor_set = FileDescriptorSet.FromString(data)
            for file_descriptor_proto in descriptor_set.file:
                self._desc_pool.Add(file_descriptor_proto)
                fname = file_descriptor_proto.name.split('.')[0].replace('/', '.')
                for service in file_descriptor_proto.service:
                    self._name_table[service.name] = f'protocol.{fname}.{service.name}'
            # Message class holder to support dynamic instantiation of messages
            self._message_classes = GetMessages(descriptor_set.file)

    async def start(self, retries=3):
        '''
        Call the start calls for the law scheme. Must be called before any 
        other function!
        '''
        logger.info('Sending startup commands...')
        completed = False
        while not completed and retries:
            completed = await self.set_law('__BASE__')
            if not completed:
                logger.warning('Startup failed, retrying...')
                retries -= 1
                await asyncio.sleep(0.5)

    def check_equal(self, command, request, matcher):
        '''
        Checks whether a command matches a command matcher.
        '''
        root = None
        payload = None
        splits = matcher.split('|')
        if len(splits) < 2: # No payload match
            root = splits[0]
            if fnmatch(command, root):
                return True
            else:
                return False
        else: # Payload match
            try:
                root, payload = splits
                payload = json.loads(payload)
                if fnmatch(command, root):
                    obj = MessageToDict(
                            request,
                            preserving_proto_field_name=True
                            )
                    return all(k in obj and obj[k] == v for k, v in payload.items())
                else:
                    return False
            except Exception as e:
                logger.error(f'Encountered error {e} while matching, ignoring...')
                return False
    
    async def allows(self, command, request):
        '''
        Perform name matching against law to see if command is
        authorized for the service.
        '''
        async with self._lock.reader_lock:
            for expr in (self._law['rules']['allowed'] + self._base['rules']['allowed']):
                if self.check_equal(command, request, expr):
                    return True
            return False

    async def match(self, command, request):
        '''
        Switch to the next control state if a name match is found.
        '''
        next_state = None
        async with self._lock.reader_lock:
            # Always consider user conditions first, then apply base cases
            user_matches = []
            matches = self._base['rules']['match']
            if 'match' in self._law['rules']:
                user_matches = self._law['rules']['match']
            for expr in user_matches: # User specified
                if self.check_equal(command, request, expr[0]):
                    next_state = expr[1]
                    break
            for expr in matches: # Base cases
                if self.check_equal(command, request, expr[0]):
                    next_state = expr[1]
                    break
        if next_state and next_state != self._state:
            logger.info(
                    f'{command} matches match expression {expr}; switching law to {next_state}!'
                    )
            await self.set_law(next_state)

    async def failsafe(self, failsafe):
        '''
        Performs failsafe actions when key services are disconnected.
        '''
        async with self._lock.writer_lock:
            name = failsafe.name.lower()
            commands = []
            if 'failsafes' in self._law and name in self._law['failsafes']:
                commands = self._law['failsafes'][name]
            commands += self._base['failsafes'][name]

            # Retry sending until commands are fully finished
            results = await self._send_commands(commands)
            return all(result.response.status == 2 for result in results)

    async def set_law(self, state):
        '''
        Sets a new law and sends on enter commands.
        '''
        if state == self._state:
            return True
        async with self._lock.writer_lock:
            if state not in self._spec:
                logger.error(f'State {state} is not in the law specification!')
                state = 'REMOTE' # Go into remote mode
            if self._spec[state]['enter']:
                results = await self._send_commands(self._spec[state]['enter'])
                if not all(result.response.status == 2 for result in results):
                    return False
            try:
                self._state = state
                self._law = self._spec[state]
                logger.info(f'Transitioned to law: {state}')
                return True
            except:
                return False

    async def get_law(self):
        '''
        Gets the current law.
        '''
        async with self._lock.reader_lock:
            return self._state, self._law 

    async def _send_commands(self, command_list, identity='authority'):
        '''
        Sends a list of commands, either JSON or a Protobuf, to the correct service
        in core and returns the results.
        '''
        results = []
        for command in command_list:
            try:
                # Check if we are calling a JSON command or a proto object
                # command from a remote controller
                is_json_command = True if type(command) == str else False
                if is_json_command:
                    splits = command.split('|')
                    if len(splits) > 1:
                        full_name, payload = splits
                    else:
                        full_name = splits[0]
                        payload = '{}'
                    service, method = full_name.rsplit('.', 1)
                else:
                    full_name = command.method_name
                    service, method = full_name.rsplit('.', 1)
                # Fully qualify the name
                service = self._name_table[service]
                service_desc = self._desc_pool.FindServiceByName(service)
                method_desc = service_desc.FindMethodByName(method)
                # Build the request
                request = self._message_classes[method_desc.input_type.full_name]()
                request.request.ParseFromString(generate_request().SerializeToString())
                if is_json_command:
                    ParseDict(json.loads(payload), request, ignore_unknown_fields=True)
                else:
                    command.control_request.Unpack(request)
                logger.proto(request)
            except KeyError:
                logger.error(f'Command {method} ignored due to failed descriptor lookup!')
                response = self._message_classes[method_desc.output_type.full_name]()
                response.response.ParseFromString(
                        generate_response(5).SerializeToString() # Invalid argument
                        )
                results.append(response)
                continue
            metadata = [('identity', identity)]
            # Send in the correct classes to unmarshall from the channel
            classes = (
                    self._message_classes[method_desc.input_type.full_name],
                    self._message_classes[method_desc.output_type.full_name]
                    )
            try:
                response = await reflective_grpc_call(
                            metadata,
                            f'/{service}/{method}',
                            method_desc,
                            request,
                            classes,
                            self._channel
                            )
                results.append(response)
                logger.proto(response)
            except grpc.aio.AioRpcError as e:
                logger.error(f'Encountered RPC error, {e.code()}: {e.details()}')
                response = self._message_classes[method_desc.output_type.full_name]()
                response.response.ParseFromString(
                        generate_response(e.code().value[0] + 2, resp_string=e.details()).SerializeToString()
                        )
                results.append(response)
                logger.proto(response)
        return results
