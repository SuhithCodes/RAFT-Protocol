import asyncio
from raft_node import RaftNode

async def main():
    # Create a cluster of 3 nodes
    nodes = []
    node_ids = [1, 2, 3]
    
    # Create nodes
    for node_id in node_ids:
        peer_ids = [id for id in node_ids if id != node_id]
        node = RaftNode(node_id, peer_ids)
        nodes.append(node)
    
    # Run for some time to observe leader election and log replication
    print("Starting RAFT cluster...")
    print("Nodes will elect a leader and start replicating logs")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            await asyncio.sleep(1)
            
            # Find the leader and submit a command
            for node in nodes:
                if node.state.name == "LEADER":
                    success = node.submit_command(f"Command from node {node.node_id}")
                    if success:
                        print(f"Leader {node.node_id} submitted a command")
                    break
    except KeyboardInterrupt:
        print("\nStopping cluster...")

if __name__ == "__main__":
    asyncio.run(main()) 