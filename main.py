"""
DotFront – Enhanced Edition
Maps, Heavy Units, Win/Lose Screens, Visual Improvements
"""

import pygame
import random
import math
import time
import sys

# -------------------- CONSTANTS --------------------
WIDTH, HEIGHT = 0, 0  # set after init
BUTTON_WIDTH = 300
BUTTON_HEIGHT = 80
BUTTON_SPACING = 20
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_BLUE = (100, 150, 255)
DARK_BLUE = (0, 50, 150)
GOLD = (255, 215, 0)
RED = (255, 50, 50)
GREEN = (34, 139, 34)      # forest green
SNOW = (240, 248, 255)      # snow white
DESERT = (237, 201, 175)    # sand

# Map types
MAP_PLAINS = 0
MAP_SNOW = 1
MAP_DESERT = 2

# Unit types
LIGHT = 0
HEAVY = 1

# -------------------- INIT PYGAME --------------------
pygame.init()
info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("DotFront")
clock = pygame.time.Clock()

# -------------------- HELPER FUNCTIONS --------------------
def draw_text(surface, text, font, color, x, y, center=True):
    text_surf = font.render(text, True, color)
    text_rect = text_surf.get_rect()
    if center:
        text_rect.center = (x, y)
    else:
        text_rect.topleft = (x, y)
    surface.blit(text_surf, text_rect)

def fade_transition(surface, duration=1.0, fade_out=True):
    fade_surf = pygame.Surface((WIDTH, HEIGHT))
    fade_surf.fill(BLACK)
    steps = int(duration * FPS)
    for alpha in range(0, 256, 256 // steps):
        fade_surf.set_alpha(alpha if fade_out else 255 - alpha)
        surface.blit(fade_surf, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)

# -------------------- UNIT CLASS --------------------
class Dot:
    def __init__(self, x, y, team, unit_type):
        self.x = float(x)
        self.y = float(y)
        self.team = team  # "player" or "enemy"
        self.type = unit_type  # LIGHT or HEAVY
        
        if self.type == LIGHT:
            self.hp = 10
            self.max_hp = 10
            self.damage = 1
            self.color = (0, 150, 255) if team == "player" else (255, 50, 50)
        else:  # HEAVY
            self.hp = 15
            self.max_hp = 15
            self.damage = 3
            # Different color shade for heavies
            if team == "player":
                self.color = (100, 200, 255)  # lighter blue
            else:
                self.color = (255, 100, 100)  # lighter red
        
        self.alive = True
        self.path = []
        self.last_combat = 0
        self.selected = False
        self.drag_offset = (0, 0)

    def move(self, speed):
        if not self.alive: return
        if time.time() - self.last_combat < 2.0:
            speed *= 0.3  # combat slowdown
        if self.path:
            target = self.path[0]
            dist = math.hypot(target[0] - self.x, target[1] - self.y)
            if dist < speed:
                self.x, self.y = target
                self.path.pop(0)
            else:
                self.x += (target[0] - self.x) / dist * speed
                self.y += (target[1] - self.y) / dist * speed

    def draw(self, surface, w2s_func):
        sx, sy = w2s_func(self.x, self.y)
        if not self.alive:
            pygame.draw.circle(surface, (30, 30, 30), (int(sx), int(sy)), 12)
            return
        
        # Selection ring
        if self.selected:
            pygame.draw.circle(surface, WHITE, (int(sx), int(sy)), 18, 3)
        
        # Path
        if self.path:
            pts = [(sx, sy)] + [w2s_func(p[0], p[1]) for p in self.path]
            if len(pts) > 1:
                pygame.draw.lines(surface, self.color, False, pts, 4)
        
        # Unit body
        pygame.draw.circle(surface, self.color, (int(sx), int(sy)), 12)
        
        # Heavy indicator: inner oval/circle
        if self.type == HEAVY:
            pygame.draw.circle(surface, BLACK, (int(sx), int(sy)), 6, 2)  # thick ring
            # Or draw a smaller filled circle with a different color
            # pygame.draw.circle(surface, (255,255,0), (int(sx), int(sy)), 4)
        
        # HP Bar
        hp_ratio = self.hp / self.max_hp
        pygame.draw.rect(surface, RED, (sx - 15, sy - 20, 30, 5))
        pygame.draw.rect(surface, GREEN, (sx - 15, sy - 20, 30 * hp_ratio, 5))

def interp(v1, v2):
    if v1 == v2: return 0.5
    denom = abs(v1) + abs(v2)
    return 0.5 if denom == 0 else abs(v1) / denom

# -------------------- GAME STATE --------------------
class GameStats:
    def __init__(self):
        self.player_kills = 0
        self.enemy_kills = 0
        self.start_time = time.time()
        self.end_time = None
        self.winner = None  # "player" or "enemy"

    def add_kill(self, team):
        if team == "player":
            self.enemy_kills += 1
        else:
            self.player_kills += 1

    def end_game(self, winner):
        self.winner = winner
        self.end_time = time.time()

    def get_duration(self):
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

# -------------------- MAIN GAME FUNCTION --------------------
def main_game(selected_map=MAP_PLAINS):
    """Main game loop – now with map, heavies, stats."""
    # Set background color based on map
    if selected_map == MAP_PLAINS:
        bg_color = GREEN
        ground_texture = "plains"
    elif selected_map == MAP_SNOW:
        bg_color = SNOW
        ground_texture = "snow"
    else:  # desert
        bg_color = DESERT
        ground_texture = "desert"

    # Camera
    cam_x, cam_y = WIDTH / 2, HEIGHT / 2
    zoom = 1.0

    def w2s(x, y):
        return (x - cam_x) * zoom + WIDTH/2, (y - cam_y) * zoom + HEIGHT/2

    def s2w(x, y):
        return (x - WIDTH/2) / zoom + cam_x, (y - HEIGHT/2) / zoom + cam_y

    # Create armies: 6 lights + 6 heavies per side
    dots = []
    # Player (blue side) – spawn on left
    for _ in range(6):
        dots.append(Dot(random.randint(50, 300), random.randint(100, HEIGHT-100), "player", LIGHT))
    for _ in range(6):
        dots.append(Dot(random.randint(50, 300), random.randint(100, HEIGHT-100), "player", HEAVY))
    # Enemy (red side) – spawn on right
    for _ in range(6):
        dots.append(Dot(random.randint(WIDTH-300, WIDTH-50), random.randint(100, HEIGHT-100), "enemy", LIGHT))
    for _ in range(6):
        dots.append(Dot(random.randint(WIDTH-300, WIDTH-50), random.randint(100, HEIGHT-100), "enemy", HEAVY))

    # Shuffle so positions are mixed
    random.shuffle(dots)

    WORLD_CELL_SIZE = 40
    global_ai_state = "defensive"
    last_ai_state_change = time.time()

    lassoing = False
    lasso_points = []
    dragged_dot = None
    lasso_mode = False

    fingers = {}
    initial_pinch_dist = 0
    initial_zoom = 1.0
    initial_cam = (0, 0)
    initial_pinch_center = (0, 0)

    middle_down = False
    last_mouse_pos = (0, 0)

    # In-game UI buttons
    button_font = pygame.font.SysFont(None, 48)
    select_button = pygame.Rect(WIDTH - 240, HEIGHT - 90, 110, 60)
    unselect_button = pygame.Rect(WIDTH - 120, HEIGHT - 90, 110, 60)
    exit_button = pygame.Rect(20, HEIGHT - 90, 110, 60)

    # Statistics
    stats = GameStats()

    # Game loop flag
    running = True
    game_over = False
    game_over_start_time = None

    while running:
        # Fill background
        screen.fill(bg_color)

        # Draw simple ground texture based on map
        if ground_texture == "plains":
            # Draw some faint grass patches
            for i in range(0, WIDTH, 50):
                for j in range(0, HEIGHT, 50):
                    if (i+j) % 100 == 0:
                        pygame.draw.circle(screen, (20,100,20), (i, j), 3)
        elif ground_texture == "snow":
            # Draw snowflakes
            for i in range(0, WIDTH, 60):
                for j in range(0, HEIGHT, 60):
                    if random.random() < 0.3:
                        pygame.draw.circle(screen, (255,255,255), (i, j), 2)
        else:  # desert
            # Draw sand ripples
            for i in range(0, WIDTH, 40):
                pygame.draw.line(screen, (210,180,140), (i,0), (i+20, HEIGHT), 1)

        current_time = time.time()

        # AI State Timer
        if current_time - last_ai_state_change > 60:
            last_ai_state_change = current_time
            global_ai_state = "offensive" if global_ai_state == "defensive" else "defensive"

        keys = pygame.key.get_pressed()

        # Camera movement
        if keys[pygame.K_w] or keys[pygame.K_UP]: cam_y -= 10 / zoom
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: cam_y += 10 / zoom
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: cam_x -= 10 / zoom
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: cam_x += 10 / zoom

        # Backspace unselect all
        if keys[pygame.K_BACKSPACE]:
            for d in dots: d.selected = False

        # ESC to return to menu (if game not over)
        if keys[pygame.K_ESCAPE] and not game_over:
            running = False

        # Event handling (similar to before, but we'll simplify for brevity – keep core)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            # Zoom
            elif event.type == pygame.MOUSEWHEEL:
                zoom = max(0.4, min(3.0, zoom + event.y * 0.1))
            # Touch events (simplified)
            elif event.type == pygame.FINGERDOWN:
                fingers[event.finger_id] = (event.x * WIDTH, event.y * HEIGHT)
            elif event.type == pygame.FINGERUP:
                fingers.pop(event.finger_id, None)
                if len(fingers) < 2: initial_pinch_dist = 0
            elif event.type == pygame.FINGERMOTION:
                fingers[event.finger_id] = (event.x * WIDTH, event.y * HEIGHT)
                if len(fingers) == 2:
                    f_vals = list(fingers.values())
                    dist = math.hypot(f_vals[0][0] - f_vals[1][0], f_vals[0][1] - f_vals[1][1])
                    cx = (f_vals[0][0] + f_vals[1][0]) / 2
                    cy = (f_vals[0][1] + f_vals[1][1]) / 2
                    if initial_pinch_dist == 0:
                        initial_pinch_dist = dist
                        initial_zoom = zoom
                        initial_pinch_center = (cx, cy)
                        initial_cam = (cam_x, cam_y)
                    else:
                        zoom = max(0.4, min(3.0, initial_zoom * (dist / initial_pinch_dist)))
                        cam_x = initial_cam[0] + (initial_pinch_center[0] - cx) / zoom
                        cam_y = initial_cam[1] + (initial_pinch_center[1] - cy) / zoom
            # Middle mouse pan
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                middle_down = True
                last_mouse_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                middle_down = False
            elif event.type == pygame.MOUSEMOTION and middle_down:
                dx = event.pos[0] - last_mouse_pos[0]
                dy = event.pos[1] - last_mouse_pos[1]
                cam_x -= dx / zoom
                cam_y -= dy / zoom
                last_mouse_pos = event.pos

            # Mouse clicks (only if game not over)
            if not game_over and len(fingers) < 2:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if exit_button.collidepoint(event.pos):
                        running = False
                    elif select_button.collidepoint(event.pos):
                        lasso_mode = True
                    elif unselect_button.collidepoint(event.pos):
                        for d in dots: d.selected = False
                    else:
                        wx, wy = s2w(event.pos[0], event.pos[1])
                        clicked_dot = None
                        for d in dots:
                            if d.alive and math.hypot(d.x - wx, d.y - wy) < 25 / zoom:
                                clicked_dot = d
                                break
                        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or lasso_mode:
                            lassoing = True
                            lasso_points = [(wx, wy)]
                        else:
                            if clicked_dot and clicked_dot.team == "player":
                                if not clicked_dot.selected:
                                    for d in dots: d.selected = False
                                    clicked_dot.selected = True
                                dragged_dot = clicked_dot
                                for d in dots:
                                    if d.selected:
                                        d.path = []
                                        d.drag_offset = (d.x - dragged_dot.x, d.y - dragged_dot.y)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if lassoing:
                        lassoing = False
                        if len(lasso_points) > 5:
                            min_x = min(p[0] for p in lasso_points)
                            max_x = max(p[0] for p in lasso_points)
                            min_y = min(p[1] for p in lasso_points)
                            max_y = max(p[1] for p in lasso_points)
                            for d in dots:
                                if d.team == "player" and d.alive and min_x <= d.x <= max_x and min_y <= d.y <= max_y:
                                    d.selected = True
                        lasso_points = []
                    dragged_dot = None
                    lasso_mode = False
                elif event.type == pygame.MOUSEMOTION:
                    wx, wy = s2w(event.pos[0], event.pos[1])
                    if lassoing:
                        if math.hypot(lasso_points[-1][0] - wx, lasso_points[-1][1] - wy) > 10 / zoom:
                            lasso_points.append((wx, wy))
                    elif dragged_dot:
                        if not dragged_dot.path or math.hypot(dragged_dot.path[-1][0] - wx, dragged_dot.path[-1][1] - wy) > 15:
                            for d in dots:
                                if d.selected and d != dragged_dot:
                                    d.path.append((wx + d.drag_offset[0], wy + d.drag_offset[1]))
                            dragged_dot.path.append((wx, wy))

        # COMBAT (only if game not over)
        if not game_over:
            for d in dots:
                if not d.alive: continue
                for other in dots:
                    if other.team != d.team and other.alive:
                        if math.hypot(d.x - other.x, d.y - other.y) < 24:
                            if current_time - d.last_combat >= 2.0 and current_time - other.last_combat >= 2.0:
                                # Decide who damages whom (original coin flip)
                                if random.choice([True, False]):
                                    # d damages other
                                    damage = d.damage
                                    other.hp -= damage
                                    if other.hp <= 0:
                                        other.alive = False
                                        other.selected = False
                                        stats.add_kill(other.team)
                                else:
                                    # other damages d
                                    damage = other.damage
                                    d.hp -= damage
                                    if d.hp <= 0:
                                        d.alive = False
                                        d.selected = False
                                        stats.add_kill(d.team)
                                d.last_combat = other.last_combat = current_time

            # Check win condition
            player_alive = any(d.alive and d.team == "player" for d in dots)
            enemy_alive = any(d.alive and d.team == "enemy" for d in dots)

            if not player_alive:
                stats.end_game("enemy")
                game_over = True
                game_over_start_time = time.time()
            elif not enemy_alive:
                stats.end_game("player")
                game_over = True
                game_over_start_time = time.time()

        # AI (only if game not over)
        if not game_over:
            players = [d for d in dots if d.team == "player" and d.alive]
            for e in dots:
                if e.team == "enemy" and e.alive:
                    if not e.path and random.random() < 0.02 and players:
                        if global_ai_state == "offensive":
                            closest = min(players, key=lambda p: math.hypot(p.x - e.x, p.y - e.y))
                            target = (closest.x + random.randint(-30,30), closest.y + random.randint(-30,30))
                        else:
                            if e.x < WIDTH/2 + 100:
                                target = (e.x + random.randint(150,400), e.y + random.randint(-150,150))
                            else:
                                target = (e.x + random.randint(-80,80), e.y + random.randint(-150,150))
                        steps = 10
                        dx = (target[0] - e.x) / steps
                        dy = (target[1] - e.y) / steps
                        for i in range(1, steps+1):
                            e.path.append((e.x + dx*i + random.randint(-20,20), e.y + dy*i + random.randint(-20,20)))

        # Territory line (unchanged, but uses w2s)
        left_world = cam_x - WIDTH/(2*zoom)
        right_world = cam_x + WIDTH/(2*zoom)
        top_world = cam_y - HEIGHT/(2*zoom)
        bottom_world = cam_y + HEIGHT/(2*zoom)

        start_i = int(math.floor(left_world / WORLD_CELL_SIZE)) - 1
        end_i = int(math.ceil(right_world / WORLD_CELL_SIZE)) + 1
        start_j = int(math.floor(top_world / WORLD_CELL_SIZE)) - 1
        end_j = int(math.ceil(bottom_world / WORLD_CELL_SIZE)) + 1

        cols = end_i - start_i + 1
        rows = end_j - start_j + 1

        grid = [[0.0 for _ in range(rows)] for _ in range(cols)]
        for i in range(cols):
            for j in range(rows):
                wx = (start_i + i) * WORLD_CELL_SIZE
                wy = (start_j + j) * WORLD_CELL_SIZE
                score = 0.0
                for d in dots:
                    if not d.alive: continue
                    dist_sq = max((d.x - wx)**2 + (d.y - wy)**2, 1)
                    if d.team == "player":
                        score -= 30000 / dist_sq
                    else:
                        score += 30000 / dist_sq
                grid[i][j] = score

        # Draw marching squares
        for i in range(cols - 1):
            for j in range(rows - 1):
                vTL = grid[i][j]
                vTR = grid[i+1][j]
                vBL = grid[i][j+1]
                vBR = grid[i+1][j+1]

                TL = 1 if vTL > 0 else 0
                TR = 1 if vTR > 0 else 0
                BL = 1 if vBL > 0 else 0
                BR = 1 if vBR > 0 else 0
                state = TL * 8 + TR * 4 + BR * 2 + BL * 1

                wx = (start_i + i) * WORLD_CELL_SIZE
                wy = (start_j + j) * WORLD_CELL_SIZE
                sx_TL, sy_TL = w2s(wx, wy)
                sx_TR, sy_TR = w2s(wx + WORLD_CELL_SIZE, wy)
                sx_BL, sy_BL = w2s(wx, wy + WORLD_CELL_SIZE)
                sx_BR, sy_BR = w2s(wx + WORLD_CELL_SIZE, wy + WORLD_CELL_SIZE)

                a = (sx_TL + (sx_TR - sx_TL) * interp(vTL, vTR), sy_TL)
                b = (sx_TR, sy_TR + (sy_BR - sy_TR) * interp(vTR, vBR))
                c = (sx_BL + (sx_BR - sx_BL) * interp(vBL, vBR), sy_BL)
                d_pt = (sx_TL, sy_TL + (sy_BL - sy_TL) * interp(vTL, vBL))

                line_color = (40, 40, 40)
                width = 8

                if state in (1, 14): pygame.draw.line(screen, line_color, c, d_pt, width)
                elif state in (2, 13): pygame.draw.line(screen, line_color, b, c, width)
                elif state in (3, 12): pygame.draw.line(screen, line_color, b, d_pt, width)
                elif state in (4, 11): pygame.draw.line(screen, line_color, a, b, width)
                elif state == 5:
                    pygame.draw.line(screen, line_color, a, d_pt, width)
                    pygame.draw.line(screen, line_color, b, c, width)
                elif state in (6, 9): pygame.draw.line(screen, line_color, a, c, width)
                elif state in (7, 8): pygame.draw.line(screen, line_color, a, d_pt, width)
                elif state == 10:
                    pygame.draw.line(screen, line_color, a, b, width)
                    pygame.draw.line(screen, line_color, c, d_pt, width)

        # Draw lasso
        if lassoing and len(lasso_points) > 1:
            screen_lasso = [w2s(p[0], p[1]) for p in lasso_points]
            pygame.draw.lines(screen, (0,200,0), False, screen_lasso, 3)

        # Move and draw dots
        for d in dots:
            d.move(2.0)
            d.draw(screen, w2s)

        # Draw UI buttons (only if game not over)
        if not game_over:
            pygame.draw.rect(screen, (70,130,180), select_button)
            pygame.draw.rect(screen, (70,130,180), unselect_button)
            pygame.draw.rect(screen, (70,130,180), exit_button)
            pygame.draw.rect(screen, WHITE, select_button, 3)
            pygame.draw.rect(screen, WHITE, unselect_button, 3)
            pygame.draw.rect(screen, WHITE, exit_button, 3)
            select_text = button_font.render("Select", True, WHITE)
            unselect_text = button_font.render("Unselect", True, WHITE)
            exit_text = button_font.render("Menu", True, WHITE)
            screen.blit(select_text, (select_button.x + 10, select_button.y + 10))
            screen.blit(unselect_text, (unselect_button.x + 10, unselect_button.y + 10))
            screen.blit(exit_text, (exit_button.x + 10, exit_button.y + 10))

        # AI state display
        if not game_over:
            state_text = button_font.render(f"AI: {global_ai_state.upper()}", True, BLACK)
            screen.blit(state_text, (20,20))

        # GAME OVER SCREEN
        if game_over:
            # Draw semi-transparent overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))

            # Determine winner message
            if stats.winner == "player":
                result_text = "VICTORY!"
                result_color = GOLD
            else:
                result_text = "DEFEAT..."
                result_color = RED

            # Draw stats
            title_font = pygame.font.Font(None, 120)
            stat_font = pygame.font.Font(None, 72)
            small_font = pygame.font.Font(None, 48)

            draw_text(screen, result_text, title_font, result_color, WIDTH//2, HEIGHT//2 - 150)
            draw_text(screen, f"Enemies Killed: {stats.player_kills}", stat_font, WHITE, WIDTH//2, HEIGHT//2 - 50)
            draw_text(screen, f"Your Losses: {stats.enemy_kills}", stat_font, WHITE, WIDTH//2, HEIGHT//2 + 20)
            duration = stats.get_duration()
            mins = int(duration // 60)
            secs = int(duration % 60)
            draw_text(screen, f"Time: {mins:02d}:{secs:02d}", stat_font, WHITE, WIDTH//2, HEIGHT//2 + 90)

            # Countdown
            elapsed = time.time() - game_over_start_time
            remaining = max(0, 5 - elapsed)
            draw_text(screen, f"Returning to menu in {int(remaining)}", small_font, GRAY, WIDTH//2, HEIGHT//2 + 180)

            if remaining <= 0:
                running = False  # exit game loop, return to menu

        pygame.display.flip()
        clock.tick(FPS)

# -------------------- MENU CLASS (Extended) --------------------
class Menu:
    def __init__(self):
        self.state = "main"  # main, options, credits, map_select, game
        self.buttons = []
        self.options = {
            "zoom_sensitivity": 0.1,
            "sound_volume": 0.5,
            "show_fps": False
        }
        self.selected_map = MAP_PLAINS  # default
        self.anim_offset = 0
        self.particles = []
        self.init_particles(100)
        self.font_large = pygame.font.Font(None, 120)
        self.font_medium = pygame.font.Font(None, 72)
        self.font_small = pygame.font.Font(None, 48)
        self.font_tiny = pygame.font.Font(None, 36)

        self.build_main_buttons()
        self.build_options_buttons()
        self.build_credits_buttons()
        self.build_map_buttons()

    def init_particles(self, count):
        for _ in range(count):
            self.particles.append({
                "x": random.randint(0, WIDTH),
                "y": random.randint(0, HEIGHT),
                "vx": random.uniform(-0.5, 0.5),
                "vy": random.uniform(-0.5, 0.5),
                "size": random.randint(2, 6),
                "color": random.choice([(100,100,255), (150,150,150), (255,255,200)])
            })

    def update_particles(self):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 0: p["x"] = WIDTH
            if p["x"] > WIDTH: p["x"] = 0
            if p["y"] < 0: p["y"] = HEIGHT
            if p["y"] > HEIGHT: p["y"] = 0

    def draw_particles(self, surface):
        for p in self.particles:
            pygame.draw.circle(surface, p["color"], (int(p["x"]), int(p["y"])), p["size"])

    def draw_background(self, surface):
        # Gradient sky
        for i in range(HEIGHT):
            color_value = int(20 + (i / HEIGHT) * 50)
            pygame.draw.line(surface, (color_value, color_value, color_value+30), (0, i), (WIDTH, i))
        self.update_particles()
        self.draw_particles(surface)

    def draw_button(self, surface, rect, text, font, color, hover=False):
        shadow_rect = rect.move(5, 5)
        pygame.draw.rect(surface, (0,0,0,100), shadow_rect, border_radius=15)
        if hover:
            pygame.draw.rect(surface, LIGHT_BLUE, rect, border_radius=15)
            pygame.draw.rect(surface, WHITE, rect, width=3, border_radius=15)
        else:
            pygame.draw.rect(surface, DARK_BLUE, rect, border_radius=15)
            pygame.draw.rect(surface, GRAY, rect, width=2, border_radius=15)
        draw_text(surface, text, font, WHITE if hover else GOLD, rect.centerx, rect.centery)

    def build_main_buttons(self):
        start_y = HEIGHT // 2 - (BUTTON_HEIGHT * 4 + BUTTON_SPACING * 3) // 2
        self.buttons = [
            {"rect": pygame.Rect(WIDTH//2 - BUTTON_WIDTH//2, start_y, BUTTON_WIDTH, BUTTON_HEIGHT),
             "text": "Start Game", "action": "map_select", "state": "main"},
            {"rect": pygame.Rect(WIDTH//2 - BUTTON_WIDTH//2, start_y + BUTTON_HEIGHT + BUTTON_SPACING, BUTTON_WIDTH, BUTTON_HEIGHT),
             "text": "Options", "action": "options", "state": "main"},
            {"rect": pygame.Rect(WIDTH//2 - BUTTON_WIDTH//2, start_y + 2*(BUTTON_HEIGHT + BUTTON_SPACING), BUTTON_WIDTH, BUTTON_HEIGHT),
             "text": "Credits", "action": "credits", "state": "main"},
            {"rect": pygame.Rect(WIDTH//2 - BUTTON_WIDTH//2, start_y + 3*(BUTTON_HEIGHT + BUTTON_SPACING), BUTTON_WIDTH, BUTTON_HEIGHT),
             "text": "Quit", "action": "quit", "state": "main"}
        ]

    def build_options_buttons(self):
        back_button = {"rect": pygame.Rect(50, HEIGHT - 100, 200, 60), "text": "Back", "action": "back", "state": "options"}
        self.options_buttons = [back_button]

    def build_credits_buttons(self):
        back_button = {"rect": pygame.Rect(50, HEIGHT - 100, 200, 60), "text": "Back", "action": "back", "state": "credits"}
        self.credits_buttons = [back_button]

    def build_map_buttons(self):
        # Three map buttons
        btn_w = 250
        btn_h = 250
        spacing = 50
        total_width = 3 * btn_w + 2 * spacing
        start_x = (WIDTH - total_width) // 2
        y = HEIGHT // 2 - btn_h // 2
        self.map_buttons = [
            {"rect": pygame.Rect(start_x, y, btn_w, btn_h), "map": MAP_PLAINS, "name": "Plains", "color": GREEN},
            {"rect": pygame.Rect(start_x + btn_w + spacing, y, btn_w, btn_h), "map": MAP_SNOW, "name": "Snowlands", "color": SNOW},
            {"rect": pygame.Rect(start_x + 2*(btn_w + spacing), y, btn_w, btn_h), "map": MAP_DESERT, "name": "Desert", "color": DESERT}
        ]
        back_btn = {"rect": pygame.Rect(50, HEIGHT - 100, 200, 60), "text": "Back", "action": "back", "state": "map_select"}
        self.map_back_button = back_btn

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.state == "main":
                for btn in self.buttons:
                    if btn["rect"].collidepoint(pos):
                        self.trigger_action(btn["action"])
            elif self.state == "options":
                for btn in self.options_buttons:
                    if btn["rect"].collidepoint(pos):
                        self.trigger_action(btn["action"])
                self.handle_options_input(pos)
            elif self.state == "credits":
                for btn in self.credits_buttons:
                    if btn["rect"].collidepoint(pos):
                        self.trigger_action(btn["action"])
            elif self.state == "map_select":
                if self.map_back_button["rect"].collidepoint(pos):
                    self.trigger_action("back")
                for btn in self.map_buttons:
                    if btn["rect"].collidepoint(pos):
                        self.selected_map = btn["map"]
                        self.trigger_action("start_game")
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == "main":
                    self.trigger_action("quit")
                else:
                    self.state = "main"

    def handle_options_input(self, pos):
        # Volume slider
        slider_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 40, 300, 20)
        if slider_rect.collidepoint(pos):
            rel_x = pos[0] - slider_rect.x
            self.options["sound_volume"] = max(0, min(1, rel_x / slider_rect.width))
        zoom_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 40, 300, 20)
        if zoom_rect.collidepoint(pos):
            rel_x = pos[0] - zoom_rect.x
            self.options["zoom_sensitivity"] = max(0.05, min(0.5, 0.05 + (rel_x / zoom_rect.width) * 0.45))

    def trigger_action(self, action):
        if action == "map_select":
            self.state = "map_select"
        elif action == "start_game":
            fade_transition(screen, 0.5, fade_out=True)
            self.state = "game"
        elif action == "options":
            self.state = "options"
        elif action == "credits":
            self.state = "credits"
        elif action == "back":
            self.state = "main"
        elif action == "quit":
            pygame.quit()
            sys.exit()

    def draw_main(self, surface):
        self.draw_background(surface)
        draw_text(surface, "DOTFRONT", self.font_large, GOLD, WIDTH//2, 150)
        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons:
            hover = btn["rect"].collidepoint(mouse_pos)
            self.draw_button(surface, btn["rect"], btn["text"], self.font_medium, DARK_BLUE, hover)

    def draw_options(self, surface):
        self.draw_background(surface)
        draw_text(surface, "OPTIONS", self.font_large, GOLD, WIDTH//2, 150)

        draw_text(surface, "Sound Volume", self.font_small, WHITE, WIDTH//2, HEIGHT//2 - 80)
        slider_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 40, 300, 20)
        pygame.draw.rect(surface, GRAY, slider_rect, border_radius=5)
        fill_width = int(300 * self.options["sound_volume"])
        fill_rect = pygame.Rect(slider_rect.x, slider_rect.y, fill_width, 20)
        pygame.draw.rect(surface, LIGHT_BLUE, fill_rect, border_radius=5)
        handle_x = slider_rect.x + fill_width
        pygame.draw.circle(surface, WHITE, (handle_x, slider_rect.centery), 12)

        draw_text(surface, "Zoom Sensitivity", self.font_small, WHITE, WIDTH//2, HEIGHT//2 + 20)
        zoom_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 40, 300, 20)
        pygame.draw.rect(surface, GRAY, zoom_rect, border_radius=5)
        zoom_val = (self.options["zoom_sensitivity"] - 0.05) / 0.45
        fill_width = int(300 * zoom_val)
        fill_rect = pygame.Rect(zoom_rect.x, zoom_rect.y, fill_width, 20)
        pygame.draw.rect(surface, LIGHT_BLUE, fill_rect, border_radius=5)
        handle_x = zoom_rect.x + fill_width
        pygame.draw.circle(surface, WHITE, (handle_x, zoom_rect.centery), 12)

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.options_buttons:
            hover = btn["rect"].collidepoint(mouse_pos)
            self.draw_button(surface, btn["rect"], btn["text"], self.font_small, DARK_BLUE, hover)

    def draw_credits(self, surface):
        self.draw_background(surface)
        draw_text(surface, "CREDITS", self.font_large, GOLD, WIDTH//2, 150)
        credits = [
            "Game Design: You",
            "Programming: You & AI",
            "Art: Procedurally Generated",
            "Music: None (yet)",
            "",
            "Inspired by War of Dots",
            "Thank you for playing!"
        ]
        y_offset = 300
        for line in credits:
            draw_text(surface, line, self.font_small, WHITE, WIDTH//2, y_offset)
            y_offset += 60

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.credits_buttons:
            hover = btn["rect"].collidepoint(mouse_pos)
            self.draw_button(surface, btn["rect"], btn["text"], self.font_small, DARK_BLUE, hover)

    def draw_map_select(self, surface):
        self.draw_background(surface)
        draw_text(surface, "SELECT MAP", self.font_large, GOLD, WIDTH//2, 150)

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.map_buttons:
            # Draw map preview
            pygame.draw.rect(surface, btn["color"], btn["rect"], border_radius=20)
            pygame.draw.rect(surface, WHITE, btn["rect"], width=4, border_radius=20)
            draw_text(surface, btn["name"], self.font_medium, BLACK, btn["rect"].centerx, btn["rect"].centery)

        # Back button
        hover = self.map_back_button["rect"].collidepoint(mouse_pos)
        self.draw_button(surface, self.map_back_button["rect"], self.map_back_button["text"], self.font_small, DARK_BLUE, hover)

    def run(self):
        running = True
        while running:
            dt = clock.tick(FPS) / 1000.0
            self.anim_offset += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_event(event)

            screen.fill(BLACK)

            if self.state == "main":
                self.draw_main(screen)
            elif self.state == "options":
                self.draw_options(screen)
            elif self.state == "credits":
                self.draw_credits(screen)
            elif self.state == "map_select":
                self.draw_map_select(screen)
            elif self.state == "game":
                # Launch game with selected map
                main_game(self.selected_map)
                # After game returns, go back to main menu
                self.state = "main"
                fade_transition(screen, 0.5, fade_out=False)

            pygame.display.flip()

        pygame.quit()
        sys.exit()

# -------------------- ENTRY POINT --------------------
if __name__ == "__main__":
    menu = Menu()
    menu.run()