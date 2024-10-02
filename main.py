import math
import os

import numpy as np
import pandas as pd
import pygame as pg
import time
from pathfinding import smooth_astar
# import screeninfo

pg.font.init()
small_font = pg.font.SysFont('arial', 20)
medium_font = pg.font.SysFont('arial', 30)
large_font = pg.font.SysFont('arial', 40)
white = (255, 255, 255)
black = (0, 0, 0)
klm_rgb = (0, 161, 228)


class Operation:
    def __init__(self, name, duration, delay):
        self.name = name
        self.duration = duration
        self.dependencies = []
        self.completed = False
        self.completion_time = None
        self.start_time = None
        self.time_left = duration
        self.locations = []
        self.delay = delay

    def reset(self):
        self.completed = False
        self.completion_time = None
        self.start_time = None
        self.time_left = self.duration

    def add_dependency(self, operation):
        self.dependencies.append(operation)

    def is_ready(self):
        return all(dep.completed for dep in self.dependencies)

    def __str__(self):
        # return f'Operation:{self.name}, Duration: {self.duration}, Dependencies: {self.dependencies}, Ready: {self.is_ready()}'
        return self.name

    def __repr__(self):
        return f'{self.name} Ops'


class Scheduler:
    def __init__(self, df):
        self.ops = {}
        for index, row in df.iterrows():  # for each operation:
            operation = Operation(row.iloc[0], row.iloc[1] * 60, row.iloc[11])
            for dep in row.iloc[2:7]:
                if pd.notna(dep):
                    operation.add_dependency(self.ops[dep])
            for i in range(2):
                if pd.notna(row.iloc[2 * i + 7]) and pd.notna(row.iloc[2 * i + 8]):
                    operation.locations.append((row.iloc[2 * i + 7], row.iloc[2 * i + 8]))
            self.ops[row.iloc[0]] = operation
        self.finished = False

    def reset(self):
        for operation in self.ops.values():
            self.finished = False
            operation.reset()

    def update(self, sim, duration):
        for operation in self.ops.values():
            if operation.is_ready() and not operation.completed:
                if operation.start_time is None:
                    operation.start_time = sim.timer
                operation.time_left -= duration
                if operation.time_left + operation.delay * 60 <= 0:
                    operation.completed = True
                    operation.completion_time = sim.timer
                    # print(f'{operation} operation completed at time {round(operation.completion_time)}!')
        if all(op.completed for op in self.ops.values()):
            self.finished = True


class Simulation:
    def __init__(self):
        pg.init()
        pg.display.set_caption("ApronSim")
        # monitors = screeninfo.get_monitors() # TODO: make it better for different monitor types
        self.screen = pg.display.set_mode((1920, 1080), pg.NOFRAME, pg.HWSURFACE, display=min(pg.display.get_num_displays() - 1, 1))

        self.images, self.rects = load_assets()
        current_df = pd.read_excel("data.xlsx")
        self.scheduler = Scheduler(current_df)
        self.timer = -self.scheduler.ops['Parking'].duration
        self.fps = 0
        self.speed = 1
        self.paused = False
        self.pause_menu = False
        self.running = True
        self.restart = False
        self.blit_paths = False
        self.blit_mesh = False
        self.blit_coord = False

        self.button_resume = Button("RESUME", (820, 280), (280, 50), self.button_resume_action)
        self.button_quit = Button("QUIT", (820, 730), (280, 50), self.button_quit_action)
        self.button_restart = Button("RESTART", (820, 360), (280, 50), self.button_restart_action)
        self.button_reset_delays = Button("Reset", (200, 95), (45, 20), self.button_reset_delays_action, font_size=24)

        self.delay_buttons = []
        for i, operation in enumerate(self.scheduler.ops.values()):
            self.delay_buttons.append(ButtonDelay("-", (200, 122 + i * 28), (20, 20), operation, font_size=20))
            self.delay_buttons.append(ButtonDelay("+", (225, 122 + i * 28), (20, 20), operation, font_size=20))
        self.buttons = [self.button_resume, self.button_quit, self.button_restart, self.button_reset_delays]
        self.buttons.extend(self.delay_buttons)

        mesh_df = pd.read_excel("Base_Mesh_4.xlsx", header=None)
        self.mesh = mesh_df.to_numpy()

        self.vehicles = []
        self.create_vehicles()

        self.mesh_surface = pg.Surface((1920, 1080), pg.SRCALPHA)
        for y, row in enumerate(self.mesh):
            if 19 < y < 128:
                for x, cell in enumerate(row):
                    rect_surface = pg.Surface((10, 10), pg.SRCALPHA)
                    if cell == 0:
                        rect_surface.fill(pg.Color(255, 100, 100, 100))
                    else:
                        rect_surface.fill(pg.Color(100, 255, 100, 100))
                    self.mesh_surface.blit(rect_surface, (x * 10, (y - 20) * 10))

    def draw(self):
        self.screen.fill('Black')
        self.screen.blit(self.images['apron'], self.rects['apron'])

        for vehicle in self.vehicles:
            vehicle.draw(self.screen)

        # Hydrant-truck rendering
        # if self.scheduler.ops['Refuel'].is_ready() and not self.scheduler.ops['Refuel'].completed:
        #     self.screen.blit(self.images['Hydrant_Truck'], (717, 515))

        # # LDL rendering
        # if self.scheduler.ops['Connect_LDL_Front'].is_ready() and not self.scheduler.ops['Remove_LDL_Front'].completed:
        #     self.screen.blit(self.images['LDL'], (711, 719))
        # if self.scheduler.ops['Connect_LDL_Rear'].is_ready() and not self.scheduler.ops['Remove_LDL_Rear'].completed:
        #     self.screen.blit(self.images['LDL'], (712, 283))

        # Tug rendering
        if self.scheduler.ops["Pushback"].is_ready():
            self.screen.blit(self.images['Tug'], (909, 869 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
                    self.timer - self.scheduler.ops["Pushback"].start_time)))
        elif self.scheduler.ops["Attatch_Tug"].is_ready():
            self.screen.blit(self.images['Tug'], (909, 869))

        # Aircraft rendering
        if not self.scheduler.ops["Parking"].completed:
            self.screen.blit(self.images['737s'], (513, min(17 - 1020 + 17 * (
                    self.timer + self.scheduler.ops['Parking'].duration), 17)))  # 17 pixels per second
        elif self.scheduler.ops["Pushback"].is_ready():
            self.screen.blit(self.images['737s'], (513, 17 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
                    self.timer - self.scheduler.ops["Pushback"].start_time)))
        else:
            self.screen.blit(self.images['737s'], (513, 17))

        # Bridge rendering
        self.screen.blit(self.images['Bridge_1'], (1330, 924))
        if self.scheduler.ops["Connect_Bridge"].start_time is None or self.scheduler.ops["Flight_Closure"].completed:
            self.screen.blit(self.images['Bridge_2'], (1233, 896))
        elif self.scheduler.ops["Connect_Bridge"].completed and self.scheduler.ops["Flight_Closure"].start_time is None:
            self.screen.blit(self.images['Bridge_2'], (987, 854))
        elif self.scheduler.ops["Flight_Closure"].start_time is not None:
            removing_bridge_time = self.timer - self.scheduler.ops["Flight_Closure"].start_time
            self.screen.blit(self.images['Bridge_2'], (
                min(987 + (((1233 - 987) / self.scheduler.ops["Flight_Closure"].duration) * removing_bridge_time),
                    1233),
                min(854 + (((896 - 854) / self.scheduler.ops["Flight_Closure"].duration) * removing_bridge_time), 896)))
        else:
            connecting_bridge_time = self.timer - self.scheduler.ops["Connect_Bridge"].start_time
            self.screen.blit(self.images['Bridge_2'], (
                max(1233 - (((1233 - 987) / self.scheduler.ops["Connect_Bridge"].duration) * connecting_bridge_time),
                    987),
                max(896 - (((896 - 854) / self.scheduler.ops["Connect_Bridge"].duration) * connecting_bridge_time),
                    854)))

        # Catering rendering
        if self.scheduler.ops['Catering_Front'].is_ready() and not self.scheduler.ops['Catering_Front'].completed:
            self.screen.blit(self.images['Catering'], (760, 870))

        if self.scheduler.ops['Catering_Rear'].is_ready() and not self.scheduler.ops['Catering_Rear'].completed:
            self.screen.blit(self.images['Catering'], (757, 196))

        rect_surface = pg.Surface((250, 1080), pg.SRCALPHA)
        rect_surface.fill(pg.Color(0, 0, 0, 150))
        self.screen.blit(rect_surface, (0, 0))

        # Operations list + red dots rendering
        operation_count = -1
        for i, operation in enumerate(self.scheduler.ops.values()):
            string = operation.name.replace('_', ' ')
            if operation.completed:
                colour = (100, 255, 100)
            elif operation.delay > 0:
                colour = (255, 100, 100)
            elif operation.is_ready():
                colour = (255, 255, 100)
            else:
                colour = white
            self.screen.blit(small_font.render(string, True, colour), (10, 120 + i * 28))

            # Delay
            self.screen.blit(small_font.render(str(operation.delay), True, colour), (175, 120 + i * 28))

            # Render operation on vop circle + name
            if operation.is_ready() and not operation.completed:
                operation_count += 1
                for op_loc_i in range(len(operation.locations)):
                    pg.draw.circle(self.screen, (255, 0, 0), operation.locations[op_loc_i], 10)
                    self.screen.blit(small_font.render(string, True, (0, 0, 0)),
                                     (operation.locations[op_loc_i][0], operation.locations[op_loc_i][1] + 10))

        # Delay buttons
        for button in self.delay_buttons:
            button.draw(self.screen)
        self.button_reset_delays.draw(self.screen)

        # Clock rendering - Minutes
        if int(self.timer / 60) < 10:
            if self.timer < 0:
                self.screen.blit(large_font.render(f'-0{int(self.timer / 60)}', True, white), (45, 10))
            else:
                self.screen.blit(large_font.render(f'0{int(self.timer / 60)}', True, white), (56, 10))
        else:
            self.screen.blit(large_font.render(f'{int(self.timer / 60)}', True, white), (56, 10))

        # Clock rendering - Seconds
        if self.timer < 0:
            if self.timer % 60 <= 51:
                self.screen.blit(large_font.render(f':{int(61 - self.timer % 60)}', True, white), (93, 10))
            else:
                self.screen.blit(large_font.render(f':0{int(61 - self.timer % 60)}', True, white), (93, 10))
        else:
            if self.timer % 60 < 10:
                self.screen.blit(large_font.render(f':0{int(self.timer % 60)}', True, white), (93, 10))
            else:
                self.screen.blit(large_font.render(f':{int(self.timer % 60)}', True, white), (93, 10))

        # Speed
        self.screen.blit(medium_font.render(f'Speed: {self.speed}x', True, white), (10, 60))

        # FPS Counter
        self.screen.blit(small_font.render(f'{int(self.fps)}', True, white), (1880, 10))

        # Pathfinding overlay
        if self.blit_paths:
            for vehicle in self.vehicles:
                for i, coord in enumerate(vehicle.path):
                    rect_surface = pg.Surface((10, 10), pg.SRCALPHA)
                    rect_surface.fill(pg.Color(100, 100, 255, 150))
                    self.screen.blit(rect_surface, (coord[0] - 5, coord[1] - 5))
                    if i < len(vehicle.path) - 1:
                        start = (vehicle.path[i][0], vehicle.path[i][1])
                        end = (vehicle.path[i + 1][0], vehicle.path[i + 1][1])
                        pg.draw.line(self.screen, black, start, end, width=2)

                    pg.draw.line(self.screen, (100, 100, 255), vehicle.location, vehicle.path[0], width=2)

        # Mesh overlay
        if self.blit_mesh:
            self.screen.blit(self.mesh_surface, (0, 0))

        # Coord debugging
        if self.blit_coord:
            coords = pg.mouse.get_pos()
            self.screen.blit(small_font.render(str(coords), True, white), (coords[0] + 5, coords[1] + 5))
            self.screen.blit(small_font.render(str((int(coords[1] / 10) + 20, int(coords[0] / 10))), True, white), (coords[0] + 5, coords[1] + 25))

        # Paused Pop-Up
        if self.paused and not self.pause_menu:
            pg.draw.rect(self.screen, black, pg.Rect(816, 0, 288, 60))
            self.screen.blit(large_font.render(f'Simulation Paused', True, white), (826, 10))

        # Pause Menu
        elif self.pause_menu or self.scheduler.finished:
            rect_surface = pg.Surface((320, 600), pg.SRCALPHA)
            rect_surface.fill(pg.Color(0, 0, 0, 150))
            self.screen.blit(rect_surface, (800, 200))

            if self.scheduler.finished:
                self.screen.blit(large_font.render(f'Simulation Finished', True, white),
                                 (960 - large_font.size('Simulation Finished')[0] / 2, 220))
            else:
                self.screen.blit(large_font.render(f'Simulation Paused', True, white),
                                 (960 - large_font.size('Simulation Paused')[0] / 2, 220))
                self.button_resume.draw(self.screen)

            self.button_restart.draw(self.screen)
            self.button_quit.draw(self.screen)

        pg.display.flip()

    def event_handler(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYUP:
                if event.key == 27:  # Escape
                    self.pause_menu = not self.pause_menu
                elif event.unicode == " " and not self.pause_menu:
                    self.paused = not self.paused
                elif event.unicode == "=":
                    self.speed = int(self.speed * 2)
                elif event.unicode == "-" and self.speed >= 2:
                    self.speed = int(self.speed / 2)
                elif event.unicode == "p":
                    self.blit_paths = not self.blit_paths
                elif event.unicode == "m":
                    self.blit_mesh = not self.blit_mesh
                elif event.unicode == "c":
                    self.blit_coord = not self.blit_coord
            elif event.type == pg.MOUSEBUTTONUP or event.type == pg.MOUSEBUTTONDOWN or event.type == pg.MOUSEMOTION:
                if event.type == pg.MOUSEMOTION:
                    if any([button.is_hovered for button in self.buttons]):
                        pg.mouse.set_cursor(pg.SYSTEM_CURSOR_HAND)
                    else:
                        pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)

                for button in self.delay_buttons:
                    button.handle_event(event)
                self.button_reset_delays.handle_event(event)

                if self.pause_menu or self.scheduler.finished:
                    self.button_quit.handle_event(event)
                    self.button_restart.handle_event(event)
                    self.button_resume.handle_event(event)

    def update(self, duration):
        time_passed = duration * self.speed
        self.timer += time_passed
        self.scheduler.update(self, time_passed)
        for vehicle in self.vehicles:
            vehicle.update(time_passed)

    def run(self):
        print("Running...")
        last_frame = time.perf_counter()

        while self.running:
            self.event_handler()
            self.draw()

            current_time = time.perf_counter()
            frame_duration = current_time - last_frame
            last_frame = current_time

            if not self.paused and not self.pause_menu and not self.scheduler.finished:
                self.update(frame_duration)

            self.fps = 1 / frame_duration

            if self.restart:
                print(f'\n Restarting...')
                self.reset()
        pg.quit()

    def reset(self):
        self.timer = -self.scheduler.ops['Parking'].duration
        self.paused = False
        self.pause_menu = False
        self.scheduler.reset()
        self.create_vehicles()
        self.restart = False

    def button_resume_action(self):
        if not self.scheduler.finished:
            self.pause_menu = False

    def button_restart_action(self):
        self.restart = True

    def button_quit_action(self):
        print('Quitting...!')
        self.running = False

    def button_reset_delays_action(self):
        for operation in self.scheduler.ops.values():
            operation.delay = 0

    def create_vehicles(self):
        self.vehicles = []
        # self.vehicles.append(
        #     Vehicle('Hydrant_Truck', self.scheduler.ops["Chocks_Front"], self.scheduler.ops["Refuel_Finalising"],
        #             (1300, 600), (535, 1370), (765, 362), 3, start_rotation=0))
        self.vehicles.append(
            Vehicle('Hydrant_Truck', self.scheduler.ops["Refuel_Prep"], self.scheduler.ops["Refuel_Finalising"],
                    (655, 1370), (535, 1370), (765, 365), 2, goal_rotation=90))
        self.vehicles.append(
            Vehicle('LDL', self.scheduler.ops["Connect_LDL_Rear"], self.scheduler.ops["Remove_LDL_Rear"],
                    (655, 1370), (535, 1370), (820, 325), 2))
        self.vehicles.append(
            Vehicle('LDL', self.scheduler.ops["Connect_LDL_Front"], self.scheduler.ops["Remove_LDL_Front"],
                    (655, 1370), (535, 1370), (820, 755), 2))


class Button:
    def __init__(self, text, pos, size, callback, color=(200, 200, 200), hover_color=klm_rgb, font_size=40):
        self.text = text
        self.pos = pos
        self.size = size
        self.color = color
        self.hover_color = hover_color
        self.callback = callback
        self.rect = pg.Rect(pos, size)
        self.font = pg.font.Font(None, font_size)
        self.is_hovered = False
        self.text_pos = (self.rect.x + size[0] / 2 - self.font.size(text)[0] / 2,
                         self.rect.y + size[1] / 2 - self.font.size(text)[1] / 2)

    def __repr__(self):
        return f'{self.text} Button'

    def draw(self, screen):
        # Change color on hover
        current_color = self.hover_color if self.is_hovered else self.color
        pg.draw.rect(screen, current_color, self.rect)

        # Render text
        text_surface = self.font.render(self.text, True, black)
        screen.blit(text_surface, (self.text_pos[0], self.text_pos[1]))

    def handle_event(self, event):
        if event.type == pg.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self.is_hovered:
            self.callback()
            self.is_hovered = False
            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)


class ButtonDelay(Button):
    def __init__(self, text, pos, size, op_id, color=(200, 200, 200), hover_color=klm_rgb, font_size=40):
        super().__init__(text, pos, size, callback=None, color=color, hover_color=hover_color, font_size=font_size)
        self.operation = op_id

    def handle_event(self, event):
        if event.type == pg.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self.is_hovered:
            if self.text == '+':
                self.operation.delay += 1
            else:
                self.operation.delay -= 1


class Vehicle:
    def __init__(self, name, start_op, end_op, start_loc, end_loc, goal_loc, max_speed, start_velocity=0,
                 start_rotation=-90, acceleration=1, goal_rotation=0):
        self.name = name
        self.start_operation = start_op
        self.end_operation = end_op
        self.location = [start_loc[0], start_loc[1]]
        self.end_loc = end_loc
        self.goal_loc = goal_loc
        self.speed = start_velocity
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.image = pg.image.load(f'assets\\{name}.png').convert_alpha()
        self.rect = self.image.get_rect()
        self.rotation = start_rotation
        self.goal_rotation = goal_rotation
        self.path = []
        self.arrived = False
        self.departed = False

        if name == 'Something':
            pass
        else:
            mesh_df = pd.read_excel("Base_Mesh_4.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()

    def draw(self, screen):
        rect_surface = pg.Surface((self.rect.width, self.rect.height), pg.SRCALPHA)
        rect_surface.blit(self.image, (0, 0))
        rotated_surface = pg.transform.rotate(rect_surface, -self.rotation)
        rotated_rect = rotated_surface.get_rect(center=(self.location[0], self.location[1]))
        screen.blit(rotated_surface, rotated_rect.topleft)

    def update(self, time_step):
        if self.start_operation.is_ready() and not self.arrived and self.path == []:
            self.path = smooth_astar(self.mesh, self.location, self.goal_loc, self.goal_rotation)
            print(f'path found for {self.name}: {self.path}')
        elif self.end_operation.completed and not self.departed and self.path == []:
            self.path = smooth_astar(self.mesh, self.location, self.end_loc, self.goal_rotation)
            print(f'path found for {self.name}: {self.path}')

        if self.path:
            dx = self.path[0][0] - self.location[0]
            dy = self.path[0][1] - self.location[1]
            distance = np.sqrt(dx ** 2 + dy ** 2)
            angle = np.rad2deg(np.arctan2(dy, dx))
            travel_distance = time_step * self.speed * 25  # 25 pixels per meter

            angle_diff = angle - self.rotation
            if angle_diff < -180:
                angle_diff += 360
            elif angle_diff > 180:
                angle_diff -= 360

            steering_factor = min(1, self.speed / 3) ** 2
            steering = np.clip(10 * angle_diff * steering_factor * time_step, -30 * time_step, 30 * time_step)
            self.rotation += steering

            dist_goal = np.sqrt((self.path[-1][0] - self.location[0]) ** 2 + (self.path[-1][1] - self.location[1]) ** 2)
            if dist_goal < 200:
                brake_speed = ((self.max_speed - 0.1) / 200) * dist_goal + 0.1
                self.speed = min(self.speed, brake_speed)
            else:
                if self.speed + self.acceleration * time_step < self.max_speed:
                    self.speed += self.acceleration * time_step
                else:
                    self.speed = self.max_speed

            tx = np.cos(np.deg2rad(self.rotation)) * travel_distance
            ty = np.sin(np.deg2rad(self.rotation)) * travel_distance
            self.location[0] += tx
            self.location[1] += ty

            if distance < 60 and len(self.path) > 1:  # TODO: make better, preferably when it "crosses" it, so also when it moves past it too far on the left or right
                self.path = self.path[1:]
            elif dist_goal < 5:
                self.path = []
                if not self.arrived:
                    self.location[0], self.location[1] = self.goal_loc[0], self.goal_loc[1]
                    self.rotation = self.goal_rotation
                    self.arrived = True
                else:
                    self.location[0], self.location[1] = self.end_loc[0], self.end_loc[1]
                    self.departed = True


def load_assets():
    images = {}
    rects = {}
    for file in os.listdir('assets'):
        if file.endswith('.png'):
            image = pg.image.load(f'assets\\{file}').convert_alpha()
            images[file[:-4]] = image
            rects[file[:-4]] = image.get_rect()
    return images, rects


def node_line(current_location, node_location, distance=60):
    x1, y1 = current_location
    x2, y2 = node_location
    if x1 == x2:
        perp_slope = 0
    elif y1 == y2:
        perp_slope = math.inf
    else:
        slope = (y2 - y1) / (x2 - x1)
        perp_slope = -1/slope

    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx ** 2 + dy ** 2)
    dx /= length
    dy /= length
    center = (node_location[0] - dx * distance, node_location[1] - dy * distance)

    return center, perp_slope


def has_crossed_line(current_location, node_location, line_center, line_slope):
    xv, yv = current_location
    xn, yn = node_location
    xl, yl = line_center

    line_distance = np.sqrt((xl - xn) ** 2 + (yl - yn) ** 2)

    b_perp_current = yv - (line_slope * xv)

    return


if __name__ == "__main__":
    main_sim = Simulation()
    main_sim.run()
