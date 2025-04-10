import grpc
import raft_pb2
import raft_pb2_grpc
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RaftClient:
    def __init__(self, server_addresses):
        self.server_addresses = server_addresses
        self.stubs = {}
        self.leader_address = None
        
        # Create stubs for all servers
        for address in server_addresses:
            channel = grpc.insecure_channel(address)
            stub = raft_pb2_grpc.RaftServiceStub(channel)
            self.stubs[address] = stub

    def get_node_id_from_address(self, address):
        """Extract node ID from address (e.g., 'localhost:50051' -> 1)"""
        port = int(address.split(':')[1])
        return port - 50050  # Convert port to node ID (e.g., 50051 -> 1)

    def add_numbers(self, num1: int, num2: int):
        # Try each server until we find the leader or exhaust all options
        for address, stub in self.stubs.items():
            try:
                node_id = self.get_node_id_from_address(address)
                logger.info(f"Trying to send addition request to Node {node_id} ({address})")
                request = raft_pb2.AddRequest(num1=num1, num2=num2)
                response = stub.Add(request)
                
                if response.success:
                    self.leader_address = address
                    leader_id = self.get_node_id_from_address(address)
                    logger.info(f"Addition successful on Node {node_id}!")
                    logger.info(f"Current leader is Node {leader_id}")
                    logger.info(f"Result: {response.sum}")
                    return {
                        'result': response.sum,
                        'leader_id': leader_id,
                        'operation_node_id': node_id
                    }
                else:
                    if hasattr(response, 'leader_hint') and response.leader_hint:
                        leader_address = f'localhost:{50050 + response.leader_hint}'
                        logger.warning(f"Request failed: Not the leader. Leader is Node {response.leader_hint}")
                        # Try the leader directly if we haven't already
                        if leader_address in self.stubs and leader_address != address:
                            try:
                                logger.info(f"Retrying with leader Node {response.leader_hint}")
                                request = raft_pb2.AddRequest(num1=num1, num2=num2)
                                response = self.stubs[leader_address].Add(request)
                                if response.success:
                                    self.leader_address = leader_address
                                    logger.info(f"Addition successful on leader Node {response.leader_hint}!")
                                    logger.info(f"Result: {response.sum}")
                                    return {
                                        'result': response.sum,
                                        'leader_id': response.leader_hint,
                                        'operation_node_id': response.leader_hint
                                    }
                            except grpc.RpcError as e:
                                logger.error(f"Failed to connect to leader Node {response.leader_hint}: {str(e)}")
                    else:
                        logger.warning(f"Request failed: {response.error}")
            except grpc.RpcError as e:
                logger.error(f"Failed to connect to Node {node_id}: {str(e)}")
                continue
        
        raise Exception("Failed to perform addition: no available servers or all attempts failed")

def main():
    if len(sys.argv) != 3:
        print("Usage: python client.py <num1> <num2>")
        sys.exit(1)

    try:
        num1 = int(sys.argv[1])
        num2 = int(sys.argv[2])
    except ValueError:
        print("Error: Please provide valid integer numbers")
        sys.exit(1)

    # List of server addresses (you can modify these based on your cluster setup)
    server_addresses = [
        'localhost:50051',
        'localhost:50052',
        'localhost:50053',
        'localhost:50054',
        'localhost:50055'
    ]

    client = RaftClient(server_addresses)
    
    try:
        result = client.add_numbers(num1, num2)
        print(f"\nOperation Summary:")
        print(f"Leader: Node {result['leader_id']}")
        print(f"Operation performed on: Node {result['operation_node_id']}")
        print(f"Result: {num1} + {num2} = {result['result']}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 