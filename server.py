import socket
import threading
import json
import random
from typing import Dict, List

class GameRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: Dict[socket.socket, dict] = {}  # socket -> player_info
        self.game_started = False
        self.current_phase = "waiting"  # waiting, night, day, vote
        self.votes = {}
        self.roles = ["Loup-Garou", "Villageois", "Sorcière", "Voyante"]
    
    def add_player(self, client_socket: socket.socket, username: str):
        """Ajoute un joueur à la room"""
        self.players[client_socket] = {
            "username": username,
            "role": None,
            "is_alive": True
        }
    
    def remove_player(self, client_socket: socket.socket):
        """Retire un joueur de la room"""
        if client_socket in self.players:
            del self.players[client_socket]
    
    def start_game(self):
        """Démarre la partie et assigne les rôles"""
        if len(self.players) >= 4:  # Minimum 4 joueurs
            self.game_started = True
            self.assign_roles()
            return True
        return False
    
    def assign_roles(self):
        """Assigne les rôles aux joueurs"""
        available_roles = ["Loup-Garou", "Loup-Garou", "Sorcière", "Voyante"]
        # Complète avec des villageois
        while len(available_roles) < len(self.players):
            available_roles.append("Villageois")
        
        random.shuffle(available_roles)
        for socket, player in self.players.items():
            player["role"] = available_roles.pop()

class LoupGarouServer:
    def __init__(self, host='localhost', port=5000):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen()
        
        self.rooms: Dict[str, GameRoom] = {}
        self.clients: Dict[socket.socket, str] = {}  # socket -> room_id
    
    def broadcast_to_room(self, room_id: str, message: dict, exclude_socket=None):
        """Envoie un message à tous les joueurs d'une room"""
        if room_id in self.rooms:
            encoded_message = json.dumps(message).encode('utf-8')
            for client_socket in self.rooms[room_id].players:
                if client_socket != exclude_socket:
                    try:
                        client_socket.send(encoded_message)
                    except:
                        self.handle_disconnection(client_socket)
    
    def create_room(self) -> str:
        """Crée une nouvelle room"""
        room_id = str(random.randint(1000, 9999))
        while room_id in self.rooms:
            room_id = str(random.randint(1000, 9999))
        self.rooms[room_id] = GameRoom(room_id)
        return room_id
    
    def handle_client(self, client_socket: socket.socket):
        """Gère les connexions des clients"""
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                message = json.loads(data)
                self.process_message(client_socket, message)
                
        except Exception as e:
            print(f"Erreur: {e}")
        finally:
            self.handle_disconnection(client_socket)
    
    def process_message(self, client_socket: socket.socket, message: dict):
        """Traite les messages reçus des clients"""
        msg_type = message.get('type')
        
        if msg_type == 'create_room':
            room_id = self.create_room()
            self.clients[client_socket] = room_id
            self.rooms[room_id].add_player(client_socket, message['username'])
            response = {
                'type': 'room_created',
                'room_id': room_id
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        elif msg_type == 'join_room':
            room_id = message['room_id']
            if room_id in self.rooms and not self.rooms[room_id].game_started:
                self.clients[client_socket] = room_id
                self.rooms[room_id].add_player(client_socket, message['username'])
                response = {
                    'type': 'room_joined',
                    'room_id': room_id
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                # Informe les autres joueurs
                self.broadcast_to_room(room_id, {
                    'type': 'player_joined',
                    'username': message['username']
                }, client_socket)
                
        elif msg_type == 'chat':
            room_id = self.clients.get(client_socket)
            if room_id:
                self.broadcast_to_room(room_id, {
                    'type': 'chat',
                    'username': message['username'],
                    'content': message['content']
                })
                
        elif msg_type == 'start_game':
            room_id = self.clients.get(client_socket)
            if room_id and self.rooms[room_id].start_game():
                # Envoie les rôles aux joueurs
                for player_socket, player_info in self.rooms[room_id].players.items():
                    response = {
                        'type': 'game_started',
                        'role': player_info['role']
                    }
                    player_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_disconnection(self, client_socket: socket.socket):
        """Gère la déconnexion d'un client"""
        room_id = self.clients.get(client_socket)
        if room_id:
            room = self.rooms.get(room_id)
            if room:
                username = room.players[client_socket]['username']
                room.remove_player(client_socket)
                self.broadcast_to_room(room_id, {
                    'type': 'player_left',
                    'username': username
                })
                
                # Supprime la room si elle est vide
                if not room.players:
                    del self.rooms[room_id]
        
        if client_socket in self.clients:
            del self.clients[client_socket]
        client_socket.close()
    
    def run(self):
        """Lance le serveur"""
        print("Serveur démarré...")
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                print(f"Nouvelle connexion de {address}")
                threading.Thread(target=self.handle_client, 
                               args=(client_socket,), 
                               daemon=True).start()
        except KeyboardInterrupt:
            print("Arrêt du serveur...")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = LoupGarouServer()
    server.run()