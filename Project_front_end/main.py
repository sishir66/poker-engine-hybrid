import sys
import pygame
from constants import HEART_MAZE, TILE_SIZE, WHITE, BLACK, PINK, RED, QUESTIONS

class ValentineApp:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("A Special Message")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Verdana", 28)
        
        # Game State
        self.state: str = "QUIZ"
        self.current_q: int = 0
        self.feedback: str = ""
        
        # Maze Entities
        self.walls: list[pygame.Rect] = []
        self.player_rect = pygame.Rect(0, 0, 25, 25)
        self.end_rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)

        #animation/proposal logic
        self.visible_chars = 0.0
        self.start_time = 0
        self.load_maze()

        self.scroll_y = 600

    def load_maze(self) -> None:
        """Translates the ASCII HEART_MAZE into Pygame Rects."""
        for r_idx, row in enumerate(HEART_MAZE):
            for c_idx, char in enumerate(row):
                x, y = c_idx * TILE_SIZE, r_idx * TILE_SIZE
                if char == "W":
                    self.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
                elif char == "S":
                    self.player_rect.topleft = (x + 7, y + 7)
                elif char == "E":
                    self.end_rect.topleft = (x, y)

    def handle_quiz(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            # Map keys K_1, K_2, K_3 to index 0, 1, 2
            answer = -1
            if event.key == pygame.K_1: answer = 0
            elif event.key == pygame.K_2: answer = 1
            elif event.key == pygame.K_3: answer = 2
            
            if answer == QUESTIONS[self.current_q][2]:
                self.current_q += 1
                self.feedback = "Correct! <3"
                if self.current_q >= len(QUESTIONS):
                    self.state = "MAZE"
            elif answer != -1:
                self.feedback = "Try again, beautiful!"

    def move_player(self) -> None:
        keys = pygame.key.get_pressed()
        old_pos = self.player_rect.topleft
        speed = 4
        
        if keys[pygame.K_UP]:    self.player_rect.y -= speed
        if keys[pygame.K_DOWN]:  self.player_rect.y += speed
        if keys[pygame.K_LEFT]:  self.player_rect.x -= speed
        if keys[pygame.K_RIGHT]: self.player_rect.x += speed

        for wall in self.walls:
            if self.player_rect.colliderect(wall):
                self.player_rect.topleft = old_pos
        
        if self.player_rect.colliderect(self.end_rect):
            self.state = "PROPOSAL"

    def run(self) -> None:
        while True:
            self.screen.fill((255, 240, 245)) # Lavender Blush
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                if self.state == "QUIZ":
                    self.handle_quiz(event)

            if self.state == "QUIZ":
                q, opts, _ = QUESTIONS[self.current_q]
                self.draw_text(q, BLACK, -100)
                for i, opt in enumerate(opts):
                    self.draw_text(f"{i+1}: {opt}", BLACK, -20 + (i * 40))
                self.draw_text(self.feedback, RED, 150)
            
            elif self.state == "MAZE":
                self.move_player()
                self.draw_maze()

            elif self.state == "PROPOSAL":
                self.draw_proposal()

            pygame.display.flip()
            self.clock.tick(60)

    def draw_maze(self) -> None:
        """Draws the walls, the goal, and the player onto the screen."""
        # Create a "darkness" surface
        fog = pygame.Surface((800, 600))
        fog.fill((30, 30, 30)) # Dark grey/black
        
        # "Punch a hole" in the darkness where the player is
        pygame.draw.circle(fog, (0, 0, 0, 0), self.player_rect.center, 100)
        
        # This requires the surface to support transparency
        # (Make sure to set fog.set_colorkey((0,0,0,0)) or use a specialized blend mode)
        self.screen.blit(fog, (0,0))
        # 1. Draw the floor (Background of the maze)
        self.screen.fill((255, 235, 240)) # Very light pink
        
        # 2. Draw the walls
        for wall in self.walls:
            pygame.draw.rect(self.screen, PINK, wall)
            # This adds a subtle 1-pixel border to make the blocks look clean
            pygame.draw.rect(self.screen, (255, 150, 160), wall, 1)
            
        # 3. Draw the Goal (The "E" block)
        # We make this a deep red so it looks like the 'target'
        self.draw_heart(self.screen, RED, self.end_rect)
        
        # 4. Draw the Player
        # You can make this a different color or even a small circle
        pygame.draw.rect(self.screen, (100, 150, 255), self.player_rect, border_radius=5)

    def draw_text(self, text: str, color: tuple, y_off: int) -> None:
        surf = self.font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=(400, 300 + y_off)))

    def draw_heart(self, surface, color, rect):
        """Draws a heart shape inside the provided Rect."""
        # Define the points for the heart (relative to the rect)
        # Top-left lobe, top-right lobe, bottom tip
        points = [
            (rect.centerx, rect.bottom), # Bottom Tip
            (rect.left, rect.centery),   # Left Curve
            (rect.left, rect.top + rect.height // 4), # Top Left
            (rect.centerx - rect.width // 4, rect.top), # Top Middle-Left
            (rect.centerx, rect.top + rect.height // 4), # Center Dip
            (rect.centerx + rect.width // 4, rect.top), # Top Middle-Right
            (rect.right, rect.top + rect.height // 4), # Top Right
            (rect.right, rect.centery),  # Right Curve
        ]
        pygame.draw.polygon(surface, color, points)
    
    def draw_proposal(self) -> None:
            """Renders the final message with a typewriter effect."""
            self.screen.fill((255, 240, 245)) 

            self.scroll_y -= 0.6
            self.visible_chars += 0.4  # Adjust this to change typing speed
            
            lines = [
                "My Dearest Grishu,",
                "",
                "I wanted to make something special for you to show",
                "how much I appreciate everything you do. You're the",
                "most important person in my life, and I'm so lucky",
                "to have you by my side. I'm so truly amazed by how",
                "amazing of a person you are. You make me the",
                "happiest person in the whole entire world.",
                "I love you so so so so so so much baby maya,"
                "",
                "",
                "Will you be my Valentine?",
            ]
            
            # char_count tracks how many total characters we have processed across all lines
            char_count = 0 
            
            for i, line in enumerate(lines):
                if self.visible_chars > char_count:
                    # Calculate how many characters of THIS line we are allowed to show
                    # We subtract char_count so it's relative to the start of this line
                    chars_in_this_line = int(self.visible_chars - char_count)
                    
                    # Slice the string to only show the allowed characters
                    text_to_show = line[:chars_in_this_line]
                    
                    # Apply the special color for the big question
                    color = RED
                    if "Valentine" in line:
                        color = (255, 105, 180) # Hot Pink
                    
                    # Draw the partial line
                    text_surf = self.font.render(text_to_show, True, color)
                    self.screen.blit(text_surf, (40, 100 + i * 40))
                    
                # Update the char_count for the next iteration
                # (+1 accounts for the invisible newline character between lines)
                char_count += len(line) + 1

if __name__ == "__main__":
    ValentineApp().run()