# constants.py
import pygame

# Colors (RGB)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PINK  = (255, 182, 193)  # Soft pink for walls
RED   = (220, 20, 60)    # Deep red for the goal/text
GOLD  = (255, 215, 0)    # Optional highlight color

# Screen Dimensions
WIDTH = 800
HEIGHT = 600
TILE_SIZE = 40  # 800/40 = 20 columns; 600/40 = 15 rows

# Quiz Data
# Format: ("Question text", ["Option 1", "Option 2", "Option 3"], index_of_correct_answer)
QUESTIONS = [
    ("When did we first meet in person?", 
     ["August 25th", "September 29th", "September 30th"], 1),
    
    ("Which of these is my absolute favorite thing about you?", 
     ["Your kindness", "Your laugh", "Everything"], 2),
    
    ("If we were at a cafe right now, what would you order?", 
     ["Dragon Fruit Refresher", "Strawberry referesher", "Hot Chocolate"], 0),
]

# Maze Map (20 columns x 15 rows)
# W = Wall, S = Start, E = End (The Center), . = Path
HEART_MAZE = [
    "WWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWW",
    "WWW   WWWWWW   WWWWW",
    "WW  S  WWWW      WWW",
    "W  .W.  WW  .W.  WWW",
    "W  .W.      .W.  WWW",
    "WW  .WWWWWWWW.  WWWW",
    "WWW .W......W. WWWWW",
    "WWWW.W.WWWW.W.WWWWWW",
    "WWWW.W.W  W.W.WWWWWW",
    "WWWW.W.W E .W.WWWWWW",
    "WWWW...WWWW...WWWWWW",
    "WWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWW"
]