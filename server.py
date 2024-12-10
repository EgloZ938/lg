import socket
import threading
import json
import random
from typing import Dict, List
from enum import Enum
from typing import Dict, List, Optional, Set, Any


class GamePhase(Enum):
    WAITING = "waiting"
    NIGHT_VOLEUR = "night_voleur"
    NIGHT_CUPIDON = "night_cupidon"
    NIGHT_AMOUREUX = "night_amoureux"
    NIGHT_VOYANTE = "night_voyante"
    NIGHT_LOUP = "night_loup"
    NIGHT_SORCIERE = "night_sorciere"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"

class Role(Enum):
    VILLAGEOIS = "Villageois"
    LOUP_GAROU = "Loup-Garou"
    SORCIERE = "Sorcière"
    VOYANTE = "Voyante"
    CUPIDON = "Cupidon"
    CHASSEUR = "Chasseur"
    PETITE_FILLE = "Petite Fille"
    VOLEUR = "Voleur"
    CAPITAINE = "Capitaine"

class PlayerState:
    def __init__(self, username: str):
        self.username = username
        self.role: Optional[Role] = None
        self.is_alive = True
        self.is_amoureux = False
        self.amoureux_with = None
        self.voted_by: Set[str] = set()  # username des joueurs qui ont voté contre
        self.has_voted = False
        self.is_captain = False
        
        # Capacités spéciales
        self.sorciere_heal = True
        self.sorciere_kill = True
        self.chasseur_can_shoot = True

class GameRoom:

    PHASE_DURATIONS = {
        GamePhase.NIGHT_VOLEUR: 30,    # 30 secondes
        GamePhase.NIGHT_CUPIDON: 30,
        GamePhase.NIGHT_AMOUREUX: 20,
        GamePhase.NIGHT_VOYANTE: 30,
        GamePhase.NIGHT_LOUP: 45,
        GamePhase.NIGHT_SORCIERE: 30,
        GamePhase.DAY_DISCUSSION: 30,  # 30 secondes
        GamePhase.DAY_VOTE: 45,
    }

    def __init__(self, room_id: str, max_players: int = 16):
        self.room_id = room_id
        self.max_players = max_players
        self.min_players = 6  # Minimum pour une partie équilibrée
        
        # Gestion des joueurs
        self.players: Dict[socket.socket, PlayerState] = {}
        
        # État du jeu
        self.game_started = False
        self.current_phase = GamePhase.WAITING
        self.current_turn = 0
        
        # Gestion des rôles et actions
        self.available_roles = []
        self.captain_socket = None
        self.victim_socket = None  # Socket de la victime des loups
        self.second_victim_socket = None  # Victime de la sorcière
        self.saved_by_witch = False  # Si la sorcière a utilisé sa potion de soin
        self.killed_by_witch = False  # Si la sorcière a utilisé sa potion de mort
        self.lovers: List[socket.socket] = []  # Liste des deux amoureux
        self.seen_by_seer = None  # Joueur vu par la voyante
        self.votes: Dict[socket.socket, socket.socket] = {}  # Votant -> Voté
        self.night_actions: Dict[socket.socket, Any] = {}  # Actions spéciales de nuit
        self.phase_timer = None
        self.server = None  # Référence au serveur pour les callbacks
        
    def add_player(self, client_socket: socket.socket, username: str) -> bool:
        """Ajoute un joueur à la room"""
        if len(self.players) >= self.max_players:
            return False
        self.players[client_socket] = PlayerState(username)
        return True
    
    def remove_player(self, client_socket: socket.socket):
        """Retire un joueur de la room"""
        if client_socket in self.players:
            # Si le joueur est capitaine, on doit en choisir un nouveau
            if client_socket == self.captain_socket:
                self.captain_socket = None
            del self.players[client_socket]
    
    def setup_roles(self):
        """Configure les rôles disponibles selon le nombre de joueurs"""
        nb_players = len(self.players)
        
        # Configuration des rôles pour 6 joueurs minimum
        if 6 <= nb_players <= 8:
            self.available_roles = [
                Role.LOUP_GAROU, Role.LOUP_GAROU,  # 2 loups
                Role.VOYANTE,  # 1 voyante
                Role.SORCIERE  # 1 sorcière
            ]
        elif 9 <= nb_players <= 12:
            self.available_roles = [
                Role.LOUP_GAROU, Role.LOUP_GAROU,  # 2 loups
                Role.VOYANTE,
                Role.SORCIERE,
                Role.CHASSEUR,
                Role.CUPIDON
            ]
        else:  # 13-16 joueurs
            self.available_roles = [
                Role.LOUP_GAROU, Role.LOUP_GAROU, Role.LOUP_GAROU,  # 3 loups
                Role.VOYANTE,
                Role.SORCIERE,
                Role.CHASSEUR,
                Role.CUPIDON,
                Role.PETITE_FILLE
            ]
        
        # Complète avec des villageois
        while len(self.available_roles) < nb_players:
            self.available_roles.append(Role.VILLAGEOIS)
            
        random.shuffle(self.available_roles)
            
    def assign_roles(self):
        """Assigne les rôles aux joueurs"""
        for socket, player in self.players.items():
            if self.available_roles:
                player.role = self.available_roles.pop()

    def start_game(self) -> bool:
        """Démarre la partie"""
        if self.min_players <= len(self.players) <= self.max_players:
            self.game_started = True
            self.setup_roles()
            self.assign_roles()
            self.current_phase = GamePhase.NIGHT_VOLEUR
            self.current_turn = 1
            return True
        return False

    def get_players_info(self) -> dict:
        """Retourne les informations sur les joueurs"""
        return {
            'player_count': len(self.players),
            'max_players': self.max_players,
            'players': [player.username for player in self.players.values()],
            'phase': self.current_phase.value if self.game_started else "waiting"
        }

    def get_roles_in_game(self) -> set:
        """Retourne l'ensemble des rôles présents dans la partie"""
        return set(player.role for player in self.players.values())
    
    def get_available_phases(self) -> list:
        """Retourne les phases dans l'ordre correct"""
        # Les phases de nuit d'abord
        phases = []
        roles = self.get_roles_in_game()
        
        if self.current_turn == 1 and Role.CUPIDON in roles:
            phases.extend([GamePhase.NIGHT_CUPIDON, GamePhase.NIGHT_AMOUREUX])
        
        if Role.LOUP_GAROU in roles:
            phases.append(GamePhase.NIGHT_LOUP)
        if Role.VOYANTE in roles:
            phases.append(GamePhase.NIGHT_VOYANTE)
        if Role.SORCIERE in roles:
            phases.append(GamePhase.NIGHT_SORCIERE)
            
        # Puis les phases de jour
        phases.extend([GamePhase.DAY_DISCUSSION, GamePhase.DAY_VOTE])
        
        return phases

    def next_phase(self):
        """Passe à la phase suivante"""
        available_phases = self.get_available_phases()
        
        if not available_phases:
            return
            
        if self.current_phase not in available_phases:
            self.current_phase = available_phases[0]
        else:
            current_idx = available_phases.index(self.current_phase)
            next_idx = (current_idx + 1) % len(available_phases)
            self.current_phase = available_phases[next_idx]
            
            # Si on revient au début, c'est un nouveau tour
            if next_idx == 0:
                self.current_turn += 1

    def start_phase_timer(self):
        """Démarre le timer pour la phase actuelle"""
        if self.current_phase in self.PHASE_DURATIONS:
            duration = self.PHASE_DURATIONS[self.current_phase]
            if self.phase_timer:
                self.phase_timer.cancel()
            self.phase_timer = threading.Timer(duration, self.force_phase_completion)
            self.phase_timer.start()

    def force_phase_completion(self):
        """Force le passage à la phase suivante quand le timer expire"""
        if self.server:
            self.server.check_phase_completion(self, force=True)

    def process_night_action(self, player_socket: socket.socket, action: dict) -> bool:
        """Traite les actions de nuit des joueurs"""
        player = self.players[player_socket]
        action_type = action.get('action')
        target_socket = action.get('target')

        if self.current_phase == GamePhase.NIGHT_LOUP and player.role == Role.LOUP_GAROU:
            self.victim_socket = target_socket
            return True
            
        elif self.current_phase == GamePhase.NIGHT_VOYANTE and player.role == Role.VOYANTE:
            self.seen_by_seer = target_socket
            return True
            
        elif self.current_phase == GamePhase.NIGHT_SORCIERE and player.role == Role.SORCIERE:
            if action_type == 'heal' and not self.saved_by_witch:
                self.saved_by_witch = True
                self.victim_socket = None
                return True
            elif action_type == 'kill' and not self.killed_by_witch:
                self.killed_by_witch = True
                self.second_victim_socket = target_socket
                return True
                
        elif self.current_phase == GamePhase.NIGHT_CUPIDON and player.role == Role.CUPIDON:
            if len(action.get('targets', [])) == 2:
                self.lovers = action['targets']
                for lover_socket in self.lovers:
                    self.players[lover_socket].is_amoureux = True
                    self.players[lover_socket].amoureux_with = [s for s in self.lovers if s != lover_socket][0]
                return True

        return False

    def process_vote(self, voter_socket: socket.socket, voted_socket: socket.socket) -> bool:
        """Traite les votes des joueurs"""
        if self.current_phase == GamePhase.DAY_VOTE:
            player = self.players[voter_socket]
            if not player.has_voted and player.is_alive:
                self.votes[voter_socket] = voted_socket
                player.has_voted = True
                # Si le votant est capitaine, son vote compte double
                if voter_socket == self.captain_socket:
                    self.votes[f"{voter_socket}_captain"] = voted_socket
                return True
        return False

    def resolve_votes(self) -> Optional[socket.socket]:
        """Résout les votes et retourne le joueur éliminé"""
        if not self.votes:
            return None

        # Compte les votes
        vote_count = {}
        for voted_socket in self.votes.values():
            if voted_socket not in vote_count:
                vote_count[voted_socket] = 0
            vote_count[voted_socket] += 1

        # Trouve le plus voté
        max_votes = max(vote_count.values())
        most_voted = [socket for socket, votes in vote_count.items() if votes == max_votes]

        # En cas d'égalité et si le capitaine est vivant
        if len(most_voted) > 1 and self.captain_socket and self.players[self.captain_socket].is_alive:
            for voted_socket in most_voted:
                if self.votes.get(self.captain_socket) == voted_socket:
                    return voted_socket
        
        return most_voted[0] if len(most_voted) == 1 else None

    def check_victory(self) -> Optional[str]:
        """Vérifie si une équipe a gagné"""
        wolves_alive = sum(1 for p in self.players.values() 
                         if p.is_alive and p.role == Role.LOUP_GAROU)
        villagers_alive = sum(1 for p in self.players.values() 
                            if p.is_alive and p.role != Role.LOUP_GAROU)

        # Victoire des loups
        if villagers_alive <= wolves_alive:
            return "loups"
        # Victoire des villageois
        elif wolves_alive == 0:
            return "villageois"
        # Victoire des amoureux
        elif len(self.lovers) == 2:
            if all(self.players[s].is_alive for s in self.lovers):
                roles = [self.players[s].role for s in self.lovers]
                if Role.LOUP_GAROU in roles and Role.LOUP_GAROU not in roles:
                    if len([p for p in self.players.values() if p.is_alive]) == 2:
                        return "amoureux"
        
        return None

    def kill_player(self, player_socket: socket.socket):
        """Tue un joueur et gère les effets en cascade"""
        if player_socket in self.players:
            player = self.players[player_socket]
            player.is_alive = False

            # Si le joueur est amoureux, son amoureux meurt aussi
            if player.is_amoureux and player.amoureux_with:
                self.kill_player(player.amoureux_with)

            # Si le joueur est chasseur, il peut tuer quelqu'un
            if player.role == Role.CHASSEUR and player.chasseur_can_shoot:
                return "chasseur_revenge"

            return "player_killed"
        return None

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
            try:
                encoded_message = json.dumps(message).encode('utf-8')
                for client_socket in list(self.rooms[room_id].players.keys()):  # Conversion en liste pour éviter les modifications pendant l'itération
                    if client_socket != exclude_socket:
                        try:
                            client_socket.send(encoded_message)
                        except Exception as e:
                            print(f"Erreur lors du broadcast: {e}")
                            self.handle_disconnection(client_socket)
            except Exception as e:
                print(f"Erreur générale lors du broadcast: {e}")
    
    def create_room(self) -> str:
        room_id = str(random.randint(1000, 9999))
        while room_id in self.rooms:
            room_id = str(random.randint(1000, 9999))
        room = GameRoom(room_id)
        room.server = self  # Permet au room d'appeler les méthodes du serveur
        self.rooms[room_id] = room
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
            room = self.rooms[room_id]
            if room.add_player(client_socket, message['username']):
                response = {
                    'type': 'room_created',
                    'room_id': room_id,
                    'players_info': room.get_players_info()
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
            else:
                response = {'type': 'room_full'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        elif msg_type == 'join_room':
            room_id = message['room_id']
            # Vérifie si la room existe
            if room_id not in self.rooms:
                response = {
                    'type': 'room_not_found',
                    'message': "Cette room n'existe pas"
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
                
            room = self.rooms[room_id]
            # Vérifie si la partie a déjà commencé
            if room.game_started:
                response = {
                    'type': 'game_already_started',
                    'message': "La partie a déjà commencé"
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
                
            # Essaie d'ajouter le joueur
            if room.add_player(client_socket, message['username']):
                self.clients[client_socket] = room_id
                response = {
                    'type': 'room_joined',
                    'room_id': room_id,
                    'players_info': room.get_players_info()
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                
                # Informe les autres joueurs
                self.broadcast_to_room(room_id, {
                    'type': 'player_joined',
                    'username': message['username'],
                    'players_info': room.get_players_info()
                }, client_socket)
            else:
                response = {
                    'type': 'room_full',
                    'message': "La room est pleine"
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
        
        elif msg_type == 'disconnect':
            self.handle_disconnection(client_socket)
                
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
            room = self.rooms.get(room_id)
            if room and room.start_game():
                # Envoie les rôles aux joueurs
                for player_socket, player_info in room.players.items():
                    response = {
                        'type': 'game_started',
                        'role': player_info.role.value
                    }
                    player_socket.send(json.dumps(response).encode('utf-8'))
                
                # Démarre la première phase
                room.next_phase()
                self.broadcast_to_room(room_id, {
                    'type': 'phase_change',
                    'phase': room.current_phase.value
                })
        
        elif msg_type == 'night_action':
            room_id = self.clients.get(client_socket)
            if room_id and room_id in self.rooms:
                room = self.rooms[room_id]
                action = message.get('action')
                target = message.get('target')
                
                # Convert target username to socket if needed
                target_socket = None
                if target:
                    target_socket = next((socket for socket, player in room.players.items() 
                                        if player.username == target), None)
                
                if room.process_night_action(client_socket, {
                    'action': action,
                    'target': target_socket,
                    'targets': message.get('targets')  # For Cupidon's action
                }):
                    # Send success response
                    response = {
                        'type': 'action_result',
                        'success': True
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                    # Special handling for Voyante
                    if action == 'see' and target_socket:
                        response = {
                            'type': 'seer_result',
                            'target': room.players[target_socket].username,
                            'role': room.players[target_socket].role.value
                        }
                        client_socket.send(json.dumps(response).encode('utf-8'))
                    
                    # Check if all night actions are completed
                    self.check_phase_completion(room)
                else:
                    response = {
                        'type': 'action_result',
                        'success': False,
                        'message': "Action impossible"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))

        elif msg_type == 'vote':
            room_id = self.clients.get(client_socket)
            if room_id and room_id in self.rooms:
                room = self.rooms[room_id]
                target = message.get('target')
                
                # Convert target username to socket
                target_socket = next((socket for socket, player in room.players.items() 
                                    if player.username == target), None)
                
                if target_socket and room.process_vote(client_socket, target_socket):
                    response = {
                        'type': 'action_result',
                        'success': True
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                    # Check if all votes are in
                    self.check_phase_completion(room)
                else:
                    response = {
                        'type': 'action_result',
                        'success': False,
                        'message': "Vote impossible"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))

    

    def check_phase_completion(self, room: GameRoom, force: bool = False):
        """Vérifie si la phase actuelle est terminée et passe à la suivante si nécessaire"""
        phase_complete = force  # Si force=True, on force le changement de phase
        
        if not force:
            if room.current_phase == GamePhase.NIGHT_LOUP:
                # Vérifie si tous les loups ont voté
                wolves = [s for s, p in room.players.items() if p.role == Role.LOUP_GAROU and p.is_alive]
                if room.victim_socket or not wolves:
                    phase_complete = True
                    
            elif room.current_phase == GamePhase.NIGHT_VOYANTE:
                # Vérifie si la voyante a utilisé son pouvoir
                voyante = next((s for s, p in room.players.items() if p.role == Role.VOYANTE and p.is_alive), None)
                if not voyante or room.seen_by_seer is not None:
                    phase_complete = True
                    
            elif room.current_phase == GamePhase.NIGHT_SORCIERE:
                # Vérifie si la sorcière a agi ou s'il n'y en a pas
                sorciere = next((s for s, p in room.players.items() if p.role == Role.SORCIERE and p.is_alive), None)
                if not sorciere or room.saved_by_witch or room.killed_by_witch:
                    phase_complete = True
                    
            elif room.current_phase == GamePhase.NIGHT_CUPIDON:
                # Vérifie si Cupidon a choisi les amoureux
                cupidon = next((s for s, p in room.players.items() if p.role == Role.CUPIDON and p.is_alive), None)
                if not cupidon or len(room.lovers) == 2 or room.current_turn > 1:
                    phase_complete = True
                    
            elif room.current_phase == GamePhase.NIGHT_VOLEUR:
                # Le voleur a un temps limité pour choisir
                phase_complete = True
                    
            elif room.current_phase == GamePhase.NIGHT_AMOUREUX:
                # Phase informative pour les amoureux
                phase_complete = True
                    
            elif room.current_phase == GamePhase.DAY_DISCUSSION:
                # La phase de discussion a une durée fixe
                if force:  # On ne complète que si le timer force
                    phase_complete = True
                    
            elif room.current_phase == GamePhase.DAY_VOTE:
                # Vérifie si tous les joueurs vivants ont voté
                alive_players = [s for s, p in room.players.items() if p.is_alive]
                votes_needed = len(alive_players)
                current_votes = len(room.votes)
                
                if current_votes >= votes_needed or force:
                    phase_complete = True
                    self.resolve_day_end(room)
            
        if phase_complete:
            # Annule le timer existant s'il y en a un
            if room.phase_timer:
                room.phase_timer.cancel()
                room.phase_timer = None

            # Si c'est la fin de la nuit, résoudre les morts
            if room.current_phase in [GamePhase.NIGHT_SORCIERE]:
                self.resolve_night_end(room)
            
            # Réinitialise les votes si on était en phase de vote
            if room.current_phase == GamePhase.DAY_VOTE:
                room.votes.clear()
                for player in room.players.values():
                    player.has_voted = False
            
            # Passe à la phase suivante
            room.next_phase()
            
            # Envoie d'abord le changement de phase
            self.broadcast_to_room(room.room_id, {
                'type': 'phase_change',
                'phase': room.current_phase.value
            })
            
            # Démarre le timer pour la nouvelle phase et envoie la durée aux clients
            if room.current_phase in room.PHASE_DURATIONS:
                duration = room.PHASE_DURATIONS[room.current_phase]
                
                # Envoie la durée du timer aux clients
                self.broadcast_to_room(room.room_id, {
                    'type': 'phase_timer',
                    'duration': duration
                })
                
                # Démarre le timer
                room.phase_timer = threading.Timer(
                    duration,
                    lambda: self.check_phase_completion(room, force=True)
                )
                room.phase_timer.start()
            
            # Message spécial pour la victime des loups à la sorcière
            if room.current_phase == GamePhase.NIGHT_SORCIERE and room.victim_socket:
                sorciere_socket = next((s for s, p in room.players.items() 
                                    if p.role == Role.SORCIERE and p.is_alive), None)
                if sorciere_socket:
                    victim_name = room.players[room.victim_socket].username
                    self.send_to_player(sorciere_socket, {
                        'type': 'victim_info',
                        'victim': victim_name
                    })
            
            # Vérifie les conditions de victoire après chaque changement de phase
            winner = room.check_victory()
            if winner:
                if room.phase_timer:
                    room.phase_timer.cancel()
                self.broadcast_to_room(room.room_id, {
                    'type': 'game_over',
                    'winner': winner
                })

    def send_to_player(self, player_socket: socket.socket, message: dict):
        """Envoie un message à un joueur spécifique"""
        try:
            encoded_message = json.dumps(message).encode('utf-8')
            player_socket.send(encoded_message)
        except Exception as e:
            print(f"Erreur lors de l'envoi au joueur: {e}")
            self.handle_disconnection(player_socket)

    def resolve_night_end(self, room: GameRoom):
        """Résout les morts de la nuit"""
        # Traite la victime des loups
        if room.victim_socket and not room.saved_by_witch:
            self.kill_player(room, room.victim_socket)
            
        # Traite la victime de la sorcière
        if room.second_victim_socket:
            self.kill_player(room, room.second_victim_socket)
        
        # Réinitialise les variables de nuit
        room.victim_socket = None
        room.second_victim_socket = None
        room.saved_by_witch = False
        room.killed_by_witch = False

    def resolve_day_end(self, room: GameRoom):
        """Résout les votes de la journée"""
        voted_socket = room.resolve_votes()
        if voted_socket:
            self.kill_player(room, voted_socket)
        
        # Réinitialise les votes
        room.votes.clear()
        for player in room.players.values():
            player.has_voted = False

    def kill_player(self, room: GameRoom, player_socket: socket.socket):
        """Gère la mort d'un joueur"""
        if player_socket in room.players:
            result = room.kill_player(player_socket)
            
            # Notification de mort
            self.broadcast_to_room(room.room_id, {
                'type': 'player_death',
                'username': room.players[player_socket].username
            })
            
            # Si c'est le chasseur qui meurt
            if result == "chasseur_revenge":
                # Permettre au chasseur de tirer
                response = {
                    'type': 'chasseur_revenge',
                    'message': "Vous pouvez tirer sur quelqu'un avant de mourir"
                }
                player_socket.send(json.dumps(response).encode('utf-8'))
            
            # Vérifie la condition de victoire
            winner = room.check_victory()
            if winner:
                if room.phase_timer:
                    room.phase_timer.cancel()
                self.broadcast_to_room(room.room_id, {
                    'type': 'game_over',
                    'winner': winner
                })

    def handle_disconnection(self, client_socket: socket.socket):
        """Gère la déconnexion d'un client"""
        try:
            room_id = self.clients.get(client_socket)
            if room_id:
                room = self.rooms.get(room_id)
                if room and client_socket in room.players:
                    try:
                        username = room.players[client_socket].username
                        room.remove_player(client_socket)
                        
                        # Informe les autres joueurs de la déconnexion
                        self.broadcast_to_room(room_id, {
                            'type': 'player_left',
                            'username': username,
                            'players_info': room.get_players_info()
                        })
                    except Exception as e:
                        print(f"Erreur lors du traitement de la déconnexion: {e}")
                        
                    # Supprime la room si elle est vide
                    if not room.players:
                        if room.phase_timer:
                            room.phase_timer.cancel()
                        del self.rooms[room_id]
            
            if client_socket in self.clients:
                del self.clients[client_socket]
                
        except Exception as e:
            print(f"Erreur lors de la déconnexion: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
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