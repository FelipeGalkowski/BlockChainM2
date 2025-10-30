import json
import os
from typing import List, Dict

from block import (
    Block,
    create_block,
    create_block_from_dict,
    create_genesis_block,
    hash_block,
)
from network import broadcast_block, broadcast_transaction


def load_chain(fpath: str) -> List[Block]:
    if os.path.exists(fpath):
        with open(fpath) as f:
            data = json.load(f)
            blockchain: List[Block] = []
            for block_data in data:
                block = create_block_from_dict(block_data)
                blockchain.append(block)
            return blockchain
    return [create_genesis_block()]


def save_chain(fpath: str, chain: List[Block]):
    blockchain_serializable: List[Dict] = []
    for b in chain:
        blockchain_serializable.append(b.as_dict())
    with open(fpath, "w") as f:
        json.dump(blockchain_serializable, f, indent=2)


def valid_chain(chain: List[Dict]) -> bool:

    for i in range(1, len(chain)):
        if chain[i]["prev_hash"] != chain[i - 1]["hash"]:
            return False
    return True


def print_chain(blockchain: List[Block]):
    for b in blockchain:
        print(f"Index: {b.index}, Hash: {b.hash[:10]}..., Tx: {len(b.transactions)}")


def mine_block(
    transactions: List[Dict],
    blockchain: List[Block],
    node_id: str,
    reward: int,
    difficulty: int,
    blockchain_fpath: str,
    peers_fpath: str,
    port: int,
):
    new_block = create_block(
        transactions,
        blockchain[-1].hash,
        miner=node_id,
        index=len(blockchain),
        reward=reward,
        difficulty=difficulty,
    )
    blockchain.append(new_block)
    transactions.clear()
    save_chain(blockchain_fpath, blockchain)
    broadcast_block(new_block, peers_fpath, port)
    print(f"[✓] Block {new_block.index} mined and broadcasted.")


def make_transaction(sender, recipient, amount, transactions, peers_file, port):
    tx = {"from": sender, "to": recipient, "amount": amount}
    transactions.append(tx)
    broadcast_transaction(tx, peers_file, port)
    print("[+] Transaction added.")


def get_balance(node_id: str, blockchain: List[Block]) -> float:
    balance = 0.0
    for block in blockchain:
        for tx in block.transactions:
            if tx["to"] == node_id:
                balance += float(tx["amount"])
            if tx["from"] == node_id:
                balance -= float(tx["amount"])
    return balance


def on_valid_block_callback(fpath: str, chain: List[Block]):
    save_chain(fpath, chain)




def is_valid_chain(chain_data: List[Dict], difficulty: int) -> bool:
    """Valida cadeia serializada recebida da rede."""
    if not chain_data or chain_data[0]["index"] != 0 or chain_data[0]["hash"] != "0":
        return False

    blocks: List[Block] = [create_block_from_dict(b) for b in chain_data]

    for i in range(1, len(blocks)):
        prev, curr = blocks[i - 1], blocks[i]

        if curr.index != prev.index + 1:
            return False
        if curr.prev_hash != prev.hash:
            return False

        expected = hash_block(curr)
        if curr.hash != expected:
            return False
        if not curr.hash.startswith("0" * difficulty):
            return False

    return True


def replace_chain_if_better(
    local_chain: List[Block],
    incoming_chain_data: List[Dict],
    difficulty: int,
) -> bool:
    """
    Se a cadeia recebida for válida e mais longa, substitui a local.
    Retorna True em caso de troca.
    """
    if not is_valid_chain(incoming_chain_data, difficulty):
        return False

    if len(incoming_chain_data) <= len(local_chain):
        return False

    new_chain = [create_block_from_dict(b) for b in incoming_chain_data]
    local_chain.clear()
    local_chain.extend(new_chain)
    print("[✓] Local chain replaced by longer valid chain from peer.")
    return True
