import pygame
import os
import time

pygame.init()

# Screen Setup 
screen_info = pygame.display.Info()
MAX_WIDTH = 1600
MAX_HEIGHT = 900
# Define the size of the *visible window*, not the entire game world
WIDTH = min(screen_info.current_w - 100, MAX_WIDTH)
HEIGHT = min(screen_info.current_h - 100, MAX_HEIGHT)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MazeQuest")

 
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)   # Now used for all static lethal hazards
BLUE = (0, 0, 255)  # No longer used for lethal water hazards
GREEN = (0, 255, 0) # No longer used for lethal slime hazards
YELLOW = (255, 255, 0) # Finish line
GRAY = (100, 100, 100) # Platform color
SKY_BLUE = (135, 206, 235) # Background sky
PURPLE = (128, 0, 128) # Moving hazard platform


menu_font = pygame.font.SysFont(None, 48)
game_font = pygame.font.SysFont(None, 36)
large_font = pygame.font.SysFont(None, 72) # For Game Over / Victory

#Game States
GAME_STATE_MENU = 0
GAME_STATE_SELECT_CHAR = 1
GAME_STATE_PLAYING = 2
GAME_STATE_LEVEL_COMPLETE = 3
GAME_STATE_GAME_OVER = 4 
GAME_STATE_VICTORY = 5 

#Game Physics Constants
GRAVITY = 0.5 
JUMP_STRENGTH = -15


def load_character_sprites(character_type_folder_name, skin, scale_factor=3):
    base_path = os.path.join(os.path.dirname(__file__), f"{character_type_folder_name}_{skin}")
    
    if not os.path.exists(base_path):
        print(f"Error: Character sprite folder not found at '{base_path}'. Make sure folder names are correct and directly in the script's directory.")
        default_sprite_size = int(24 * scale_factor) 
        default_sprite = pygame.Surface([default_sprite_size, default_sprite_size], pygame.SRCALPHA)
        placeholder_color = RED if character_type_folder_name == "Male" else BLUE 
        pygame.draw.circle(default_sprite, placeholder_color, (default_sprite_size // 2, default_sprite_size // 2), default_sprite_size // 2)
        return { "DownP": default_sprite }

    sprites = {}
    actions_map = {
        "Down": ["DownP", "DownR"],
        "Right": ["RightP", "RightR"],
        "Left": ["LeftP", "LeftR"],
        "Forward": ["ForwardP", "ForwardR"] 
    }

    default_sprite_size = int(12 * scale_factor) 
    default_sprite_for_frame = pygame.Surface([default_sprite_size, default_sprite_size], pygame.SRCALPHA)
    placeholder_color = RED if character_type_folder_name == "Male" else BLUE 
    pygame.draw.circle(default_sprite_for_frame, placeholder_color, (default_sprite_size // 2, default_sprite_size // 2), default_sprite_size // 2)

    for direction, frames in actions_map.items():
        for action_suffix in frames:
            image_path = os.path.join(base_path, f"{character_type_folder_name}_{skin}_{action_suffix}.png")

            try:
                image = pygame.image.load(image_path).convert_alpha()
                original_size = image.get_size()
                
                target_max_size = 40 
                new_width = int(original_size[0] * scale_factor)
                new_height = int(original_size[1] * scale_factor)

                if new_width > target_max_size or new_height > target_max_size:
                    scale_ratio = min(target_max_size / new_width, target_max_size / new_height)
                    new_width = int(new_width * scale_ratio)
                    new_height = int(new_height * scale_ratio)
                
                if new_width <= 0: new_width = 1
                if new_height <= 0: new_height = 1

                sprites[action_suffix] = pygame.transform.scale(image, (new_width, new_height))
            except FileNotFoundError:
                print(f"Warning: Sprite not found at {image_path}. Using placeholder for {action_suffix}.")
                sprites[action_suffix] = default_sprite_for_frame
            except pygame.error as e:
                print(f"Error loading image {image_path}: {e}. Using placeholder.")
                sprites[action_suffix] = default_sprite_for_frame
    
    if "DownP" not in sprites: 
        sprites["DownP"] = default_sprite_for_frame

    return sprites



class Camera:
    def __init__(self, width, height, level_width, level_height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height
        self.level_width = level_width 
        self.level_height = level_height 

    def apply(self, entity):
        return entity.rect.move(self.camera.topleft)

    def apply_rect(self, rect):
        return rect.move(self.camera.topleft)

    def update(self, target_rects):
        if not target_rects:
            return

        avg_x = sum(r.centerx for r in target_rects) // len(target_rects)
        avg_y = sum(r.centery for r in target_rects) // len(target_rects)

        x = -avg_x + int(self.width / 2)
        y = -avg_y + int(self.height / 2)

        x = min(0, x) 
        x = max(-(self.level_width - self.width), x) 
        y = min(0, y) 
        y = max(-(self.level_height - self.height), y) 

        self.camera = pygame.Rect(x, y, self.width, self.height)



class Tile(pygame.sprite.Sprite):
    def __init__(self, x, y, tile_size, color=BLACK, tile_type="platform"):
        super().__init__()
        self.image = pygame.Surface([tile_size, tile_size])
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y)) 
        self.tile_type = tile_type

    def draw(self, surface, camera):
        surface.blit(self.image, camera.apply(self))


class HazardTile(pygame.sprite.Sprite):
    def __init__(self, x, y, tile_size, color_ignored, hazard_type_ignored, height_ratio=0.4): # Увеличено до 0.4
        super().__init__()
        self.tile_size = tile_size
        self.hazard_height = int(tile_size * height_ratio)
        if self.hazard_height < 5: self.hazard_height = 5 

        self.image = pygame.Surface([tile_size, self.hazard_height])
        self.image.fill(RED) # FORCE ALL STATIC HAZARDS TO BE RED
        
        self.rect = self.image.get_rect(topleft=(x, y + tile_size - self.hazard_height))
        self.hazard_type = "lethal_static_hazard" # Generic lethal type

    def draw(self, surface, camera):
        surface.blit(self.image, camera.apply(self))


class MovingHazardPlatform(pygame.sprite.Sprite):
    def __init__(self, x, y, tile_size, color, move_range_x, speed, hazard_type="sticky_hazard"):
        super().__init__()
        self.tile_size = tile_size
        self.image = pygame.Surface([tile_size, tile_size // 2]) 
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y + tile_size // 2)) 

        self.hazard_type = hazard_type
        self.start_x = x
        self.end_x = x + move_range_x # The point it moves to
        self.current_speed = speed
        self.moving_right = True

    def update(self):
        if self.moving_right:
            self.rect.x += self.current_speed
            if self.rect.x >= self.end_x:
                self.rect.x = self.end_x
                self.moving_right = False
        else:
            self.rect.x -= self.current_speed
            if self.rect.x <= self.start_x:
                self.rect.x = self.start_x
                self.moving_right = True

    def draw(self, surface, camera):
        surface.blit(self.image, camera.apply(self))



class Character(pygame.sprite.Sprite):
    def __init__(self, character_actual_type, skin, start_x, start_y, tile_size, world_width, world_height):
        super().__init__()
        self.character_type_for_folder = character_actual_type 
        self.skin = skin
        self.sprites = load_character_sprites(character_actual_type, skin)
        
        self.elemental_type = "Fire" if character_actual_type == "Male" else "Water"

        self.image = self.sprites.get("DownP", pygame.Surface([int(tile_size * 0.8), int(tile_size * 0.8)], pygame.SRCALPHA))
        if self.image.get_width() == 0 or self.image.get_height() == 0: 
            self.image = pygame.Surface([int(tile_size * 0.8), int(tile_size * 0.8)], pygame.SRCALPHA)
            pygame.draw.circle(self.image, RED if self.elemental_type == "Fire" else BLUE, (int(tile_size*0.4), int(tile_size*0.4)), int(tile_size*0.4))

        self.rect = self.image.get_rect(topleft=(start_x, start_y)) # World coordinates
        self.start_pos = (start_x, start_y) 

        self.direction = "Down" 
        self.moving = False 
        self.speed = 5 

        self.y_velocity = 0
        self.on_ground = False
        self.jump_strength = JUMP_STRENGTH
        self.is_dead = False 

        self.world_width = world_width
        self.world_height = world_height


    def update_sprite(self):
        sprite_key = f"{self.direction}{'R' if self.moving else 'P'}"
        
        new_image = self.sprites.get(sprite_key, 
                                     self.sprites.get(f"{self.direction}P", 
                                                      self.sprites.get("DownP", 
                                                                       pygame.Surface([self.rect.width, self.rect.height], pygame.SRCALPHA))))

        old_center_x = self.rect.centerx
        old_bottom = self.rect.bottom
        self.image = new_image
        self.rect = self.image.get_rect(centerx=old_center_x, bottom=old_bottom)

    def move(self, keys, left_key, right_key, jump_key, platforms):
        dx = 0
        self.moving = False 

        if keys[left_key]:
            dx = -self.speed
            self.direction = "Left"
            self.moving = True
        elif keys[right_key]:
            dx = self.speed
            self.direction = "Right"
            self.moving = True

        if keys[jump_key] and self.on_ground:
            self.y_velocity = self.jump_strength
            self.on_ground = False
            self.direction = "Forward" 
            self.moving = False 

        self.y_velocity += GRAVITY
        if self.y_velocity > 10: 
            self.y_velocity = 10

        self.rect.x += dx
        self.handle_horizontal_collisions(platforms)

        self.rect.y += self.y_velocity
        self.on_ground = False 
        self.handle_vertical_collisions(platforms)

        # Keep player within world bounds
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > self.world_width:
            self.rect.right = self.world_width
        # If character falls below world_height , they die
        if self.rect.top > self.world_height + 50: 
             self.is_dead = True

        if dx == 0 and self.on_ground: 
              self.direction = "Down"

        self.update_sprite()

    def handle_horizontal_collisions(self, platforms):
        collided_platforms = pygame.sprite.spritecollide(self, platforms, False)
        for platform in collided_platforms:
            if self.rect.colliderect(platform.rect): 
                if self.rect.x < platform.rect.x: 
                    self.rect.right = platform.rect.left
                elif self.rect.x > platform.rect.x: 
                    self.rect.left = platform.rect.right

    def handle_vertical_collisions(self, platforms):
        collided_platforms = pygame.sprite.spritecollide(self, platforms, False)
        for platform in collided_platforms:
            if self.rect.colliderect(platform.rect): 
                if self.y_velocity > 0: 
                    self.rect.bottom = platform.rect.top
                    self.y_velocity = 0
                    self.on_ground = True
                elif self.y_velocity < 0: 
                    self.rect.top = platform.rect.bottom
                    self.y_velocity = 0 
        
        if self.y_velocity == 0 and not self.on_ground: 
            self.y_velocity = 1 

    def handle_hazards(self, static_hazards, moving_hazards): 
        for hazard in static_hazards:
            if self.rect.colliderect(hazard.rect):
                if self.rect.bottom >= hazard.rect.top + 5 and self.rect.top < hazard.rect.bottom: 
                    return True 
        
        for m_hazard in moving_hazards: 
            if self.rect.colliderect(m_hazard.rect):
                return True 
        return False

    def reset_position(self):
        self.rect.topleft = self.start_pos
        self.y_velocity = 0
        self.on_ground = False
        self.is_dead = False 



class Level:
    def __init__(self, level_map_data, BASE_TILE_SIZE=50, WORLD_SCALE_FACTOR=1.75):
        self.level_map_data = level_map_data
        self.base_tile_size = BASE_TILE_SIZE
        self.world_scale_factor = WORLD_SCALE_FACTOR

        self.map_width_tiles = max(len(row) for row in level_map_data)
        self.map_height_tiles = len(level_map_data)

        self.tile_size = int(self.base_tile_size * self.world_scale_factor)
        if self.tile_size == 0: self.tile_size = 1 

        self.world_width_pixels = self.map_width_tiles * self.tile_size
        self.world_height_pixels = self.map_height_tiles * self.tile_size

        self.platforms = pygame.sprite.Group() 
        self.hazards = pygame.sprite.Group() 
        self.moving_hazards = pygame.sprite.Group() 
        self.finish_line = None
        self.player1_start = None
        self.player2_start = None

        self._build_level()

    def _build_level(self):
        self.platforms.empty()
        self.hazards.empty()
        self.moving_hazards.empty() 
        self.finish_line = None
        self.player1_start = None
        self.player2_start = None

        for row_idx, row in enumerate(self.level_map_data):
            for col_idx, tile_char in enumerate(row):
                x = col_idx * self.tile_size
                y = row_idx * self.tile_size 

                if tile_char == '#': 
                    self.platforms.add(Tile(x, y, self.tile_size, GRAY, "platform"))
                elif tile_char in ['L', 'W', 'S']: 
                    
                    self.hazards.add(HazardTile(x, y, self.tile_size, RED, "lethal_static_hazard")) 
                elif tile_char == 'M': 
                    self.moving_hazards.add(MovingHazardPlatform(x, y, self.tile_size, PURPLE, move_range_x=self.tile_size * 2, speed=2))
                elif tile_char == '1': 
                    self.player1_start = (x, y) 
                elif tile_char == '2': 
                    self.player2_start = (x, y)
                elif tile_char == 'F': 
                    self.finish_line = Tile(x, y, self.tile_size, YELLOW, "finish")

        if not self.player1_start:
            print("WARNING: Player 1 start point ('1') not found in level map! Defaulting to (0, 0).")
            self.player1_start = (0, 0) 
        if not self.player2_start:
            print("WARNING: Player 2 start point ('2') not found in level map! Defaulting to near P1.")
            self.player2_start = (self.player1_start[0] + self.tile_size, self.player1_start[1]) 
        if not self.finish_line:
            print("WARNING: Finish point ('F') not found in level map! Defaulting to top-right.")
            self.finish_line = Tile(self.tile_size * (self.map_width_tiles - 1), 0, self.tile_size, YELLOW, "finish") 


    def draw(self, surface, camera):
        surface.fill(SKY_BLUE) 

        for p in self.platforms:
            p.draw(surface, camera)
        for h in self.hazards:
            h.draw(surface, camera)
        for mh in self.moving_hazards: 
            mh.draw(surface, camera)
        if self.finish_line:
            self.finish_line.draw(surface, camera)

    def update(self):
        self.moving_hazards.update() 

    def get_start_positions(self):
        return self.player1_start, self.player2_start
    
    def get_tile_size(self):
        return self.tile_size

    def get_world_dimensions(self):
        return self.world_width_pixels, self.world_height_pixels



class Menu:
    def __init__(self):
        self.mode = None

    def draw_main_menu(self):
        screen.fill(WHITE)
        text_solo = menu_font.render("1. Solo Mode", True, BLACK)
        text_coop = menu_font.render("2. Coop Mode", True, BLACK)
        
        screen.blit(text_solo, (WIDTH // 2 - text_solo.get_width() // 2, HEIGHT // 2 - 50))
        screen.blit(text_coop, (WIDTH // 2 - text_coop.get_width() // 2, HEIGHT // 2))
        
        pygame.display.flip()

    def select_mode(self):
        running = True
        while running:
            self.draw_main_menu()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.mode = "solo"
                        running = False
                    elif event.key == pygame.K_2:
                        self.mode = "coop"
                        running = False
        return self.mode

    def draw_skin_selection(self, character_skins_library, player_number, selected_skin_index=None):
        screen.fill(WHITE)
        text_title = menu_font.render(f"Player {player_number}: Select Skin", True, BLACK)
        screen.blit(text_title, (WIDTH // 2 - text_title.get_width() // 2, HEIGHT // 2 - 200))

        # Display male skins (1-4)
        male_skins_start_y = HEIGHT // 2 - 50
        text_male = game_font.render("Male (1-4):", True, BLACK)
        screen.blit(text_male, (WIDTH // 4 - text_male.get_width() // 2, male_skins_start_y - 40))

        for i in range(1, 5):
            slot_center_x = (WIDTH // 4 * (i - 1)) + (WIDTH // 8)
            
            display_sprite = None
            if str(i) in character_skins_library["Male"] and "DownP" in character_skins_library["Male"][str(i)]:
                display_sprite = character_skins_library["Male"][str(i)]["DownP"]
            
            if display_sprite:
                sprite_x = slot_center_x - display_sprite.get_width() // 2
                screen.blit(display_sprite, (sprite_x, male_skins_start_y))
                number_text = menu_font.render(str(i), True, BLACK)
                screen.blit(number_text, (slot_center_x - number_text.get_width() // 2, male_skins_start_y + display_sprite.get_height() + 10))
                if selected_skin_index == i:
                    pygame.draw.rect(screen, GREEN, (sprite_x - 5, male_skins_start_y - 5, display_sprite.get_width() + 10, display_sprite.get_height() + 10), 3) 
            else:
                pygame.draw.rect(screen, (150, 150, 150), (slot_center_x - 25, male_skins_start_y, 50, 50)) 
                number_text = menu_font.render(str(i), True, BLACK)
                screen.blit(number_text, (slot_center_x - number_text.get_width() // 2, male_skins_start_y + 60))

        # Display female skins (5-8)
        female_skins_start_y = HEIGHT // 2 + 100
        text_female = game_font.render("Female (5-8):", True, BLACK)
        screen.blit(text_female, (WIDTH // 4 - text_female.get_width() // 2, female_skins_start_y - 40))

        for i in range(1, 5):
            slot_center_x = (WIDTH // 4 * (i - 1)) + (WIDTH // 8)
            
            display_sprite = None
            if str(i) in character_skins_library["Femal"] and "DownP" in character_skins_library["Femal"][str(i)]:
                display_sprite = character_skins_library["Femal"][str(i)]["DownP"]
            
            if display_sprite:
                sprite_x = slot_center_x - display_sprite.get_width() // 2
                screen.blit(display_sprite, (sprite_x, female_skins_start_y))
                number_text = menu_font.render(str(i + 4), True, BLACK) 
                screen.blit(number_text, (slot_center_x - number_text.get_width() // 2, female_skins_start_y + display_sprite.get_height() + 10))
                if selected_skin_index == (i + 4):
                    pygame.draw.rect(screen, GREEN, (sprite_x - 5, female_skins_start_y - 5, display_sprite.get_width() + 10, display_sprite.get_height() + 10), 3)
            else:
                pygame.draw.rect(screen, (150, 150, 150), (slot_center_x - 25, female_skins_start_y, 50, 50))
                number_text = menu_font.render(str(i+4), True, BLACK)
                screen.blit(number_text, (slot_center_x - number_text.get_width() // 2, female_skins_start_y + 60))

        pygame.display.flip()

    def select_skin(self, character_skins_library, player_number):
        running = True
        selected_index = None
        while running:
            self.draw_skin_selection(character_skins_library, player_number, selected_index)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN: 
                    if pygame.K_1 <= event.key <= pygame.K_4:
                        selected_index = int(event.unicode)
                        if str(selected_index) in character_skins_library["Male"] and "DownP" in character_skins_library["Male"][str(selected_index)]:
                            return "Male", str(selected_index)
                        else:
                            print(f"Skin Male {selected_index} not fully loaded or invalid key. Please check sprite files.")
                    elif pygame.K_5 <= event.key <= pygame.K_8:
                        selected_index = int(event.unicode)
                        female_skin_num = str(selected_index - 4) 
                        if female_skin_num in character_skins_library["Femal"] and "DownP" in character_skins_library["Femal"][female_skin_num]:
                            return "Femal", female_skin_num 
                        else:
                            print(f"Skin Femal {female_skin_num} (selected as {selected_index}) not fully loaded or invalid key. Please check sprite files.")
        return None, None 



class Timer:
    def __init__(self):
        self.start_time = None
        self.elapsed_time = 0

    def start(self):
        self.start_time = time.time()
        self.elapsed_time = 0

    def stop(self):
        if self.start_time is not None:
            self.elapsed_time = time.time() - self.start_time
            self.start_time = None

    def get_elapsed_time(self):
        if self.start_time is not None:
            return time.time() - self.start_time
        return self.elapsed_time

    def format_time(self):
        return self.format_time_from_seconds(self.get_elapsed_time())

    @staticmethod
    def format_time_from_seconds(total_seconds):
        total_seconds = int(total_seconds)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02}:{seconds:02}"



class Game:
    def __init__(self):
        self.menu = Menu()
        self.game_state = GAME_STATE_MENU
        self.players = []
        self.mode = None
        self.player_skins = {"player1": None, "player2": None}
        self.player_times = {"player1": 0.0, "player2": 0.0} 
        self.retries_left = 3 

        self.character_sprites_library = {
            "Male": {str(i): load_character_sprites("Male", str(i)) for i in range(1, 5)},
            "Femal": {str(i): load_character_sprites("Femal", str(i)) for i in range(1, 5)} 
        }

        
        self.level_data = [
            "________________F__", # Finish 
            "_____##_______#####", 
            "___#_____###L__S___", 
            "#######____________", 
            "_____###M_____#####", # Movingplatform
            "####_______________",
            "_______#####_______", 
            "_____________L#____", 
            "_________________#_", 
            "#####LL#___####LL##",
            "1_________________2", 
            "###################"  
        ]
        
        self.current_level = Level(self.level_data) 
        world_width, world_height = self.current_level.get_world_dimensions()
        
        self.camera = Camera(WIDTH, HEIGHT, world_width, world_height)

        self.game_timer = Timer()
        self.clock = pygame.time.Clock()

    def handle_input(self, event):
        if event.type == pygame.QUIT:
            self.game_state = -1 

    def reset_players_to_start(self):
        """Resets all players to their starting positions and clears their 'dead' status."""
        
        start1_x, start1_y = self.current_level.get_start_positions()[0]
        self.players[0].rect.topleft = (start1_x, start1_y)
        self.players[0].y_velocity = 0
        self.players[0].on_ground = False
        self.players[0].is_dead = False

        if len(self.players) > 1:
            start2_x, start2_y = self.current_level.get_start_positions()[1]
            self.players[1].rect.topleft = (start2_x, start2_y)
            self.players[1].y_velocity = 0
            self.players[1].on_ground = False
            self.players[1].is_dead = False
        
        
        self.player_times["player1"] = 0.0
        self.player_times["player2"] = 0.0

    def reset_game(self):
        """Resets the entire game state for a new playthrough."""
        self.players = []
        self.mode = None
        self.player_skins = {"player1": None, "player2": None}
        self.player_times = {"player1": 0.0, "player2": 0.0}
        self.retries_left = 3
        self.game_timer.stop() 

        self.current_level = Level(self.level_data) 
        world_width, world_height = self.current_level.get_world_dimensions()
        self.camera = Camera(WIDTH, HEIGHT, world_width, world_height)


    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                self.handle_input(event)
                if self.game_state in [GAME_STATE_LEVEL_COMPLETE, GAME_STATE_GAME_OVER]:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_r: 
                            self.reset_game()
                            self.game_state = GAME_STATE_MENU 
                        elif event.key == pygame.K_q: 
                            running = False

            if self.game_state == GAME_STATE_MENU:
                self.mode = self.menu.select_mode()
                self.game_state = GAME_STATE_SELECT_CHAR

            elif self.game_state == GAME_STATE_SELECT_CHAR:
                char_type1, skin1 = self.menu.select_skin(self.character_sprites_library, 1)
                if char_type1 and skin1:
                    self.player_skins["player1"] = {"type": char_type1, "skin": skin1}
                    start1_x, start1_y = self.current_level.get_start_positions()[0]
                    
                    self.players.append(Character(char_type1, skin1, start1_x, start1_y, 
                                                    self.current_level.get_tile_size(), 
                                                    self.current_level.world_width_pixels, 
                                                    self.current_level.world_height_pixels))
                    self.players[0].start_pos = (start1_x, start1_y) 

                    if self.mode == "coop":
                        char_type2, skin2 = self.menu.select_skin(self.character_sprites_library, 2)
                        if char_type2 and skin2:
                            self.player_skins["player2"] = {"type": char_type2, "skin": skin2}
                            start2_x, start2_y = self.current_level.get_start_positions()[1]
                            self.players.append(Character(char_type2, skin2, start2_x, start2_y, 
                                                            self.current_level.get_tile_size(),
                                                            self.current_level.world_width_pixels, 
                                                            self.current_level.world_height_pixels))
                            self.players[1].start_pos = (start2_x, start2_y)
                        else:
                            self.players = [] 
                            self.player_skins = {"player1": None, "player2": None}
                            self.game_state = GAME_STATE_MENU
                            print("Player 2 skin selection failed or cancelled. Restarting game mode selection.")
                            continue 
                    
                    self.retries_left = 3 
                    self.game_state = GAME_STATE_PLAYING
                    self.game_timer.start() 
                else:
                    self.game_state = GAME_STATE_MENU
                    print("Player 1 skin selection failed or cancelled. Returning to main menu.")

            elif self.game_state == GAME_STATE_PLAYING:
                active_player_rects = [p.rect for p in self.players if not p.is_dead]
                self.camera.update(active_player_rects)

                self.current_level.update() 

                screen.fill(SKY_BLUE) 
                self.current_level.draw(screen, self.camera) 

                keys = pygame.key.get_pressed()
                
                a_player_hit_hazard_this_frame = False 

                # Player 1 Logic
                if len(self.players) > 0:
                    if not self.players[0].is_dead:
                        self.players[0].move(keys, pygame.K_a, pygame.K_d, pygame.K_w, self.current_level.platforms)
                        if self.players[0].handle_hazards(self.current_level.hazards, self.current_level.moving_hazards):
                            print(f"Player 1 ({self.players[0].elemental_type}) hit a lethal hazard!")
                            self.players[0].is_dead = True 
                            a_player_hit_hazard_this_frame = True 
                        
                        if self.current_level.finish_line and self.players[0].rect.colliderect(self.current_level.finish_line.rect) and self.player_times["player1"] == 0.0:
                            self.player_times["player1"] = self.game_timer.get_elapsed_time()
                            print(f"Player 1 finished in: {Timer.format_time_from_seconds(self.player_times['player1'])}")
                else:
                    self.game_state = GAME_STATE_MENU 

                # Player 2 Logic
                if len(self.players) > 1:
                    if not self.players[1].is_dead:
                        self.players[1].move(keys, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, self.current_level.platforms)
                        if self.players[1].handle_hazards(self.current_level.hazards, self.current_level.moving_hazards):
                            print(f"Player 2 ({self.players[1].elemental_type}) hit a lethal hazard!")
                            self.players[1].is_dead = True
                            a_player_hit_hazard_this_frame = True
                        
                        if self.current_level.finish_line and self.players[1].rect.colliderect(self.current_level.finish_line.rect) and self.player_times["player2"] == 0.0:
                            self.player_times["player2"] = self.game_timer.get_elapsed_time()
                            print(f"Player 2 finished in: {Timer.format_time_from_seconds(self.player_times['player2'])}")
                
                #Hazard Respawn Logic
                if a_player_hit_hazard_this_frame:
                    if self.retries_left > 0:
                        print(f"Respawning all players. Retries left: {self.retries_left}")
                        self.retries_left -= 1
                        self.reset_players_to_start() 
                        self.game_timer.start() 
                    else:
                        print("No retries left. Game Over.")
                        self.game_state = GAME_STATE_GAME_OVER
                        self.game_timer.stop() 
                
                # Check for level completion (all players reached finish line)
                all_finished = True
                if self.mode == "solo":
                    if self.player_times["player1"] == 0.0:
                        all_finished = False
                elif self.mode == "coop":
                    if self.player_times["player1"] == 0.0 or self.player_times["player2"] == 0.0 or self.players[0].is_dead or self.players[1].is_dead:
                        all_finished = False
                
                if all_finished:
                    self.game_timer.stop()
                    self.game_state = GAME_STATE_LEVEL_COMPLETE
                
                # Draw players 
                for player in self.players:
                    if not player.is_dead: 
                        screen.blit(player.image, self.camera.apply(player))

                # Display HUD 
                time_text = game_font.render(f"Time: {self.game_timer.format_time()}", True, BLACK)
                screen.blit(time_text, (10, 10))

                retries_text = game_font.render(f"Retries: {self.retries_left}", True, BLACK)
                screen.blit(retries_text, (10, 50))


                pygame.display.flip()
                self.clock.tick(60) 

            elif self.game_state == GAME_STATE_LEVEL_COMPLETE:
                screen.fill(SKY_BLUE) 
                victory_text = large_font.render("Level Completed!", True, BLACK)
                screen.blit(victory_text, (WIDTH // 2 - victory_text.get_width() // 2, HEIGHT // 2 - 150))

                if self.mode == "solo":
                    time_p1_formatted = Timer.format_time_from_seconds(self.player_times["player1"])
                    player1_time_text = game_font.render(f"Your Time: {time_p1_formatted}", True, BLACK)
                    screen.blit(player1_time_text, (WIDTH // 2 - player1_time_text.get_width() // 2, HEIGHT // 2 - 50))
                elif self.mode == "coop":
                    time_p1_formatted = Timer.format_time_from_seconds(self.player_times["player1"])
                    time_p2_formatted = Timer.format_time_from_seconds(self.player_times["player2"])
                    
                    player1_time_text = game_font.render(f"Player 1 Time: {time_p1_formatted}", True, BLACK)
                    player2_time_text = game_font.render(f"Player 2 Time: {time_p2_formatted}", True, BLACK)
                    
                    screen.blit(player1_time_text, (WIDTH // 2 - player1_time_text.get_width() // 2, HEIGHT // 2 - 50))
                    screen.blit(player2_time_text, (WIDTH // 2 - player2_time_text.get_width() // 2, HEIGHT // 2))

                instructions_text = game_font.render("Press 'R' to Restart or 'Q' to Quit", True, BLACK)
                screen.blit(instructions_text, (WIDTH // 2 - instructions_text.get_width() // 2, HEIGHT // 2 + 100))
                pygame.display.flip()

            elif self.game_state == GAME_STATE_GAME_OVER:
                screen.fill(BLACK) 
                game_over_text = large_font.render("GAME OVER", True, RED)
                screen.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, HEIGHT // 2 - 50))
                
                instructions_text = game_font.render("Press 'R' to Restart or 'Q' to Quit", True, WHITE)
                screen.blit(instructions_text, (WIDTH // 2 - instructions_text.get_width() // 2, HEIGHT // 2 + 50))
                pygame.display.flip()
            
            elif self.game_state == -1: 
                running = False

        pygame.quit()
        exit()

if __name__ == "__main__":
    game = Game()
    game.run()