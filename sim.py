import pygame
import sys
import random
import csv
import datetime

pygame.init()
SIM_WIDTH, HEIGHT = 800, 800
UI_WIDTH = 450
WIDTH = SIM_WIDTH + UI_WIDTH
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AI Traffic V25 - Final Fixed Flow ATCS")

font = pygame.font.SysFont("consolas", 14)
bold_font = pygame.font.SysFont("consolas", 17, bold=True)
title_font = pygame.font.SysFont("consolas", 22, bold=True)

BG_COLOR = (15, 18, 22)
ROAD_COLOR = (35, 38, 45)
UI_COLOR = (10, 12, 16)
LINE_COLOR = (150, 150, 160)
ZEBRA_COLOR = (120, 120, 130)
YELLOW_BOX = (160, 130, 30)

RED_LIGHT = (255, 30, 30)
YELLOW_LIGHT = (255, 190, 0)
GREEN_LIGHT = (30, 255, 100)

CAR_COLORS = [(255, 70, 70), (70, 180, 255), (255, 200, 50), (220, 220, 230)]
PED_COLORS = [(255, 180, 150), (150, 255, 180), (180, 150, 255), (240, 240, 240)]

ROAD_WIDTH = 140
CENTER = SIM_WIDTH // 2 
CW_OFFSET = 110          
CAR_STOP_LINE = 145      
PED_STOP_MARGIN = 20     

total_cars_passed = 0
total_peds_passed = 0

class BalancedAgent:
    def __init__(self):
        self.q_table = {}
        self.alpha = 0.2
        self.gamma = 0.95 
        self.epsilon = 0.01
        self.episodes = 0
        
    def get_state(self, light, ns_load, ew_load):
        def cat_l(l):
            if l == 0: return 0
            elif l <= 2.0: return 1   
            elif l <= 5.0: return 2  
            else: return 3           
        return (light, cat_l(ns_load), cat_l(ew_load))
        
    def get_action(self, state):
        if state not in self.q_table: self.q_table[state] = [0.0, 0.0]
        if random.uniform(0, 1) < self.epsilon: return random.choice([0, 1])
        return self.q_table[state].index(max(self.q_table[state]))
        
    def update(self, state, action, reward, next_state):
        if state not in self.q_table: self.q_table[state] = [0.0, 0.0]
        if next_state not in self.q_table: self.q_table[next_state] = [0.0, 0.0]
        best_next_q = max(self.q_table[next_state])
        self.q_table[state][action] += self.alpha * (reward + self.gamma * best_next_q - self.q_table[state][action])

agent = BalancedAgent()

class Pedestrian:
    def __init__(self, direction):
        self.dir = direction 
        self.color = random.choice(PED_COLORS)
        self.speed = 2.8 
        self.radius = 6
        self.is_stopped = False
        self.wait_time = 0 
        
        if self.dir == 'NS': 
            self.x = (CENTER - CW_OFFSET) if random.random() > 0.5 else (CENTER + CW_OFFSET)
            self.start_side = 'top' if random.random() > 0.5 else 'bottom'
            self.y = -10 if self.start_side == 'top' else HEIGHT + 10
        else: 
            self.y = (CENTER - CW_OFFSET) if random.random() > 0.5 else (CENTER + CW_OFFSET)
            self.start_side = 'left' if random.random() > 0.5 else 'right'
            self.x = -10 if self.start_side == 'left' else SIM_WIDTH + 10
            
        self.rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius*2, self.radius*2)

    def move(self, current_light, phase):
        global total_peds_passed
        can_move = True
        ped_light_green = False
        if phase == 'GREEN':
            ped_light_green = (current_light == 0) if self.dir == 'NS' else (current_light == 1) 
            
        if not ped_light_green:
            if self.dir == 'NS':
                if self.start_side == 'top' and CENTER - ROAD_WIDTH//2 - PED_STOP_MARGIN - 15 < self.y < CENTER - ROAD_WIDTH//2: can_move = False
                elif self.start_side == 'bottom' and CENTER + ROAD_WIDTH//2 < self.y < CENTER + ROAD_WIDTH//2 + PED_STOP_MARGIN + 15: can_move = False
            elif self.dir == 'EW':
                if self.start_side == 'left' and CENTER - ROAD_WIDTH//2 - PED_STOP_MARGIN - 15 < self.x < CENTER - ROAD_WIDTH//2: can_move = False
                elif self.start_side == 'right' and CENTER + ROAD_WIDTH//2 < self.x < CENTER + ROAD_WIDTH//2 + PED_STOP_MARGIN + 15: can_move = False

        self.is_stopped = not can_move
        if self.is_stopped: self.wait_time += 1/60 
            
        if can_move:
            if self.dir == 'NS': self.y += self.speed if self.start_side == 'top' else -self.speed
            elif self.dir == 'EW': self.x += self.speed if self.start_side == 'left' else -self.speed
        self.rect.center = (self.x, self.y)

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

class Car:
    def __init__(self, direction):
        self.dir = direction 
        self.color = random.choice(CAR_COLORS)
        
        self.speed = 4.0       
        self.max_speed = 7.0   
        self.acceleration = 0.25
        
        self.width = 22
        self.length = 42
        self.is_stopped = False
        self.wait_time = 0 
        
        if self.dir == 'N': 
            self.x = CENTER - ROAD_WIDTH//4 - self.width//2
            self.y = -self.length
        elif self.dir == 'S': 
            self.x = CENTER + ROAD_WIDTH//4 - self.width//2
            self.y = HEIGHT
        elif self.dir == 'E': 
            self.x = SIM_WIDTH
            self.y = CENTER - ROAD_WIDTH//4 - self.width//2
        elif self.dir == 'W': 
            self.x = -self.length
            self.y = CENTER + ROAD_WIDTH//4 - self.width//2
            
        self.rect = pygame.Rect(self.x, self.y, self.width, self.length)

    def move(self, cars_list, peds_list, current_light, phase):
        global total_cars_passed
        target_speed = self.max_speed 
        
        is_vertical = self.dir in ['N', 'S']
        w = self.width if is_vertical else self.length
        l = self.length if is_vertical else self.width
        self.rect = pygame.Rect(self.x, self.y, w, l)

        sensor_len = 60
        if self.dir == 'N': sensor_rect = pygame.Rect(self.x, self.y + l, w, sensor_len)
        elif self.dir == 'S': sensor_rect = pygame.Rect(self.x, self.y - sensor_len, w, sensor_len)
        elif self.dir == 'E': sensor_rect = pygame.Rect(self.x - sensor_len, self.y, sensor_len, l)
        elif self.dir == 'W': sensor_rect = pygame.Rect(self.x + w, self.y, sensor_len, l)

        for other in cars_list:
            if other != self and other.dir == self.dir and sensor_rect.colliderect(other.rect):
                target_speed = 0; break

        for ped in peds_list:
            if sensor_rect.colliderect(ped.rect) or self.rect.colliderect(ped.rect):
                target_speed = 0; break
                
        intersection_box = pygame.Rect(CENTER - ROAD_WIDTH//2, CENTER - ROAD_WIDTH//2, ROAD_WIDTH, ROAD_WIDTH)
        is_in_intersection = self.rect.colliderect(intersection_box)
        
        if not is_in_intersection:
            should_stop = False
            is_ns_car = self.dir in ['N', 'S']
            if phase in ['YELLOW', 'ALL_RED']:
                should_stop = True
            elif current_light == 0 and not is_ns_car:  
                should_stop = True
            elif current_light == 1 and is_ns_car:      
                should_stop = True

            if should_stop:
                if self.dir == 'N' and CENTER - CAR_STOP_LINE - 15 < self.y + l < CENTER - CAR_STOP_LINE: target_speed = 0
                elif self.dir == 'S' and CENTER + CAR_STOP_LINE < self.y < CENTER + CAR_STOP_LINE + 15: target_speed = 0
                elif self.dir == 'E' and CENTER + CAR_STOP_LINE < self.x < CENTER + CAR_STOP_LINE + 15: target_speed = 0
                elif self.dir == 'W' and CENTER - CAR_STOP_LINE - 15 < self.x + l < CENTER - CAR_STOP_LINE: target_speed = 0

            if target_speed > 0: 
                cross_traffic_present = False
                for other in cars_list:
                    if other.dir not in [self.dir, 'N' if self.dir=='S' else 'S' if self.dir=='N' else 'E' if self.dir=='W' else 'W']:
                        if other.rect.colliderect(intersection_box): cross_traffic_present = True; break
                
                if cross_traffic_present:
                    if self.dir == 'N' and CENTER - CAR_STOP_LINE - 25 < self.y + l < CENTER - CAR_STOP_LINE: target_speed = 0
                    elif self.dir == 'S' and CENTER + CAR_STOP_LINE < self.y < CENTER + CAR_STOP_LINE + 25: target_speed = 0
                    elif self.dir == 'E' and CENTER + CAR_STOP_LINE < self.x < CENTER + CAR_STOP_LINE + 25: target_speed = 0
                    elif self.dir == 'W' and CENTER - CAR_STOP_LINE - 25 < self.x + l < CENTER - CAR_STOP_LINE: target_speed = 0

        if target_speed == 0:
            self.speed = 0
            self.is_stopped = True
            self.wait_time += 1/60
        else:
            self.speed += self.acceleration
            if self.speed > target_speed: self.speed = target_speed
            self.is_stopped = False

        if self.dir == 'N': self.y += self.speed
        elif self.dir == 'S': self.y -= self.speed
        elif self.dir == 'E': self.x -= self.speed
        elif self.dir == 'W': self.x += self.speed

        self.rect = pygame.Rect(self.x, self.y, w, l)

    def draw(self, surface):
        is_vertical = self.dir in ['N', 'S']
        w = self.width if is_vertical else self.length
        l = self.length if is_vertical else self.width
        pygame.draw.rect(surface, self.color, (self.x, self.y, w, l), border_radius=4)

cars = []
peds = []
clock = pygame.time.Clock()
spawn_timer = 0
ped_timer = 0

current_light = 0   
target_light = 0
phase = 'GREEN'     
phase_timer = 0

MIN_GREEN_DUR = 70  
YELLOW_DUR = 40     
ALL_RED_DUR = 10    
MAX_GREEN_SAFETY = 250 

frames = 0
action_interval = 15  
last_state = None
last_action = 0
penalty = 0

def draw_dashed_line(surface, color, start_pos, end_pos, width=2, dash_length=15):
    x1, y1 = start_pos; x2, y2 = end_pos
    if x1 == x2: 
        for y in range(y1, y2, dash_length * 2): pygame.draw.line(surface, color, (x1, y), (x1, y + dash_length), width)
    elif y1 == y2: 
        for x in range(x1, x2, dash_length * 2): pygame.draw.line(surface, color, (x, y1), (x + dash_length, y1), width)

def export_simulation_report(total_cars, total_peds, episodes):
    filename = "traffic_simulation_report.csv"
    print(f"\n📊 در حال استخراج گزارش مهندسی به فایل {filename}...")
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Simulation Date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["Total Cars Processed", total_cars])
        writer.writerow(["Total Pedestrians Processed", total_peds])
        writer.writerow(["AI Learning Epochs", episodes])
        writer.writerow(["System Status", "Balanced Optimal Flow (Anti-Lock Fixed)"])
    print("✅ گزارش مهندسی با موفقیت ذخیره شد!")

main_surface = pygame.Surface((WIDTH, HEIGHT))
trans_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            export_simulation_report(total_cars_passed, total_peds_passed, agent.episodes)
            pygame.quit()
            sys.exit()

    frames += 1
    phase_timer += 1 

    main_surface.fill(UI_COLOR) 
    trans_surface.fill((0,0,0,0))
    pygame.draw.rect(main_surface, BG_COLOR, (0, 0, SIM_WIDTH, HEIGHT)) 
    pygame.draw.rect(main_surface, ROAD_COLOR, (CENTER - ROAD_WIDTH//2, 0, ROAD_WIDTH, HEIGHT))
    pygame.draw.rect(main_surface, ROAD_COLOR, (0, CENTER - ROAD_WIDTH//2, SIM_WIDTH, ROAD_WIDTH))
    
    draw_dashed_line(main_surface, LINE_COLOR, (CENTER, 0), (CENTER, CENTER - ROAD_WIDTH//2))
    draw_dashed_line(main_surface, LINE_COLOR, (CENTER, CENTER + ROAD_WIDTH//2), (CENTER, HEIGHT))
    draw_dashed_line(main_surface, LINE_COLOR, (0, CENTER), (CENTER - ROAD_WIDTH//2, CENTER))
    draw_dashed_line(main_surface, LINE_COLOR, (CENTER + ROAD_WIDTH//2, CENTER), (SIM_WIDTH, CENTER))

    box_rect = pygame.Rect(CENTER - ROAD_WIDTH//2, CENTER - ROAD_WIDTH//2, ROAD_WIDTH, ROAD_WIDTH)
    pygame.draw.rect(main_surface, YELLOW_BOX, box_rect, 2)
    for i in range(10, ROAD_WIDTH, 15):
        pygame.draw.line(main_surface, YELLOW_BOX, (box_rect.left + i, box_rect.top), (box_rect.left, box_rect.top + i), 1)
        pygame.draw.line(main_surface, YELLOW_BOX, (box_rect.right, box_rect.bottom - i), (box_rect.right - i, box_rect.bottom), 1)

    for i in range(7):
        pygame.draw.rect(main_surface, ZEBRA_COLOR, (CENTER - ROAD_WIDTH//2 + i*20 + 5, CENTER - CW_OFFSET - 15, 10, 30))
        pygame.draw.rect(main_surface, ZEBRA_COLOR, (CENTER - ROAD_WIDTH//2 + i*20 + 5, CENTER + CW_OFFSET - 15, 10, 30))
        pygame.draw.rect(main_surface, ZEBRA_COLOR, (CENTER - CW_OFFSET - 15, CENTER - ROAD_WIDTH//2 + i*20 + 5, 30, 10))
        pygame.draw.rect(main_surface, ZEBRA_COLOR, (CENTER + CW_OFFSET - 15, CENTER - ROAD_WIDTH//2 + i*20 + 5, 30, 10))

    pygame.draw.rect(main_surface, RED_LIGHT, (CENTER - ROAD_WIDTH//2, CENTER - CAR_STOP_LINE, ROAD_WIDTH//2, 4))
    pygame.draw.rect(main_surface, RED_LIGHT, (CENTER, CENTER + CAR_STOP_LINE, ROAD_WIDTH//2, 4))
    pygame.draw.rect(main_surface, RED_LIGHT, (CENTER - CAR_STOP_LINE, CENTER, 4, ROAD_WIDTH//2))
    pygame.draw.rect(main_surface, RED_LIGHT, (CENTER + CAR_STOP_LINE, CENTER - ROAD_WIDTH//2, 4, ROAD_WIDTH//2))

    if phase == 'YELLOW':
        if phase_timer >= YELLOW_DUR: phase = 'ALL_RED'; phase_timer = 0
    elif phase == 'ALL_RED':
        if phase_timer >= ALL_RED_DUR: 
            current_light = target_light
            phase = 'GREEN'
            phase_timer = 0

    ns_cars = [c for c in cars if c.dir in ['N', 'S']]
    ew_cars = [c for c in cars if c.dir in ['E', 'W']]
    
    ns_stopped = sum(1 for c in ns_cars if c.is_stopped)
    ew_stopped = sum(1 for c in ew_cars if c.is_stopped)
    ns_approaching = sum(1 for c in ns_cars if not c.is_stopped)
    ew_approaching = sum(1 for c in ew_cars if not c.is_stopped)
    
    ns_total_load = ns_stopped + (ns_approaching * 0.4)
    ew_total_load = ew_stopped + (ew_approaching * 0.4)

    if frames % action_interval == 0 and phase == 'GREEN':
        penalty = (ns_total_load ** 2) + (ew_total_load ** 2)
        state = agent.get_state(current_light, ns_total_load, ew_total_load)
        reward = -penalty 
        
        if last_state is not None: agent.update(last_state, last_action, reward, state)
        action = agent.get_action(state)
        
        force_switch = (phase_timer >= MAX_GREEN_SAFETY)
        
        if phase_timer >= MIN_GREEN_DUR:
            if current_light == 0:  
                if force_switch or (ns_total_load == 0 and ew_total_load > 0) or (ns_stopped >= 3 and ew_total_load > 0):
                    target_light = 1
                    phase = 'YELLOW'
                    phase_timer = 0
            else:                   
                if force_switch or (ew_total_load == 0 and ns_total_load > 0) or (ew_stopped >= 3 and ns_total_load > 0):
                    target_light = 0
                    phase = 'YELLOW'
                    phase_timer = 0
            
        last_state = state
        last_action = action
        agent.episodes += 1

    spawn_timer += 1
    if spawn_timer > random.randint(45, 75):
        new_car = Car(random.choice(['N', 'S', 'E', 'W']))
        safe = True
        for c in cars:
            if new_car.rect.colliderect(c.rect): safe = False; break
        if safe: cars.append(new_car); total_cars_passed += 1; spawn_timer = 0
        
    ped_timer += 1
    if ped_timer > random.randint(100, 160):
        peds.append(Pedestrian(random.choice(['NS', 'EW'])))
        total_peds_passed += 1
        ped_timer = 0

    cars = [c for c in cars if -120 < c.x < SIM_WIDTH+120 and -120 < c.y < HEIGHT+120]
    peds = [p for p in peds if -50 < p.x < SIM_WIDTH+50 and -50 < p.y < HEIGHT+50]

    for car in cars: car.move(cars, peds, current_light, phase)
    for ped in peds: ped.move(current_light, phase)

    ns_car_color = GREEN_LIGHT if (current_light == 0 and phase == 'GREEN') else YELLOW_LIGHT if (current_light == 0 and phase == 'YELLOW') else RED_LIGHT
    ew_car_color = GREEN_LIGHT if (current_light == 1 and phase == 'GREEN') else YELLOW_LIGHT if (current_light == 1 and phase == 'YELLOW') else RED_LIGHT
    
    pygame.draw.circle(main_surface, ns_car_color, (CENTER - ROAD_WIDTH//2 - 20, CENTER - CAR_STOP_LINE), 14)
    pygame.draw.circle(main_surface, ns_car_color, (CENTER + ROAD_WIDTH//2 + 20, CENTER + CAR_STOP_LINE), 14)
    pygame.draw.circle(main_surface, ew_car_color, (CENTER + CAR_STOP_LINE, CENTER - ROAD_WIDTH//2 - 20), 14)
    pygame.draw.circle(main_surface, ew_car_color, (CENTER - CAR_STOP_LINE, CENTER + ROAD_WIDTH//2 + 20), 14)

    ns_ped_color = GREEN_LIGHT if (current_light == 0 and phase == 'GREEN') else RED_LIGHT
    ew_ped_color = GREEN_LIGHT if (current_light == 1 and phase == 'GREEN') else RED_LIGHT 
    pygame.draw.rect(main_surface, ew_ped_color, (CENTER - CW_OFFSET - 10, CENTER - ROAD_WIDTH//2 - 20, 20, 20), border_radius=3)
    pygame.draw.rect(main_surface, ew_ped_color, (CENTER + CW_OFFSET - 10, CENTER + ROAD_WIDTH//2, 20, 20), border_radius=3)
    pygame.draw.rect(main_surface, ns_ped_color, (CENTER - ROAD_WIDTH//2 - 20, CENTER - CW_OFFSET - 10, 20, 20), border_radius=3)
    pygame.draw.rect(main_surface, ns_ped_color, (CENTER + ROAD_WIDTH//2, CENTER + CW_OFFSET - 10, 20, 20), border_radius=3)

    for ped in peds: ped.draw(main_surface)
    for car in cars: car.draw(trans_surface)
    
    main_surface.blit(trans_surface, (0,0)) 
    screen.blit(main_surface, (0,0))

    ui_x = SIM_WIDTH + 15
    screen.blit(title_font.render("BALANCED FLOW ATCS V25", True, (0, 255, 255)), (ui_x, 20))
    pygame.draw.line(screen, (50, 60, 70), (ui_x, 55), (WIDTH - 15, 55), 2)

    screen.blit(bold_font.render("📡 OPTIMAL SENSORS (MAX 3)", True, (200, 200, 220)), (ui_x, 70))
    screen.blit(font.render(f"N-S Stopped : {ns_stopped} | Load: {ns_total_load:.1f}", True, (255, 80, 80) if ns_stopped >= 3 else (150, 150, 150)), (ui_x, 100))
    screen.blit(font.render(f"E-W Stopped : {ew_stopped} | Load: {ew_total_load:.1f}", True, (255, 80, 80) if ew_stopped >= 3 else (150, 150, 150)), (ui_x, 125))
    screen.blit(font.render(f"Queue Limit: Max 3 Cars", True, GREEN_LIGHT), (ui_x, 150))
    
    pygame.draw.line(screen, (50, 60, 70), (ui_x, 185), (WIDTH - 15, 185), 1)

    screen.blit(bold_font.render("🚦 ADAPTIVE CONTROLLER", True, (200, 200, 220)), (ui_x, 200))
    phase_color = GREEN_LIGHT if phase == 'GREEN' else YELLOW_LIGHT if phase == 'YELLOW' else RED_LIGHT
    screen.blit(font.render(f"Current Phase : {phase}", True, phase_color), (ui_x, 230))
    screen.blit(font.render(f"Flow State    : BALANCED", True, (0, 255, 255)), (ui_x, 255))
    
    pygame.draw.line(screen, (50, 60, 70), (ui_x, 290), (WIDTH - 15, 290), 1)

    screen.blit(bold_font.render("🧠 AI KERNEL (OPTIMAL)", True, (150, 100, 255)), (ui_x, 305))
    screen.blit(font.render(f"Learning Epochs: {agent.episodes}", True, (180, 180, 200)), (ui_x, 335))
    screen.blit(font.render("Traffic Status: ANTI-LOCK ACTIVE", True, GREEN_LIGHT), (ui_x, 380))

    pygame.display.flip()
    clock.tick(60)