import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json

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
        
        # Création des différentes pages
        self.main_menu = None
        self.game_room = None
        self.current_frame = None
        
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
        self.room_label = ttk.Label(info_frame, text=f"Room: {self.room_id}")
        self.room_label.pack(side=tk.LEFT)
        self.role_label = ttk.Label(info_frame, text="En attente du début de la partie")
        self.role_label.pack(side=tk.RIGHT)
        
        # Zone de chat
        chat_frame = ttk.Frame(self.game_room)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Chat et liste des joueurs côte à côte
        self.chat_area = tk.Text(chat_frame, height=20, width=40, state='disabled')
        self.chat_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        players_frame = ttk.Frame(chat_frame)
        players_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        ttk.Label(players_frame, text="Joueurs").pack()
        self.players_list = tk.Listbox(players_frame, height=10, width=20)
        self.players_list.pack()
        
        # Zone de saisie du message
        input_frame = ttk.Frame(self.game_room)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame, text="Envoyer", 
                   command=self.send_message).pack(side=tk.RIGHT, padx=5)
        
        # Bouton pour démarrer la partie
        self.start_button = ttk.Button(self.game_room, text="Démarrer la partie",
                                     command=self.start_game)
        self.start_button.pack(pady=5)
    
    def handle_message(self, message):
        """Traite les messages reçus du serveur"""
        msg_type = message.get('type')
        
        if msg_type == 'room_created':
            self.room_id = message['room_id']
            self.room_label.config(text=f"Room: {self.room_id}")
            self.add_chat_message("Système", f"Room créée! ID: {self.room_id}")
            
        elif msg_type == 'room_joined':
            self.room_id = message['room_id']
            self.room_label.config(text=f"Room: {self.room_id}")
            self.add_chat_message("Système", "Vous avez rejoint la partie!")
            
        elif msg_type == 'chat':
            self.add_chat_message(message['username'], message['content'])
            
        elif msg_type == 'player_joined':
            self.add_chat_message("Système", f"{message['username']} a rejoint la partie")
            self.update_players_list(message['players'])
            
        elif msg_type == 'player_left':
            self.add_chat_message("Système", f"{message['username']} a quitté la partie")
            self.update_players_list(message['players'])
            
        elif msg_type == 'game_started':
            self.game_started = True
            self.role = message['role']
            self.role_label.config(text=f"Rôle: {self.role}")
            self.start_button.config(state='disabled')
            self.add_chat_message("Système", f"La partie commence! Vous êtes {self.role}")
    
    def add_chat_message(self, username, content):
        """Ajoute un message au chat"""
        self.chat_area.config(state='normal')
        self.chat_area.insert('end', f"{username}: {content}\n")
        self.chat_area.see('end')
        self.chat_area.config(state='disabled')
    
    def update_players_list(self, players):
        """Met à jour la liste des joueurs"""
        self.players_list.delete(0, tk.END)
        for player in players:
            self.players_list.insert(tk.END, player)
    
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
    
    def start_game(self):
        """Démarre la partie"""
        if self.connected:
            message = {
                'type': 'start_game'
            }
            self.client_socket.send(json.dumps(message).encode('utf-8'))
    
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