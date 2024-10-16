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
gray = (150, 150, 150)
black = (0, 0, 0)
klm_rgb = (0, 161, 228)
op_list_margin = 26


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
    def __init__(self, sim_type: str):
        self.ops = {}
        self.load_df(sim_type)
        self.finished = False
        self.previous = sim_type

    def reset(self, sim_type: str):
        self.finished = False
        if self.previous == sim_type:
            for operation in self.ops.values():
                self.finished = False
                operation.reset()
        else:
            self.load_df(sim_type)

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

    def load_df(self, sim_type):
        if sim_type.lower() == 'old':
            df = pd.read_excel("data_manual.xlsx")
        elif sim_type.lower() == 'new':
            df = pd.read_excel("data_auto.xlsx")
        else:
            raise ValueError(f'Type must be either "old" or "new"')

        self.ops = {}
        dep_count = 6
        for index, row in df.iterrows():  # for each operation:
            operation = Operation(row.iloc[0], row.iloc[1] * 60, round(row.iloc[dep_count + 6]))
            for dep in row.iloc[2:dep_count + 2]:
                if pd.notna(dep):
                    operation.add_dependency(self.ops[dep])
            for i in range(2):
                if pd.notna(row.iloc[2 * i + dep_count + 2]) and pd.notna(row.iloc[2 * i + dep_count + 3]):
                    operation.locations.append((row.iloc[2 * i + dep_count + 2], row.iloc[2 * i + dep_count + 3]))
            self.ops[row.iloc[0]] = operation


class Simulation:
    def __init__(self):
        pg.init()
        pg.display.set_caption("ApronSim")
        # monitors = screeninfo.get_monitors() # TODO: make it better for different monitor types
        self.screen = pg.display.set_mode((1920, 1080), pg.NOFRAME, pg.HWSURFACE, display=min(pg.display.get_num_displays() - 1, 1))

        self.images, self.rects = load_assets()
        self.scheduler = Scheduler('Old')
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
        self.new_sim = False
        self.last_frame = time.perf_counter()

        self.button_resume = Button("RESUME", (820, 320), (280, 50), self.button_resume_action)
        self.button_quit = Button("QUIT", (820, 730), (280, 50), self.button_quit_action)
        self.button_restart = Button("RESTART", (820, 400), (280, 50), self.button_restart_action)
        self.button_reset_delays = Button("Reset", (200, 95), (45, 20), self.button_reset_delays_action, font_size=24)
        self.button_sim_type = ButtonFlip("Old", "New", (900, 480), (120, 40), callback=self.button_sim_type_action, state=self.new_sim)

        self.delay_buttons = []
        for i, operation in enumerate(self.scheduler.ops.values()):
            self.delay_buttons.append(ButtonDelay("-", (200, 122 + i * op_list_margin), (20, 20), operation, font_size=20))
            self.delay_buttons.append(ButtonDelay("+", (225, 122 + i * op_list_margin), (20, 20), operation, font_size=20))
        self.buttons = [self.button_resume, self.button_quit, self.button_restart, self.button_reset_delays, self.button_sim_type]
        self.buttons.extend(self.delay_buttons)

        mesh_df = pd.read_excel("assets/Meshes/Base_Mesh_4.xlsx", header=None)
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

        # Cones & GPU
        if not self.new_sim:
            self.screen.blit(self.images['GPU'], (1110, 1000))
            if self.scheduler.ops['Place_Cones'].completed and not self.scheduler.ops['Remove_Cones'].completed:
                self.screen.blit(self.images['Cone'], (535, 455))
                self.screen.blit(self.images['Cone'], (1375, 455))
                self.screen.blit(self.images['Cone'], (835, 700))
                self.screen.blit(self.images['Cone'], (1075, 700))

        for vehicle in self.vehicles:
            vehicle.draw(self.screen)

        # Tug rendering
        if self.new_sim:
            if self.scheduler.ops["Pushback"].is_ready():
                self.screen.blit(self.images['Taxibot'], (909, 869 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
                        self.timer - self.scheduler.ops["Pushback"].start_time)))
            elif self.scheduler.ops["Attach_Tug"].is_ready():
                self.screen.blit(self.images['Taxibot'], (909, 869))
        else:
            if self.scheduler.ops["Pushback"].is_ready():
                self.screen.blit(self.images['Tug'], (909, 869 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
                        self.timer - self.scheduler.ops["Pushback"].start_time)))
            elif self.scheduler.ops["Attach_Tug"].is_ready():
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

        # # Catering rendering
        # if self.scheduler.ops['Catering_Front'].is_ready() and not self.scheduler.ops['Catering_Front'].completed:
        #     self.screen.blit(self.images['Catering'], (760, 870))
        #
        # if self.scheduler.ops['Catering_Rear'].is_ready() and not self.scheduler.ops['Catering_Rear'].completed:
        #     self.screen.blit(self.images['Catering'], (757, 196))

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
            self.screen.blit(small_font.render(string, True, colour), (10, 120 + i * op_list_margin))

            # Delay
            self.screen.blit(small_font.render(str(operation.delay), True, colour), (175, 120 + i * op_list_margin))

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
                if len(vehicle.path) > 0:
                    for i, coord in enumerate(vehicle.path):
                        rect_surface = pg.Surface((10, 10), pg.SRCALPHA)
                        rect_surface.fill(pg.Color(100, 100, 255, 150))
                        self.screen.blit(rect_surface, (coord[0] - 5, coord[1] - 5))
                        if i < len(vehicle.path) - 1:
                            start = (vehicle.path[i][0], vehicle.path[i][1])
                            end = (vehicle.path[i + 1][0], vehicle.path[i + 1][1])
                            pg.draw.line(self.screen, black, start, end, width=2)

                    pg.draw.line(self.screen, (100, 100, 255), vehicle.location, vehicle.path[0], width=2)
                    pg.draw.circle(self.screen, (0, 255, 255), vehicle.gate_center, 5)
                    pg.draw.line(self.screen, white, (vehicle.gate_center[0] - vehicle.gate_dx, vehicle.gate_center[1] - vehicle.gate_dy),
                                 (vehicle.gate_center[0] + vehicle.gate_dx, vehicle.gate_center[1] + vehicle.gate_dy), 2)

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
        elif self.speed > 32:
            rect_surface = pg.Surface((556, 60), pg.SRCALPHA)
            rect_surface.fill(pg.Color(0, 0, 0, 150))
            self.screen.blit(rect_surface, (682, 0))
            self.screen.blit(large_font.render(f'Warning: Skipping Vehicle Movement', True, white), (692, 10))

        # Pause Menu
        if self.pause_menu or self.scheduler.finished:
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
            self.button_sim_type.draw(self.screen)

        pg.display.flip()

    def event_handler(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYUP:
                if event.key == 27:  # Escape
                    if not self.pause_menu:
                        self.pause_menu = True
                    else:
                        self.button_resume_action()
                elif event.unicode == " " and not self.pause_menu:
                    self.paused = not self.paused
                elif (event.unicode == "=" or event.unicode == "+") and self.speed <= 512:
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
                    self.button_sim_type.handle_event(event)

    def update(self, duration):
        time_passed = duration * self.speed
        self.timer += time_passed
        self.scheduler.update(self, time_passed)
        for vehicle in self.vehicles:
            vehicle.update(time_passed, self)

    def run(self):
        print("Running...")
        self.last_frame = time.perf_counter()

        while self.running:
            self.event_handler()
            self.draw()

            current_time = time.perf_counter()
            frame_duration = current_time - self.last_frame
            self.last_frame = current_time

            if not self.paused and not self.pause_menu and not self.scheduler.finished:
                self.update(frame_duration)

            self.fps = 1 / frame_duration

            if self.restart:
                print(f'\n Restarting...')
                self.reset()
        pg.quit()

    def reset(self):
        if self.new_sim:
            self.scheduler.reset('new')
        else:
            self.scheduler.reset('old')
        self.timer = -self.scheduler.ops['Parking'].duration

        self.delay_buttons = []
        for i, operation in enumerate(self.scheduler.ops.values()):
            self.delay_buttons.append(ButtonDelay("-", (200, 122 + i * op_list_margin), (20, 20), operation, font_size=20))
            self.delay_buttons.append(ButtonDelay("+", (225, 122 + i * op_list_margin), (20, 20), operation, font_size=20))
        self.create_vehicles()

        self.paused = False
        self.pause_menu = False
        self.restart = False
        self.last_frame = time.perf_counter()

    def button_resume_action(self):
        if not self.scheduler.finished:
            self.pause_menu = False
        for button in self.buttons:
            button.is_hovered = False
            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)

    def button_restart_action(self):
        self.restart = True
        for button in self.buttons:
            button.is_hovered = False
            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)

    def button_quit_action(self):
        print('Quitting...!')
        self.running = False

    def button_reset_delays_action(self):
        for operation in self.scheduler.ops.values():
            operation.delay = 0

    def button_sim_type_action(self):
        self.new_sim = not self.new_sim
        self.button_restart_action()

    def create_vehicles(self):
        self.vehicles = []

        if self.new_sim:
            self.vehicles.append(
                Vehicle('Hydrant_Truck_auto', self.scheduler.ops["Refuel_Prep"], self.scheduler.ops["Refuel_Finalising"],
                        (655, 1370), (535, 1370), [(725, 535)], max_speed=2, goal_rotation=90))
            self.vehicles.append(
                Vehicle('LDL_auto', self.scheduler.ops["Connect_LDL_Rear"], self.scheduler.ops["Remove_LDL_Rear"],
                        (655, 1370), (535, 1370), [(815, 325)], max_speed=2, goal_rotation=0))
            self.vehicles.append(
                Vehicle('LDL_auto', self.scheduler.ops["Connect_LDL_Front"], self.scheduler.ops["Remove_LDL_Front"],
                        (655, 1370), (535, 1370), [(815, 755)], max_speed=2, goal_rotation=0))
            self.vehicles.append(
                Vehicle('Catering_auto', self.scheduler.ops["Catering_Rear"], self.scheduler.ops["Catering_Rear"],
                        (655, 1370), (535, 1370), [(837, 227)], max_speed=2, goal_rotation=5))
            self.vehicles.append(
                Vehicle('Catering_auto', self.scheduler.ops["Catering_Front"], self.scheduler.ops["Catering_Front"],
                        (655, 1370), (535, 1370), [(842, 919)], max_speed=2, goal_rotation=-8))
            self.vehicles.append(
                Vehicle('Spot', self.scheduler.ops["Technical_Inspection"], self.scheduler.ops["Technical_Inspection"],
                        (1485, 735), (1485, 735), [(1155, 635), (1065, 405), (1125, 145), (855, 145), (855, 405), (755, 635), (865, 985)],
                        max_speed=0.5, goal_rotation=None, straighten=0, waiting_times=[140, 140, 140, 140, 140, 140, 140]))
        else:
            self.vehicles.append(
                Vehicle('Hydrant_Truck', self.scheduler.ops["Refuel_Prep"], self.scheduler.ops["Refuel_Finalising"],
                        (655, 1370), (535, 1370), [(725, 535)], max_speed=2, goal_rotation=90))
            self.vehicles.append(
                Vehicle('LDL', self.scheduler.ops["Connect_LDL_Rear"], self.scheduler.ops["Remove_LDL_Rear"],
                        (655, 1370), (535, 1370), [(815, 325)], max_speed=2, goal_rotation=0))
            self.vehicles.append(
                Vehicle('LDL', self.scheduler.ops["Connect_LDL_Front"], self.scheduler.ops["Remove_LDL_Front"],
                        (655, 1370), (535, 1370), [(815, 755)], max_speed=2, goal_rotation=0))
            self.vehicles.append(
                Vehicle('Catering', self.scheduler.ops["Catering_Rear"], self.scheduler.ops["Catering_Rear"],
                        (655, 1370), (535, 1370), [(837, 227)], max_speed=2, goal_rotation=5))
            self.vehicles.append(
                Vehicle('Catering', self.scheduler.ops["Catering_Front"], self.scheduler.ops["Catering_Front"],
                        (655, 1370), (535, 1370), [(842, 919)], max_speed=2, goal_rotation=-8))
            self.vehicles.append(
                Vehicle('Lavatory', self.scheduler.ops["Toilet_Service"], self.scheduler.ops["Toilet_Service"],
                        (655, 1370), (535, 1370), [(1055, 255)], max_speed=2, goal_rotation=180))
            self.vehicles.append(
                Vehicle('Water', self.scheduler.ops["Water_Service"], self.scheduler.ops["Water_Service"],
                        (655, 1370), (535, 1370), [(1055, 375)], max_speed=2, goal_rotation=180))


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


class ButtonDelay(Button):
    def __init__(self, text, pos, size, op_id, color=(200, 200, 200), hover_color=klm_rgb, font_size=40):
        super().__init__(text, pos, size, callback=None, color=color, hover_color=hover_color, font_size=font_size)
        self.operation = op_id

    def handle_event(self, event):
        if event.type == pg.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self.is_hovered:
            keys = pg.key.get_pressed()
            change = 10 if keys[pg.K_LCTRL] or keys[pg.K_RCTRL] else 1
            if self.text == '+':
                self.operation.delay += change
            else:
                self.operation.delay -= change


class ButtonFlip:
    def __init__(self, text1, text2, pos, size, callback, state, font_size=40):
        self.pos = pos
        self.size = size
        self.callback = callback
        self.rect = pg.Rect(pos, size)
        self.font = pg.font.Font(None, font_size)
        self.is_hovered = False

        self.state = state
        self.flip_y = self.rect.y + self.rect.height / 2

        self.circle_radius = self.rect.height / 2
        self.circle_radius_small = self.circle_radius - 0.1 * self.rect.height
        self.flip_circle_1 = (self.rect.x + self.circle_radius, self.flip_y)
        self.flip_circle_2 = (self.rect.x - self.circle_radius + self.rect.width, self.flip_y)
        self.flip_rect = pg.Rect(self.rect.x + self.circle_radius, self.flip_y - self.rect.height / 2, self.rect.width - 2 * self.circle_radius, self.rect.height)

        self.text_surface_1 = self.font.render(text1, True, white)
        self.text_surface_2 = self.font.render(text2, True, white)

        self.text_pos_1 = (self.rect.x - self.font.size(text1)[0] - 10, self.flip_y - self.font.size(text1)[1] / 2)
        self.text_pos_2 = (self.rect.x + self.rect.width + 10, self.flip_y - self.font.size(text1)[1] / 2)

    def draw(self, screen):
        # Render text
        screen.blit(self.text_surface_1, (self.text_pos_1[0], self.text_pos_1[1]))
        screen.blit(self.text_surface_2, (self.text_pos_2[0], self.text_pos_2[1]))

        if self.state:
            flip_color = klm_rgb
            flip_loc = self.flip_circle_2
        else:
            flip_color = gray
            flip_loc = self.flip_circle_1

        pg.draw.circle(screen, flip_color, self.flip_circle_1, self.circle_radius)
        pg.draw.circle(screen, flip_color, self.flip_circle_2, self.circle_radius)
        pg.draw.rect(screen, flip_color, self.flip_rect)
        pg.draw.circle(screen, white, flip_loc, self.circle_radius_small)

    def handle_event(self, event):
        if event.type == pg.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self.is_hovered:
            self.callback()
            self.state = not self.state


class Vehicle:
    def __init__(self, name, start_op, end_op, start_loc, end_loc, goal_locs, goal_rotation, max_speed, start_velocity=0,
                 start_rotation=-90, acceleration=1, straighten=20, waiting_times=None):
        self.name = name
        self.start_operation = start_op
        self.end_operation = end_op
        self.location = [start_loc[0], start_loc[1]]
        self.end_loc = end_loc
        self.goal_locs = goal_locs
        self.speed = start_velocity
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.image = pg.image.load(f'assets\\{name}.png').convert_alpha()
        self.rect = self.image.get_rect()
        self.rotation = start_rotation
        self.goal_rotation = goal_rotation
        self.straighten = straighten
        self.waiting_times = waiting_times
        if self.waiting_times is None:
            self.waiting_times = [0]
        self.wait_time = self.waiting_times[0]

        self.path = []
        self.arrived = False
        self.departed = False
        self.gate_center = None
        self.gate_slope = None
        self.gate_dx = None
        self.gate_dy = None
        self.gate_b = None
        self.upwards = None
        self.rightwards = None
        self.goals_completed = 0

        if name in ['Hydrant_Truck', 'Hydrant_Truck_auto']:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Refuel_1.xlsx", header=None)
            self.mesh_1 = mesh_df.to_numpy()
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Refuel_2.xlsx", header=None)
            self.mesh_2 = mesh_df.to_numpy()
        elif name in ['Spot']:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Inspection.xlsx", header=None)
            self.mesh_1 = mesh_df.to_numpy()
            self.mesh_2 = self.mesh_1
        else:
            mesh_df = pd.read_excel("assets/Meshes/Base_Mesh_4.xlsx", header=None)
            self.mesh_1 = mesh_df.to_numpy()
            self.mesh_2 = self.mesh_1

    def draw(self, screen):
        rect_surface = pg.Surface((self.rect.width, self.rect.height), pg.SRCALPHA)
        rect_surface.blit(self.image, (0, 0))
        rotated_surface = pg.transform.rotate(rect_surface, -self.rotation)
        rotated_rect = rotated_surface.get_rect(center=self.location)
        screen.blit(rotated_surface, rotated_rect.topleft)

    def update(self, time_step, simulation):
        if self.path:
            if simulation.speed <= 32:
                dx = self.path[0][0] - self.location[0]
                dy = self.path[0][1] - self.location[1]
                angle = np.rad2deg(np.arctan2(dy, dx))
                travel_distance = time_step * self.speed * 25  # 25 pixels per meter

                backwards = False
                angle_diff = angle - self.rotation
                if angle_diff < -180:
                    angle_diff += 360
                elif angle_diff > 180:
                    angle_diff -= 360
                if abs(angle_diff) > 160:
                    backwards = True
                    angle_diff = 0

                # Steering
                if self.name == 'Spot':
                    steering_factor = 1
                else:
                    steering_factor = min(1.0, self.speed / 3) ** 2
                steering = np.clip(10 * angle_diff * steering_factor * time_step, -30 * time_step, 30 * time_step)
                self.rotation += steering

                # Accelerating + Braking
                dist_goal = np.sqrt((self.path[-1][0] - self.location[0]) ** 2 + (self.path[-1][1] - self.location[1]) ** 2)
                if dist_goal < 200:
                    brake_speed = ((self.max_speed - 0.1) / 200) * dist_goal + 0.1
                    self.speed = min(self.speed, brake_speed)
                else:
                    if backwards:
                        if self.speed - self.acceleration * time_step > -self.max_speed / 2:
                            self.speed -= self.acceleration * time_step
                        else:
                            self.speed = -self.max_speed
                    else:
                        if self.speed + self.acceleration * time_step < self.max_speed:
                            self.speed += self.acceleration * time_step
                        else:
                            self.speed = self.max_speed

                # Displacement
                tx = np.cos(np.deg2rad(self.rotation)) * travel_distance
                ty = np.sin(np.deg2rad(self.rotation)) * travel_distance
                self.location[0] += tx
                self.location[1] += ty

                # Gate crossing
                crossed_gate = self.has_crossed_gate()
                if crossed_gate and len(self.path) > 1:
                    self.path = self.path[1:]
                    if len(self.path) == 1:
                        self.create_gate(0)
                    elif not self.arrived and len(self.path) <= self.straighten + 1:
                        self.create_gate(min(80, len(self.path) * 7))
                    elif self.name in ['Spot']:
                        self.create_gate(10)
                    else:
                        self.create_gate()
                elif crossed_gate:
                    self.finish_path()
            else:  # Sim speed > 32
                self.finish_path()
        else:  # No path
            if not any(np.sqrt((self.location[0] - vehicle.location[0]) ** 2 + (self.location[1] - vehicle.location[1]) ** 2) < 250
                       and len(vehicle.path) >= 1 for vehicle in simulation.vehicles):
                if ((self.start_operation.is_ready() and not self.arrived) or (self.end_operation.completed and not self.departed)) and simulation.speed > 32:
                    self.finish_path()
                elif self.start_operation.is_ready() and self.goals_completed < len(self.goal_locs) and (self.wait_time <= 0 or self.goals_completed == 0):
                    self.arrived = False
                    self.path = smooth_astar(self.mesh_1, (self.location[0], self.location[1]),
                                             self.goal_locs[self.goals_completed], self.goal_rotation, straighten=self.straighten)
                    if self.path:
                        if len(self.path) == 1:
                            self.create_gate(0)
                        elif self.name in ['Spot']:
                            self.create_gate(10)
                        else:
                            self.create_gate()
                elif self.end_operation.completed and not self.departed:
                    if self.name in ['Hydrant_Truck', 'Hydrant_Truck_auto', 'Spot']:
                        reverse = False
                    else:
                        reverse = True
                    self.path = smooth_astar(self.mesh_2, (self.location[0], self.location[1]),
                                             self.end_loc, goal_rotation=self.goal_rotation, straighten=self.straighten, reverse=reverse)
                    if self.path:
                        if len(self.path) == 1:
                            self.create_gate(0)
                        elif self.name in ['Spot']:
                            self.create_gate(10)
                        else:
                            self.create_gate()
                elif self.arrived and self.wait_time > 0:
                    self.wait_time -= time_step

    def finish_path(self):
        self.path = []
        if self.goals_completed < len(self.goal_locs):
            self.location[0], self.location[1] = self.goal_locs[self.goals_completed][0], self.goal_locs[self.goals_completed][1]
            if self.goal_rotation is not None:
                self.rotation = self.goal_rotation
            self.arrived = True
            self.wait_time = self.waiting_times[self.goals_completed]
            self.goals_completed += 1
        else:
            self.location[0], self.location[1] = self.end_loc[0], self.end_loc[1]
            self.departed = True

    def create_gate(self, distance=80):
        x1, y1 = self.location
        x2, y2 = self.path[0]
        if x1 == x2:
            self.gate_slope = 0
        elif y1 == y2:
            self.gate_slope = math.inf
        else:
            slope = (y2 - y1) / (x2 - x1)
            self.gate_slope = -1 / slope

        dx = x2 - x1
        dy = y2 - y1
        if dy == 0:
            self.upwards = None
        else:
            self.upwards = True if dy > 0 else False
        if dx == 0:
            self.rightwards = None
        else:
            self.rightwards = True if dx > 0 else False

        length = np.sqrt(dx ** 2 + dy ** 2)
        dx /= length
        dy /= length
        self.gate_center = (x2 - dx * distance, y2 - dy * distance)
        self.gate_dx = np.sqrt(4000 / (1 + self.gate_slope ** 2))
        self.gate_dy = self.gate_slope * self.gate_dx
        self.gate_b = self.gate_center[1] - self.gate_slope * self.gate_center[0]

    def has_crossed_gate(self):
        if self.upwards is True:
            if self.location[1] >= self.gate_b + self.gate_slope * self.location[0]:
                return True
            else:
                return False
        elif self.upwards is False:
            if self.location[1] <= self.gate_b + self.gate_slope * self.location[0]:
                return True
            else:
                return False
        else:
            if self.rightwards is True:
                if self.location[0] >= self.gate_center[0]:
                    return True
                else:
                    return False
            else:
                if self.location[0] <= self.gate_center[0]:
                    return True
                else:
                    return False


def load_assets():
    images = {}
    rects = {}
    for file in os.listdir('assets'):
        if file.endswith('.png'):
            image = pg.image.load(f'assets\\{file}').convert_alpha()
            images[file[:-4]] = image
            rects[file[:-4]] = image.get_rect()
    return images, rects


if __name__ == "__main__":
    main_sim = Simulation()
    main_sim.run()
