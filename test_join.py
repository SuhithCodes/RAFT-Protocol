import asyncio
import grpc
import logging
import os
import time
from typing import List
import raft_pb2
import raft_pb2_grpc
from node import RaftNode, serve

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def join_cluster(node_id: int, known_node_address: str) -> bool:
    """Attempt to join a cluster through a known node"""
    try:
        channel = grpc.aio.insecure_channel(known_node_address)
        stub = raft_pb2_grpc.RaftServiceStub(channel)
        
        request = raft_pb2.JoinRequest(
            node_id=node_id,
            address=f'node{node_id}:50051'
        )
        
        logger.info(f"Node {node_id} sending join request to {known_node_address}")
        response = await stub.JoinCluster(request)
        
        if response.success:
            logger.info(f"Node {node_id} successfully joined cluster")
            logger.info(f"Cluster config: {response.cluster_config}")
            return True, response.cluster_config
        elif response.current_leader is not None:
            # Retry with correct leader
            leader_address = f'node{response.current_leader}:50051'
            logger.info(f"Redirecting to leader at {leader_address}")
            return await join_cluster(node_id, leader_address)
        else:
            logger.error(f"Failed to join cluster: {response.error}")
            return False, None
            
    except Exception as e:
        logger.error(f"Error joining cluster: {e}")
        return False, None

async def run_node():
    """Join cluster and then run the node"""
    # Wait for initial cluster to stabilize
    await asyncio.sleep(10)
    
    # Try joining through each existing node until successful
    new_node_id = 6  # Assuming initial cluster is nodes 1-5
    existing_nodes = [1, 2, 3, 4, 5]
    
    for node_id in existing_nodes:
        known_address = f'node{node_id}:50051'
        logger.info(f"Attempting to join through node {node_id}")
        
        success, cluster_config = await join_cluster(new_node_id, known_address)
        if success:
            logger.info("Successfully joined cluster, starting node server...")
            # Get peer IDs from cluster config
            peer_ids = [n for n in cluster_config.nodes if n != new_node_id]
            # Set environment variables for node
            os.environ['NODE_ID'] = str(new_node_id)
            os.environ['PEER_IDS'] = ','.join(map(str, peer_ids))
            # Start the node server
            await serve()
            return
        
        # Wait before trying next node
        await asyncio.sleep(2)
    
    logger.error("Failed to join cluster through any existing node")

if __name__ == "__main__":
    asyncio.run(run_node()) 