import json
import os
import socket
import threading
import traceback
from typing import Callable, Dict, List

from block import Block, create_block_from_dict, hash_block
import chain


def list_peers(fpath: str):
    if not os.path.exists(fpath):
        print("[!] No peers file founded!")
        return []
    with open(fpath) as f:
        return [line.strip() for line in f if line.strip()]


def broadcast_block(block: Block, peers_fpath: str, port: int):
    print("[BROADCAST] Enviando bloco para os pares...")
    for peer in list_peers(peers_fpath):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer, port))
            s.send(json.dumps({"type": "block", "data": block.as_dict()}).encode())
            s.close()
        except Exception as e:
            print(f"[BROADCAST_BLOCK] Falha ao enviar para {peer}:{port} -> {e}")


def broadcast_transaction(tx: Dict, peers_fpath: str, port: int):
    print("[BROADCAST] Enviando transação para os pares...")
    for peer in list_peers(peers_fpath):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer, port))
            s.send(json.dumps({"type": "tx", "data": tx}).encode())
            s.close()
        except Exception as e:
            print(f"[BROADCAST_TX] Falha durante comunicação com {peer}:{port}. Erro: {e}")


def handle_client(
    conn: socket.socket,
    addr: str,
    blockchain: List[Block],
    difficulty: int,
    transactions: List[Dict],
    blockchain_fpath: str,
    on_valid_block_callback: Callable,
    port: int,
):
    try:
        data = conn.recv(8192).decode()
        if not data:
            conn.close()
            return

        msg = json.loads(data)

        if msg["type"] == "block":
            block = create_block_from_dict(msg["data"])
            expected_hash = hash_block(block)

            if (
                block.prev_hash == blockchain[-1].hash
                and block.hash.startswith("0" * difficulty)
                and block.hash == expected_hash
            ):
                blockchain.append(block)
                on_valid_block_callback(blockchain_fpath, blockchain)
                print(f"[✓] Novo bloco válido adicionado de {addr}")
            else:
                print(f"[!] Bloco inválido recebido de {addr}. Solicitando cadeia completa...")
                try:
                    peer_ip = addr[0] if isinstance(addr, tuple) else addr
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect((peer_ip, port))
                    s.send(json.dumps({"type": "get_chain"}).encode())
                    s.close()
                except Exception as e:
                    print(f"[SYNC] Falha ao solicitar cadeia de {addr}: {e}")

        elif msg["type"] == "tx":
            tx = msg["data"]
            if tx not in transactions:
                transactions.append(tx)
                print(f"[+] Transação recebida de {addr}")

        elif msg["type"] == "get_chain":
            try:
                chain_data = [b.as_dict() for b in blockchain]
                conn.send(json.dumps({"type": "chain", "data": chain_data}).encode())
                print(f"[SYNC] Enviando cadeia completa para {addr}")
            except Exception as e:
                print(f"[SYNC] Erro ao enviar cadeia: {e}")

        elif msg["type"] == "chain":
            incoming = msg["data"]
            if chain.replace_chain_if_better(blockchain, incoming, difficulty):
                on_valid_block_callback(blockchain_fpath, blockchain)
                print(f"[✓] Cadeia local substituída por versão mais longa de {addr}")
            else:
                print(f"[i] Cadeia recebida de {addr}, mas mantida local.")

    except Exception as e:
        print(f"Exception ao lidar com cliente: {e}\n{traceback.format_exc()}")

    conn.close()


def start_server(
    host: str,
    port: int,
    blockchain: List[Block],
    difficulty: int,
    transactions: List[Dict],
    blockchain_fpath: str,
    on_valid_block_callback: Callable,
):
    def server_thread():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        server.listen()
        print(f"[SERVER] Listening on {host}:{port}")

        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(
                    conn,
                    addr,
                    blockchain,
                    difficulty,
                    transactions,
                    blockchain_fpath,
                    on_valid_block_callback,
                    port,
                ),
            ).start()

    threading.Thread(target=server_thread, daemon=True).start()
