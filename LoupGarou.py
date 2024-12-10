import tkinter as tk
from tkinter import ttk
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
        
        # Boutons
        ttk.Button(self.main_menu, text="Créer une partie", 
                   command=self.create_game).pack(pady=5)
        ttk.Button(self.main_menu, text="Rejoindre une partie", 
                   command=self.join_game).pack(pady=5)
        
        self.show_frame(self.main_menu)
        
    def setup_game_room(self):
        """Configure la salle de jeu"""
        self.game_room = ttk.Frame(self.root)
        
        # Zone de chat
        self.chat_area = tk.Text(self.game_room, height=20, width=50, state='disabled')
        self.chat_area.pack(pady=10)
        
        # Zone de saisie du message
        self.message_entry = ttk.Entry(self.game_room)
        self.message_entry.pack(fill=tk.X, padx=10)
        ttk.Button(self.game_room, text="Envoyer", 
                   command=self.send_message).pack(pady=5)
        
        # Liste des joueurs
        self.players_list = tk.Listbox(self.game_room, height=10)
        self.players_list.pack(pady=10)
    
    def connect_to_server(self, host='localhost', port=5000):
        """Établit la connexion avec le serveur"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.connected = True
            
            # Démarre un thread pour recevoir les messages
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"Erreur de connexion: {e}")
            return False
    
    def receive_messages(self):
        """Reçoit les messages du serveur"""
        while self.connected:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    self.handle_message(json.loads(message))
            except:
                self.connected = False
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
    
    def create_game(self):
        """Crée une nouvelle partie"""
        self.username = self.username_entry.get()
        if self.connect_to_server():
            self.setup_game_room()
            self.show_frame(self.game_room)
    
    def join_game(self):
        """Rejoint une partie existante"""
        self.username = self.username_entry.get()
        if self.connect_to_server():
            self.setup_game_room()
            self.show_frame(self.game_room)
    
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