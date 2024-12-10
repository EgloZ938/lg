import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
from enum import Enum

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

class LoupGarouClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Loup-Garou")
        self.root.geometry("800x600")
        
        # Variables pour la connexion
        self.username = ""
        self.client_socket = None
        self.connected = False
        self.room_id = None
        self.role = None
        self.game_started = False
        
        # États du joueur
        self.is_alive = True
        self.is_amoureux = False
        self.amoureux_with = None
        self.potion_heal = True
        self.potion_kill = True
        self.has_voted = False
        self.is_captain = False
        
        # Variables pour la sélection de Cupidon
        self.selected_lovers = []
        
        # Variables de phase
        self.current_phase = None
        self.can_act = False
        
        # Création des différentes pages
        self.main_menu = None
        self.game_room = None
        self.current_frame = None
        self.action_window = None
        
        # Dictionnaire des joueurs
        self.players_dict = {}  # username -> état (vivant/mort)
        
        self.setup_main_menu()

    def setup_main_menu(self):
        """Configure le menu principal"""
        self.main_menu = ttk.Frame(self.root)
        
        # Titre
        title = ttk.Label(self.main_menu, text="Loup-Garou", font=("Arial", 24))
        title.pack(pady=20)
        
        # Champ pour le nom d'utilisateur
        username_frame = ttk.Frame(self.main_menu)
        username_frame.pack(pady=10)
        ttk.Label(username_frame, text="Nom d'utilisateur:").pack(side=tk.LEFT)
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side=tk.LEFT, padx=5)
        
        # Frame pour rejoindre une partie
        join_frame = ttk.Frame(self.main_menu)
        join_frame.pack(pady=10)
        ttk.Label(join_frame, text="ID Room:").pack(side=tk.LEFT)
        self.room_entry = ttk.Entry(join_frame)
        self.room_entry.pack(side=tk.LEFT, padx=5)
        
        # Boutons
        ttk.Button(self.main_menu, text="Créer une partie", 
                   command=self.create_game).pack(pady=5)
        ttk.Button(self.main_menu, text="Rejoindre une partie", 
                   command=self.join_game).pack(pady=5)
        
        self.show_frame(self.main_menu)
        
    def setup_game_room(self):
        """Configure la salle de jeu"""
        self.game_room = ttk.Frame(self.root)
        
        # Info frame (Room ID et Rôle)
        info_frame = ttk.Frame(self.game_room)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Left side: Room info
        left_info = ttk.Frame(info_frame)
        left_info.pack(side=tk.LEFT)
        self.room_label = ttk.Label(left_info, text=f"Room: {self.room_id}")
        self.room_label.pack(side=tk.LEFT, padx=5)
        
        # Right side: Role info
        right_info = ttk.Frame(info_frame)
        right_info.pack(side=tk.RIGHT)
        self.role_label = ttk.Label(right_info, text="En attente du début de la partie")
        self.role_label.pack()
        
        # Main content
        content_frame = ttk.Frame(self.game_room)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Chat area (left side)
        chat_frame = ttk.Frame(content_frame)
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.chat_area = tk.Text(chat_frame, height=20, width=40, state='disabled')
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        
        # Players list (right side)
        players_frame = ttk.Frame(content_frame)
        players_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        
        # Phase label
        self.phase_label = ttk.Label(players_frame, text="Phase: -")
        self.phase_label.pack()

        # Timer label
        self.timer_label = ttk.Label(players_frame, text="")
        self.timer_label.pack()
        
        # Player count label
        self.player_count_label = ttk.Label(players_frame, text="Joueurs: 0/16")
        self.player_count_label.pack()
        
        # Players list
        self.players_list = tk.Listbox(players_frame, height=10, width=20)
        self.players_list.pack(fill=tk.Y, expand=True)
        
        # Message input area
        input_frame = ttk.Frame(self.game_room)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        
        ttk.Button(input_frame, text="Envoyer", 
                command=self.send_message).pack(side=tk.RIGHT, padx=5)
        
        # Action buttons frame
        self.action_buttons = ttk.Frame(self.game_room)
        self.action_buttons.pack(fill=tk.X, padx=10, pady=5)
        
        # Start button
        self.start_button = ttk.Button(self.action_buttons, text="Démarrer la partie",
                                    command=self.start_game, state='disabled')
        self.start_button.pack(side=tk.LEFT, pady=5)

        # Bouton Déconnexion
        ttk.Button(left_info, text="Déconnexion", 
                command=self.disconnect).pack(side=tk.LEFT, padx=5)
    
    def get_alive_players(self):
        """Retourne la liste des joueurs vivants"""
        return [username for username, is_alive in self.players_dict.items() if is_alive]

    def handle_message(self, message):
        """Traite les messages reçus du serveur"""
        msg_type = message.get('type')
        
        if msg_type == 'room_created':
            self.room_id = message['room_id']
            self.room_label.config(text=f"Room: {self.room_id}")
            self.add_chat_message("Système", f"Room créée! ID: {self.room_id}")
            self.update_players_list(message['players_info'])

        elif msg_type == 'room_not_found':
            messagebox.showerror("Erreur", message['message'])
            self.show_frame(self.main_menu)

        elif msg_type == 'game_already_started':
            messagebox.showerror("Erreur", message['message'])
            self.show_frame(self.main_menu)
            
        elif msg_type == 'room_joined':
            self.room_id = message['room_id']
            self.room_label.config(text=f"Room: {self.room_id}")
            self.add_chat_message("Système", "Vous avez rejoint la partie!")
            self.update_players_list(message['players_info'])
            
        elif msg_type == 'chat':
            self.add_chat_message(message['username'], message['content'])
            
        elif msg_type == 'player_joined':
            self.add_chat_message("Système", f"{message['username']} a rejoint la partie")
            self.update_players_list(message['players_info'])
            
        elif msg_type == 'player_left':
            self.add_chat_message("Système", f"{message['username']} a quitté la partie")
            self.update_players_list(message['players_info'])
            
        elif msg_type == 'game_started':
            self.game_started = True
            self.role = Role(message['role'])
            self.role_label.config(text=f"Rôle: {self.role.value}")
            self.start_button.config(state='disabled')
            self.add_chat_message("Système", f"La partie commence! Vous êtes {self.role.value}")
            
        elif msg_type == 'phase_change':
            self.current_phase = GamePhase(message['phase'])
            self.phase_label.config(text=f"Phase: {self.current_phase.value}")
            self.handle_phase(message['phase'])
            
        elif msg_type == 'phase_timer':
            duration = message.get('duration')
            self.start_timer(duration)

        elif msg_type == 'action_result':
            if message.get('success'):
                self.add_chat_message("Système", "Action effectuée avec succès!")
            else:
                messagebox.showerror("Erreur", message.get('message', "Action impossible"))

        elif msg_type == 'player_death':
            username = message['username']
            self.players_dict[username] = False
            if username == self.username:
                self.is_alive = False
                self.add_chat_message("Système", "Vous êtes mort!")
            else:
                self.add_chat_message("Système", f"{username} est mort!")

        elif msg_type == 'seer_result':
            target = message['target']
            role = message['role']
            self.add_chat_message("Système", f"Le rôle de {target} est {role}")

        elif msg_type == 'room_full':
            messagebox.showerror("Erreur", "La room est pleine!")
            self.show_frame(self.main_menu)

        elif msg_type == 'game_over':
            winner = message.get('winner')
            self.add_chat_message("Système", f"La partie est terminée! Victoire des {winner}!")
            # Désactiver toutes les actions
            self.disable_all_actions()
    
    def start_timer(self, duration: int):
        """Démarre un compte à rebours pour la phase actuelle"""
        def update_timer(remaining):
            if remaining <= 0:
                self.timer_label.config(text="Temps écoulé!")
                return
                
            minutes = remaining // 60
            seconds = remaining % 60
            self.timer_label.config(text=f"Temps restant: {minutes:02d}:{seconds:02d}")
            self.root.after(1000, update_timer, remaining - 1)
        
        update_timer(duration)

    def add_chat_message(self, username, content):
        """Ajoute un message au chat"""
        self.chat_area.config(state='normal')
        self.chat_area.insert('end', f"{username}: {content}\n")
        self.chat_area.see('end')
        self.chat_area.config(state='disabled')
    
    def update_players_list(self, players_info):
        """Met à jour la liste des joueurs et le compteur"""
        player_count = players_info['player_count']
        max_players = players_info['max_players']
        players = players_info['players']
        
        # Mise à jour du dictionnaire des joueurs
        self.players_dict = {player: True for player in players}
        
        # Mise à jour du compteur
        self.player_count_label.config(text=f"Joueurs: {player_count}/{max_players}")
        
        # Mise à jour de la liste
        self.players_list.delete(0, tk.END)
        for player in players:
            self.players_list.insert(tk.END, player)
            
        # Active le bouton de démarrage si assez de joueurs
        if 6 <= player_count <= max_players:
            self.start_button.config(state='normal')
        else:
            self.start_button.config(state='disabled')
    
    def handle_player_selection(self, player_list, callback, selection_window):
        """Gère la sélection d'un joueur dans une li"""
        selections = player_list.curselection()
        if selections:
            selected_player = player_list.get(selections[0])
            callback(selected_player)
            selection_window.destroy()
        else:
            messagebox.showerror("Erreur", "Veuillez sélectionner un joueur")

    def create_game(self):
        """Crée une nouvelle partie"""
        self.username = self.username_entry.get()
        if not self.username:
            messagebox.showerror("Erreur", "Veuillez entrer un nom d'utilisateur")
            return
            
        if self.connect_to_server():
            message = {
                'type': 'create_room',
                'username': self.username
            }
            self.client_socket.send(json.dumps(message).encode('utf-8'))
            self.setup_game_room()
            self.show_frame(self.game_room)
    
    def join_game(self):
        """Rejoint une partie existante"""
        self.username = self.username_entry.get()
        room_id = self.room_entry.get()
        
        if not self.username or not room_id:
            messagebox.showerror("Erreur", "Veuillez entrer un nom d'utilisateur et un ID de room")
            return
            
        if self.connect_to_server():
            message = {
                'type': 'join_room',
                'username': self.username,
                'room_id': room_id
            }
            self.client_socket.send(json.dumps(message).encode('utf-8'))
            self.setup_game_room()
            self.show_frame(self.game_room)
    
    def connect_to_server(self, host='localhost', port=5000):
        """Établit la connexion avec le serveur"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.connected = True
            
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Erreur de connexion", 
                               "Impossible de se connecter au serveur. Vérifiez qu'il est bien démarré.")
            return False
    
    def receive_messages(self):
        """Reçoit les messages du serveur"""
        while self.connected:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    self.root.after(0, self.handle_message, json.loads(message))
            except:
                self.connected = False
                self.root.after(0, messagebox.showerror, "Erreur", 
                              "Connexion au serveur perdue")
                break

    def send_message(self):
        """Envoie un message au serveur"""
        if self.message_entry.get() and self.connected:
            message = {
                'type': 'chat',
                'content': self.message_entry.get(),
                'username': self.username
            }
            self.client_socket.send(json.dumps(message).encode('utf-8'))
            self.message_entry.delete(0, tk.END)

    def start_game(self):
        """Démarre la partie"""
        if self.connected:
            message = {
                'type': 'start_game'
            }
            self.client_socket.send(json.dumps(message).encode('utf-8'))

    def disconnect(self):
        """Déconnecte le client et retourne au menu"""
        if self.connected:
            try:
                message = {
                    'type': 'disconnect',
                    'username': self.username
                }
                self.client_socket.send(json.dumps(message).encode('utf-8'))
            except:
                pass
            finally:
                self.client_socket.close()
                self.connected = False
                self.room_id = None
                self.role = None
                self.game_started = False
                self.show_frame(self.main_menu)

    def handle_phase(self, phase: str):
        """Gère l'affichage et les actions selon la phase"""
        current_phase = GamePhase(phase)
        self.current_phase = current_phase
        
        # Désactive toutes les actions par défaut
        self.disable_all_actions()
        
        # Phase NIGHT_LOUP
        if current_phase == GamePhase.NIGHT_LOUP:
            if self.role == Role.LOUP_GAROU:
                self.add_chat_message("Système", "C'est votre tour! Sélectionnez un joueur à tuer")
                self.enable_player_selection("Choisissez votre victime", self.send_wolf_action)
            else:
                self.add_chat_message("Système", "La nuit tombe... Les loups-garous choisissent leur victime...")
        
        # Phase NIGHT_VOYANTE
        elif current_phase == GamePhase.NIGHT_VOYANTE:
            if self.role == Role.VOYANTE:
                self.add_chat_message("Système", "C'est votre tour! Sélectionnez un joueur à examiner")
                self.enable_player_selection("Choisissez un joueur", self.send_seer_action)
            else:
                self.add_chat_message("Système", "La voyante examine un joueur...")
        
        # Phase NIGHT_SORCIERE
        elif current_phase == GamePhase.NIGHT_SORCIERE:
            if self.role == Role.SORCIERE:
                self.setup_witch_actions()
            else:
                self.add_chat_message("Système", "La sorcière décide d'utiliser ou non ses potions...")
        
        # Phase NIGHT_CUPIDON
        elif current_phase == GamePhase.NIGHT_CUPIDON:
            if self.role == Role.CUPIDON:
                self.add_chat_message("Système", "Choisissez deux joueurs à lier")
                self.setup_cupid_selection()
            else:
                self.add_chat_message("Système", "Cupidon choisit deux amoureux...")
        
        # Phase DAY_DISCUSSION
        elif current_phase == GamePhase.DAY_DISCUSSION:
            self.add_chat_message("Système", "Le village se réveille! C'est le moment de débattre")
            self.enable_chat()
        
        # Phase DAY_VOTE
        elif current_phase == GamePhase.DAY_VOTE:
            if self.is_alive:
                self.add_chat_message("Système", "C'est l'heure du vote!")
                self.enable_player_selection("Votez pour un joueur", self.send_vote)
            else:
                self.add_chat_message("Système", "Vous êtes mort, vous ne pouvez pas voter")

    def enable_player_selection(self, message: str, callback):
        """Active la sélection d'un joueur"""
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Sélection")
        selection_window.geometry("300x400")
        
        ttk.Label(selection_window, text=message).pack(pady=10)
        
        player_list = tk.Listbox(selection_window, height=10)
        player_list.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Ajoute uniquement les joueurs vivants
        for player in self.get_alive_players():
            if player != self.username:  # Ne pas s'afficher soi-même
                player_list.insert(tk.END, player)
        
        ttk.Button(selection_window, text="Confirmer",
                command=lambda: self.handle_player_selection(player_list, callback, selection_window)).pack(pady=10)
        
        ttk.Button(selection_window, text="Annuler",
                command=selection_window.destroy).pack(pady=5)

    def setup_witch_actions(self):
        """Configure les actions de la sorcière"""
        action_window = tk.Toplevel(self.root)
        action_window.title("Actions de la Sorcière")
        
        ttk.Label(action_window, text="Choisissez une action:").pack(pady=10)
        
        if self.potion_heal:
            ttk.Button(action_window, text="Utiliser potion de vie", 
                      command=lambda: self.send_witch_action("heal")).pack(pady=5)
        
        if self.potion_kill:
            ttk.Button(action_window, text="Utiliser potion de mort",
                      command=lambda: self.enable_player_selection(
                          "Choisir la cible", self.send_witch_kill)).pack(pady=5)
        
        ttk.Button(action_window, text="Ne rien faire",
                  command=lambda: self.send_witch_action("pass")).pack(pady=5)

    def setup_cupid_selection(self):
        """Configure la sélection pour Cupidon"""
        self.selected_lovers = []
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Sélection des amoureux")
        
        ttk.Label(selection_window, text="Choisissez deux joueurs:").pack(pady=10)
        
        player_list = tk.Listbox(selection_window, height=10, selectmode=tk.MULTIPLE)
        player_list.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        for player in self.get_alive_players():
            if player != self.username:
                player_list.insert(tk.END, player)
        
        def confirm_selection():
            selections = player_list.curselection()
            if len(selections) == 2:
                lovers = [player_list.get(i) for i in selections]
                self.send_cupid_action(lovers)
                selection_window.destroy()
            else:
                messagebox.showerror("Erreur", "Vous devez sélectionner exactement 2 joueurs")
        
        ttk.Button(selection_window, text="Confirmer",
                  command=confirm_selection).pack(pady=10)

    def send_wolf_action(self, target):
        """Envoie l'action du loup-garou"""
        message = {
            'type': 'night_action',
            'action': 'kill',
            'target': target
        }
        self.client_socket.send(json.dumps(message).encode('utf-8'))

    def send_seer_action(self, target):
        """Envoie l'action de la voyante"""
        message = {
            'type': 'night_action',
            'action': 'see',
            'target': target
        }
        self.client_socket.send(json.dumps(message).encode('utf-8'))

    def send_witch_action(self, action_type, target=None):
        """Envoie l'action de la sorcière"""
        message = {
            'type': 'night_action',
            'action': action_type
        }
        if target:
            message['target'] = target
        self.client_socket.send(json.dumps(message).encode('utf-8'))

    def send_witch_kill(self, target):
        """Envoie l'action de meurtre de la sorcière"""
        self.send_witch_action('kill', target)

    def send_cupid_action(self, lovers):
        """Envoie l'action de Cupidon"""
        message = {
            'type': 'night_action',
            'action': 'link',
            'targets': lovers
        }
        self.client_socket.send(json.dumps(message).encode('utf-8'))

    def send_vote(self, target):
        """Envoie un vote"""
        message = {
            'type': 'vote',
            'target': target
        }
        self.client_socket.send(json.dumps(message).encode('utf-8'))

    def disable_all_actions(self):
        """Désactive toutes les actions possibles"""
        self.message_entry.config(state='disabled')
        # Ferme toutes les fenêtres d'action ouvertes
        if self.action_window and self.action_window.winfo_exists():
            self.action_window.destroy()

    def enable_chat(self):
        """Active le chat"""
        self.message_entry.config(state='normal')

    def show_frame(self, frame):
        """Change la frame affichée"""
        if self.current_frame:
            self.current_frame.pack_forget()
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

    def run(self):
        """Lance l'application"""
        self.root.mainloop()

if __name__ == "__main__":
    client = LoupGarouClient()
    client.run()