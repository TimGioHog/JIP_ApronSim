import math
import os
import random

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
op_list_margin = 24
op_list_start = 160
display_mesh = pd.read_excel("assets/Meshes/Mesh_Inspection.xlsx", header=None)
random.seed(time.time())


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
        print(f'resetting for {sim_type}')
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
        self.screen = pg.display.set_mode((1920, 1080), pg.NOFRAME, pg.HWSURFACE,
                                          display=min(pg.display.get_num_displays() - 1, 1))

        self.images, self.rects = load_assets()
        self.scheduler = Scheduler('Old')
        self.timer = -self.scheduler.ops['Parking'].duration
        self.speed_limit = 32
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

        self.button_menu = Button(" ", (0, 0), (30, 30), callback=self.button_menu_action, color=(0, 0, 0))
        self.button_speed_decrease = Button("-", (200, 70), (20, 20), callback=self.button_speed_decrease_action,
                                            font_size=20)
        self.button_speed_increase = Button("+", (225, 70), (20, 20), callback=self.button_speed_increase_action,
                                            font_size=20)
        self.button_resume = Button("RESUME", (820, 320), (280, 50), self.button_resume_action)
        self.button_quit = Button("QUIT", (820, 730), (280, 50), self.button_quit_action)
        self.button_restart = Button("RESTART", (820, 400), (280, 50), self.button_restart_action)
        self.button_reset_delays = Button("Reset", (200, op_list_start - 27), (45, 20), self.button_reset_delays_action,
                                          font_size=24)
        self.button_sim_type = ButtonFlip("Old", "New", (900, 480), (120, 40), callback=self.button_sim_type_action,
                                          state=self.new_sim)
        self.button_sim_type_2 = ButtonFlip("Old", "New", (900, 1030), (120, 40), callback=self.button_sim_type_action,
                                            state=self.new_sim)
        self.button_paths = ButtonFlip("Off", "On", (1800, 50), (60, 20), callback=self.button_paths_action,
                                       state=self.blit_paths)
        self.button_mesh = ButtonFlip("Off", "On", (1800, 130), (60, 20), callback=self.button_mesh_action,
                                      state=self.blit_mesh)

        self.delay_buttons = []
        for i, operation in enumerate(self.scheduler.ops.values()):
            self.delay_buttons.append(
                ButtonDelay("-", (200, op_list_start + i * op_list_margin), (20, 20), operation, font_size=20))
            self.delay_buttons.append(
                ButtonDelay("+", (225, op_list_start + i * op_list_margin), (20, 20), operation, font_size=20))
        self.buttons = [self.button_menu, self.button_speed_decrease, self.button_speed_increase, self.button_resume,
                        self.button_quit, self.button_restart, self.button_reset_delays,
                        self.button_sim_type, self.button_sim_type_2, self.button_paths, self.button_mesh]
        self.buttons.extend(self.delay_buttons)

        self.mesh = display_mesh.to_numpy()

        self.vehicles = []
        self.create_vehicles()
        self.employees = [f'Employee_{random.randint(1, 4)}' for _ in range(5)]

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

        self.belt_front = Belt('Front')
        self.belt_rear = Belt('Rear')

    def draw(self):
        self.screen.fill('Black')
        self.screen.blit(self.images['apron'], self.rects['apron'])

        # Old Sim: Cones, GPU, PCA
        if not self.new_sim:
            if self.scheduler.ops['Connect_GPU'].completed and not self.scheduler.ops['Remove_GPU'].completed:
                self.screen.blit(self.images['GPU_cable'], (889, 943))
            if self.scheduler.ops['Place_Cones'].completed and not self.scheduler.ops['Remove_Cones'].completed:
                self.screen.blit(self.images['Cone'], (535, 455))
                self.screen.blit(self.images['Cone'], (1375, 455))
                self.screen.blit(self.images['Cone'], (835, 700))
                self.screen.blit(self.images['Cone'], (1075, 700))
            if self.scheduler.ops['Connect_PCA'].completed and not self.scheduler.ops['Remove_PCA'].completed:
                self.screen.blit(self.images['PCA_tube'], (965, 660))
            if self.scheduler.ops['Connect_LDL_Front'].completed and not self.scheduler.ops['Load_Front'].completed:
                draw_rotated(self.images[self.employees[0]], (800, 775), 90, self.screen)
                draw_rotated(self.images[self.employees[1]], (850, 870), -135, self.screen)
            if self.scheduler.ops['Connect_LDL_Rear'].completed and not self.scheduler.ops['Load_Rear'].completed:
                draw_rotated(self.images[self.employees[2]], (800, 285), 90, self.screen)
                draw_rotated(self.images[self.employees[3]], (850, 375), -135, self.screen)
            if self.scheduler.ops['Refuel_Prep'].completed and not self.scheduler.ops['Refuel_Finalising'].completed:
                draw_rotated(self.images[self.employees[4]], (625, 585), 40, self.screen)
        # New Sim: Rail chocks, Baggage Pit, GPU & PCA cables
        else:
            self.screen.blit(self.images['Rail_chock'], (865, 481))
            self.screen.blit(self.images['Rail_chock'], (1043, 481))
            self.screen.blit(self.images['Rail_chock'], (942, 871))

            if self.scheduler.ops['Connect_LDL_Rear'].start_time is not None and not self.scheduler.ops['Remove_LDL_Rear'].completed:
                if self.scheduler.ops['Offload_Rear'].start_time is not None and not self.scheduler.ops['Load_Rear'].completed:
                    self.screen.blit(self.images['Baggage_pit_extended'], (769, 314))
                elif self.scheduler.ops["Remove_LDL_Rear"].start_time is not None:
                    time_passed = self.timer - self.scheduler.ops["Remove_LDL_Rear"].start_time
                    self.screen.blit(self.images['Baggage_pit_extended'], (
                        max(769 - (((769 - 625) / self.scheduler.ops["Remove_LDL_Rear"].duration) * time_passed), 625),
                        314))
                else:
                    time_passed = self.timer - self.scheduler.ops["Connect_LDL_Rear"].start_time
                    self.screen.blit(self.images['Baggage_pit_extended'], (
                        min(625 + (((769 - 625) / self.scheduler.ops["Connect_LDL_Rear"].duration) * time_passed), 769),
                        314))

                self.screen.blit(self.images['Baggage_pit_open'], (712, 300))
            else:
                self.screen.blit(self.images['Baggage_pit'], (712, 300))

            if self.scheduler.ops['Connect_LDL_Front'].start_time is not None and not self.scheduler.ops['Remove_LDL_Front'].completed:
                if self.scheduler.ops['Offload_Front'].start_time is not None and not self.scheduler.ops['Load_Front'].completed:
                    self.screen.blit(self.images['Baggage_pit_extended'], (769, 815))
                elif self.scheduler.ops["Remove_LDL_Rear"].start_time is not None:
                    time_passed = self.timer - self.scheduler.ops["Remove_LDL_Front"].start_time
                    self.screen.blit(self.images['Baggage_pit_extended'], (
                        max(769 - (((769 - 625) / self.scheduler.ops["Remove_LDL_Front"].duration) * time_passed), 625),
                        815))

                else:
                    time_passed = self.timer - self.scheduler.ops["Connect_LDL_Front"].start_time
                    self.screen.blit(self.images['Baggage_pit_extended'], (
                        min(625 + (((769 - 625) / self.scheduler.ops["Connect_LDL_Front"].duration) * time_passed),
                            769),
                        815))

                self.screen.blit(self.images['Baggage_pit_open'], (712, 801))
            else:
                self.screen.blit(self.images['Baggage_pit'], (712, 801))

            pg.draw.line(self.screen, (255, 233, 38), (1238, 767), self.vehicles[0].location, width=10)
            pg.draw.line(self.screen, (255, 233, 38), (890, 1005), self.vehicles[1].location, width=3)

        # Vehicles
        for vehicle in self.vehicles:
            vehicle.draw(self.screen)

        # Baggage
        self.belt_front.draw(self.screen)
        self.belt_rear.draw(self.screen)
        if self.new_sim:
            self.screen.blit(self.images['Baggage_pit_cover_rear'], (620, 301))
            self.screen.blit(self.images['Baggage_pit_cover_front'], (620, 802))

        # PCA and GPU Units
        self.screen.blit(self.images['PCA_unit'], (1237, 750))
        self.screen.blit(self.images['GPU'], (850, 990))

        # Hydrant piping
        if self.scheduler.ops['Refuel_Prep'].completed and not self.scheduler.ops['Refuel_Finalising'].completed:
            self.screen.blit(self.images['Hydrant_pipes'], (588, 561))

        # Pushback Tug rendering
        if self.new_sim:
            if self.scheduler.ops["Pushback"].is_ready():
                self.screen.blit(self.images['Taxibot'],
                                 (909, 869 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
                                         self.timer - self.scheduler.ops["Pushback"].start_time)))
            elif self.scheduler.ops["Attach_Tug"].is_ready():
                self.screen.blit(self.images['Taxibot'], (909, 869))
        else:
            if self.scheduler.ops["Pushback"].is_ready():
                self.screen.blit(self.images['Tug'],
                                 (909, 869 - (20 / (self.scheduler.ops["Pushback"].duration / 60)) * (
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
            time_passed = self.timer - self.scheduler.ops["Connect_Bridge"].start_time
            self.screen.blit(self.images['Bridge_2'], (
                max(1233 - (((1233 - 987) / self.scheduler.ops["Connect_Bridge"].duration) * time_passed),
                    987),
                max(896 - (((896 - 854) / self.scheduler.ops["Connect_Bridge"].duration) * time_passed),
                    854)))

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
            self.screen.blit(small_font.render(string, True, colour), (10, op_list_start - 2 + i * op_list_margin))

            # Delay
            self.screen.blit(small_font.render(str(operation.delay), True, colour),
                             (175, op_list_start - 2 + i * op_list_margin))

            # Render operation on vop circle + name
            if operation.is_ready() and not operation.completed:
                operation_count += 1
                for op_loc_i in range(len(operation.locations)):
                    pg.draw.circle(self.screen, (255, 0, 0), operation.locations[op_loc_i], 10)
                    self.screen.blit(small_font.render(string, True, (0, 0, 0)),
                                     (operation.locations[op_loc_i][0], operation.locations[op_loc_i][1] + 10))

        # Menu button
        self.button_menu.draw(self.screen)
        pg.draw.circle(self.screen, white, (15, 8), 2)
        pg.draw.circle(self.screen, white, (15, 15), 2)
        pg.draw.circle(self.screen, white, (15, 22), 2)

        # Option buttons
        rect_surface = pg.Surface((180, 170), pg.SRCALPHA)
        rect_surface.fill(pg.Color(0, 0, 0, 150))
        self.screen.blit(rect_surface, (1740, 0))
        self.screen.blit(medium_font.render(f'Pathing', True, white),
                         (1830 - medium_font.size('Pathing')[0] / 2, 5))
        self.button_paths.draw(self.screen, self.blit_paths)
        self.screen.blit(medium_font.render(f'Access Map', True, white),
                         (1830 - medium_font.size('Access Map')[0] / 2, 85))
        self.button_mesh.draw(self.screen, self.blit_mesh)

        # Speed buttons
        self.button_speed_decrease.draw(self.screen)
        self.button_speed_increase.draw(self.screen)

        # Delay buttons
        for button in self.delay_buttons:
            button.draw(self.screen)
        self.button_reset_delays.draw(self.screen)

        # Clock rendering - Minutes
        time_left = 51 * 60 - self.timer

        sign = '+' if time_left < 0 else '-'
        minutes = abs(int(time_left / 60))
        self.screen.blit(large_font.render(f'{sign}{minutes:02}', True, white), (67 if time_left < 0 else 75, 10))

        # Clock rendering - Seconds
        seconds = int(60 - time_left % 60) if time_left < 0 else int(time_left % 60)
        self.screen.blit(large_font.render(f':{seconds:02}', True, white), (123, 10))

        # Speed
        self.screen.blit(medium_font.render(f'Speed: {self.speed}x', True, white), (10, 60))

        # FPS Counter
        self.screen.blit(small_font.render(f'{int(self.fps)}', True, white), (210, 10))

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
                    pg.draw.line(self.screen, white,
                                 (vehicle.gate_center[0] - vehicle.gate_dx, vehicle.gate_center[1] - vehicle.gate_dy),
                                 (vehicle.gate_center[0] + vehicle.gate_dx, vehicle.gate_center[1] + vehicle.gate_dy),
                                 2)

        # Mesh overlay
        if self.blit_mesh:
            self.screen.blit(self.mesh_surface, (0, 0))

        # Coord debugging
        if self.blit_coord:
            coords = pg.mouse.get_pos()
            self.screen.blit(small_font.render(str(coords), True, white), (coords[0] + 5, coords[1] + 5))
            self.screen.blit(small_font.render(str((int(coords[1] / 10) + 20, int(coords[0] / 10))), True, white),
                             (coords[0] + 5, coords[1] + 25))

        # Paused Pop-Up
        if self.paused and not self.pause_menu:
            pg.draw.rect(self.screen, black, pg.Rect(816, 0, 288, 60))
            self.screen.blit(large_font.render(f'Simulation Paused', True, white), (826, 10))
        elif self.speed > self.speed_limit:
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
            self.button_sim_type.draw(self.screen, self.new_sim)

        else:
            rect_surface = pg.Surface((320, 60), pg.SRCALPHA)
            rect_surface.fill(pg.Color(0, 0, 0, 150))
            self.screen.blit(rect_surface, (800, 1020))
            self.button_sim_type_2.draw(self.screen, self.new_sim)
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
                self.button_menu.handle_event(event)
                self.button_speed_decrease.handle_event(event)
                self.button_speed_increase.handle_event(event)
                self.button_paths.handle_event(event)
                self.button_mesh.handle_event(event)
                self.button_reset_delays.handle_event(event)

                if self.pause_menu or self.scheduler.finished:
                    self.button_quit.handle_event(event)
                    self.button_restart.handle_event(event)
                    self.button_resume.handle_event(event)
                    self.button_sim_type.handle_event(event)
                else:
                    self.button_sim_type_2.handle_event(event)

    def update(self, duration):
        time_step = duration * self.speed
        self.timer += time_step
        self.scheduler.update(self, time_step)
        for vehicle in self.vehicles:
            if not vehicle.departed:
                vehicle.update(time_step, self)

        self.belt_front.update(time_step, self)
        self.belt_rear.update(time_step, self)

        if self.scheduler.ops['Connect_LDL_Front'].completed and self.scheduler.ops['Remove_LDL_Front'].start_time is None:
            if self.scheduler.ops['Offload_Front'].start_time is not None and not self.scheduler.ops['Offload_Front'].completed:
                new_front_status = 'Unload'
            elif self.scheduler.ops['Load_Front'].start_time is not None and not self.scheduler.ops['Load_Front'].completed:
                new_front_status = 'Load'
            else:
                new_front_status = None
        else:
            new_front_status = None
        if self.scheduler.ops['Connect_LDL_Rear'].completed and self.scheduler.ops['Remove_LDL_Rear'].start_time is None:
            if self.scheduler.ops['Offload_Rear'].start_time is not None and not self.scheduler.ops['Offload_Rear'].completed:
                new_rear_status = 'Unload'
            elif self.scheduler.ops['Load_Rear'].start_time is not None and not self.scheduler.ops['Load_Rear'].completed:
                new_rear_status = 'Load'
            else:
                new_rear_status = None
        else:
            new_rear_status = None

        if new_front_status != self.belt_front.status:
            if self.belt_front.bags:
                if not self.belt_front.status.startswith('Finish'):
                    self.belt_front.status = 'Finish_' + self.belt_front.status
            elif self.belt_front.delay_counter > 0:
                self.belt_front.delay_counter -= time_step
            else:
                self.belt_front.status = new_front_status
                self.belt_front.delay_counter = 150
        if new_rear_status != self.belt_rear.status:
            if self.belt_rear.bags:
                if not self.belt_rear.status.startswith('Finish'):
                    self.belt_rear.status = 'Finish_' + self.belt_rear.status
            elif self.belt_rear.delay_counter > 0:
                self.belt_rear.delay_counter -= time_step
            else:
                self.belt_rear.status = new_rear_status
                self.belt_rear.delay_counter = 150

    def run(self):
        print("Running...")
        self.last_frame = time.perf_counter()
        fps_list = []
        fps_update_time = 0

        while self.running:
            self.draw()
            self.event_handler()

            current_time = time.perf_counter()
            frame_duration = current_time - self.last_frame
            self.last_frame = current_time

            if not self.paused and not self.pause_menu and not self.scheduler.finished:
                self.update(frame_duration)

            fps_list.append(1 / frame_duration)
            fps_update_time += frame_duration
            if fps_update_time >= 0.5:
                self.fps = int(sum(fps_list) / len(fps_list))
                self.speed_limit = self.fps / 2  # Makes sure there are always two updates per simulated second
                fps_list = []
                fps_update_time = 0
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
            self.delay_buttons.append(
                ButtonDelay("-", (200, op_list_start + i * op_list_margin), (20, 20), operation, font_size=20))
            self.delay_buttons.append(
                ButtonDelay("+", (225, op_list_start + i * op_list_margin), (20, 20), operation, font_size=20))
        self.create_vehicles()

        self.belt_front.reset()
        self.belt_rear.reset()

        self.paused = False
        self.pause_menu = False
        self.restart = False
        self.last_frame = time.perf_counter()

    def button_menu_action(self):
        if not self.scheduler.finished:
            self.pause_menu = not self.pause_menu

    def button_speed_decrease_action(self):
        if self.speed >= 2:
            self.speed = int(self.speed / 2)

    def button_speed_increase_action(self):
        if self.speed <= 512:
            self.speed = int(self.speed * 2)

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

    def button_paths_action(self):
        self.blit_paths = not self.blit_paths

    def button_mesh_action(self):
        self.blit_mesh = not self.blit_mesh

    def create_vehicles(self):
        self.vehicles = []

        if self.new_sim:
            self.vehicles.append(
                Vehicle('PCA_cart', [self.scheduler.ops["Connect_PCA"], None], [None, self.scheduler.ops["Remove_PCA"]],
                        (1215, 765), goal_locs=[(975, 705), (1215, 765)], max_speed=0.5, goal_rotations=[None, None], straighten=0,
                        start_rotation=-164, service_road_end=False))
            self.vehicles.append(
                Vehicle('GPU_cart', [self.scheduler.ops["Connect_GPU"], None], [None, self.scheduler.ops["Remove_GPU"]],
                        (905, 995), goal_locs=[(965, 945), (905, 995)], max_speed=0.5, goal_rotations=[None, None], straighten=0,
                        start_rotation=-40, service_road_end=False))
            self.vehicles.append(
                Vehicle('Hydrant_Truck_auto', [self.scheduler.ops["Refuel_Prep"], None], [None, None, self.scheduler.ops["Refuel_Finalising"]],
                        (655, 1370), goal_locs=[(355, 895), (715, 635)], goal_rotations=[160, 98],
                        reverse=[False, True], waiting_times=[10, 0], straighten=10, snap=[False, False]))
            self.vehicles.append(
                Vehicle('Catering_auto', [self.scheduler.ops["Catering_Rear"], None], [None, self.scheduler.ops["Catering_Rear"], None],
                        (655, 1370), goal_locs=[(837, 227), (335, 200)], goal_rotations=[5, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Catering_auto', [self.scheduler.ops["Catering_Front"], None], [None, self.scheduler.ops["Catering_Front"], None],
                        (655, 1370), goal_locs=[(845, 925), (445, 940)], goal_rotations=[-12, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Lavatory_auto', [self.scheduler.ops["Toilet_Service"], None], [None, None, self.scheduler.ops["Toilet_Service"]],
                        (655, 1370), goal_locs=[(1445, 305), (1055, 305)],
                        goal_rotations=[0, 0], reverse=[False, True], snap=[False, True], straighten=15))
            self.vehicles.append(
                Vehicle('Water_auto', [self.scheduler.ops["Water_Service"]], [None, self.scheduler.ops["Water_Service"]],
                        (655, 1370), goal_locs=[(905, 75)], goal_rotations=[80], snap=[False]))
            self.vehicles.append(
                Vehicle(f'Cleaning_car_auto', [self.scheduler.ops['Cabin_Cleaning']], [None, self.scheduler.ops['Cabin_Cleaning']],
                        (655, 1370), [(1425, 125)], goal_rotations=[70]))
            self.vehicles.append(
                Vehicle('Stairs_auto', [self.scheduler.ops["Deboard"], None], [None, self.scheduler.ops["Cabin_Cleaning"], None],
                        (655, 1370), goal_locs=[(1085, 205), (1335, 165)], goal_rotations=[171, 171], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Spot', [self.scheduler.ops["Technical_Inspection"]] + [None] * 7, [None] * 7 + [self.scheduler.ops["Technical_Inspection"]],
                        (1485, 735), goal_locs=[(1085, 715), (1065, 405), (1125, 145), (855, 145), (855, 405), (845, 715), (815, 985), (1485, 735)],
                        max_speed=0.3, goal_rotations=[None] * 8, straighten=0, waiting_times=[140] * 8,
                        snap=[False] * 8, service_road_end=False))
        else:
            self.vehicles.append(
                Vehicle('Hydrant_Truck', [self.scheduler.ops["Refuel_Prep"], None, None], [None, None, self.scheduler.ops["Refuel_Finalising"], None],
                        (655, 1370), goal_locs=[(355, 895), (705, 635), (635, 695)], goal_rotations=[160, 110, None], reverse=[False, True, False], straighten=10))
            self.vehicles.append(
                Vehicle('LDL', [self.scheduler.ops["Connect_LDL_Rear"], None], [None, self.scheduler.ops["Remove_LDL_Rear"], None],
                        (655, 1370), goal_locs=[(815, 325), (315, 325)], goal_rotations=[0, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('LDL', [self.scheduler.ops["Connect_LDL_Front"], None], [None, self.scheduler.ops["Remove_LDL_Front"], None],
                        (655, 1370), goal_locs=[(815, 825), (415, 825)], goal_rotations=[0, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Catering', [self.scheduler.ops["Catering_Rear"], None], [None, self.scheduler.ops["Catering_Rear"], None],
                        (655, 1370), goal_locs=[(837, 227), (335, 200)], goal_rotations=[5, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Catering', [self.scheduler.ops["Catering_Front"], None], [None, self.scheduler.ops["Catering_Front"], None],
                        (655, 1370), goal_locs=[(845, 925), (375, 940)], goal_rotations=[-12, None], snap=[True, False], reverse=[False, True]))
            self.vehicles.append(
                Vehicle('Lavatory', [self.scheduler.ops["Toilet_Service"], None], [None, None, self.scheduler.ops["Toilet_Service"]],
                        (655, 1370), goal_locs=[(1445, 305), (1055, 305)],
                        goal_rotations=[0, 0], reverse=[False, True], snap=[False, True], straighten=15))
            self.vehicles.append(
                Vehicle('Water', [self.scheduler.ops["Water_Service"]], [None, self.scheduler.ops["Water_Service"]],
                        (655, 1370), goal_locs=[(905, 75)], goal_rotations=[80], snap=[False]))
            self.vehicles.append(
                Vehicle(f'Cleaning_car', [self.scheduler.ops['Cabin_Cleaning']], [None, self.scheduler.ops['Cabin_Cleaning']],
                        (655, 1370), [(1425, 125)], goal_rotations=[70]))
            self.vehicles.append(
                Vehicle('Stairs', [self.scheduler.ops["Deboard"], None], [None, self.scheduler.ops["Cabin_Cleaning"], None],
                        (655, 1370), goal_locs=[(1085, 205), (1335, 165)], goal_rotations=[171, 171], reverse=[False, True]))
            self.vehicles.append(
                Vehicle(f'Employee_{random.randint(1, 4)}', [self.scheduler.ops["Technical_Inspection"]] + [None] * 7,
                        [None] * 7 + [self.scheduler.ops["Technical_Inspection"]],
                        (1485, 735), goal_locs=[(1085, 715), (1065, 405), (1125, 145), (855, 145), (855, 405), (845, 715), (815, 985), (1485, 735)],
                        max_speed=0.5, goal_rotations=[None] * 8, straighten=0, waiting_times=[230] * 8,
                        snap=[False] * 8, service_road_end=False))
            self.vehicles.append(
                Vehicle(f'Baggage_truck', [self.scheduler.ops['Offload_Front'], None, None], [None, None, self.scheduler.ops['Offload_Front'], None],
                        (655, 1370), [(685, 785), (335, 805), (665, 785)], goal_rotations=[-90, None, -135], trailers=3,
                        waiting_times=[30, 0, 30], reverse=[False, False, True], straighten=10))
            self.vehicles.append(
                Vehicle(f'Baggage_truck', [self.scheduler.ops['Offload_Rear'], None, None], [None, None, self.scheduler.ops['Offload_Rear'], None],
                        (655, 1370), [(685, 225), (305, 215), (625, 225)], goal_rotations=[-90, None, -135], trailers=3,
                        waiting_times=[30, 0, 30], reverse=[False, False, True], straighten=10))
            self.vehicles.append(
                Vehicle(f'Baggage_truck', [self.scheduler.ops['Load_Front'], None, None, None], [None, None, None, self.scheduler.ops['Load_Front'], None],
                        (655, 1370), [(655, 1015), (685, 785), (335, 805), (665, 785)], goal_rotations=[-90, -90, None, -135], trailers=3,
                        waiting_times=[40, 30, 0, 30], reverse=[False, False, False, True], straighten=10, trailers_loaded=True))
            self.vehicles.append(
                Vehicle(f'Baggage_truck', [self.scheduler.ops['Load_Rear'], None, None, None], [None, None, None, self.scheduler.ops['Load_Rear'], None],
                        (655, 1370), [(285, 465), (685, 225), (305, 215), (625, 225)], goal_rotations=[-90, -90, None, -135], trailers=3,
                        waiting_times=[50, 30, 0, 30], reverse=[False, False, False, True], straighten=10, trailers_loaded=True))


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
        self.flip_rect = pg.Rect(self.rect.x + self.circle_radius, self.flip_y - self.rect.height / 2,
                                 self.rect.width - 2 * self.circle_radius, self.rect.height)

        self.text_surface_1 = self.font.render(text1, True, white)
        self.text_surface_2 = self.font.render(text2, True, white)

        self.text_pos_1 = (self.rect.x - self.font.size(text1)[0] - 10, self.flip_y - self.font.size(text1)[1] / 2)
        self.text_pos_2 = (self.rect.x + self.rect.width + 10, self.flip_y - self.font.size(text1)[1] / 2)

    def draw(self, screen, state):
        # Render text
        screen.blit(self.text_surface_1, (self.text_pos_1[0], self.text_pos_1[1]))
        screen.blit(self.text_surface_2, (self.text_pos_2[0], self.text_pos_2[1]))

        self.state = state
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


class Vehicle:
    def __init__(self, name: str, start_ops: list, end_ops: list, start_loc, goal_locs, goal_rotations,
                 max_speed: float = 1.1, start_velocity=0, start_rotation=-90, acceleration=0.5, straighten=20, max_rotation=30,
                 waiting_times: list = None, reverse: list = None, snap: list = None, trailers=0, trailers_loaded=False, service_road_end=True):

        # Standard parameters
        self.name = name
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.image = pg.image.load(f'assets\\{name}.png').convert_alpha()
        self.image_rect = self.image.get_rect()
        self.straighten = straighten
        self.max_rotation = max_rotation

        # Goal specific
        self.goal_locs = goal_locs
        self.goal_rotations = goal_rotations
        if waiting_times is None:
            self.waiting_times = [0] * len(goal_locs)
        else:
            self.waiting_times = waiting_times
        if reverse is None:
            self.reverse_list = [False] * len(goal_locs)
        else:
            self.reverse_list = reverse
        if snap is None:
            self.snap_list = [False] * len(goal_locs)
        else:
            self.snap_list = snap
        self.start_ops = start_ops
        self.end_ops = end_ops

        if service_road_end:
            self.goal_locs.append((535, 1370))
            self.goal_rotations.append(90)
            self.waiting_times.append(0)
            self.reverse_list.append(False)
            self.snap_list.append(True)
            self.start_ops.append(None)

        assert len(self.goal_locs) == len(self.goal_rotations)
        assert len(self.goal_locs) == len(self.waiting_times)
        assert len(self.goal_locs) == len(self.reverse_list)
        assert len(self.goal_locs) == len(self.snap_list)
        assert len(self.goal_locs) == len(self.start_ops)
        assert len(self.goal_locs) == len(self.end_ops)

        # Start parameters
        self.location = [start_loc[0], start_loc[1]]
        self.rotation = start_rotation
        self.speed = start_velocity
        self.wait_time = self.waiting_times[0]
        self.trailers = [Trailer(self.rotation, self.location, i, trailers_loaded, self) for i in range(trailers)]

        # Variable initialisation
        self.path = []
        self.full_reverse = False
        self.arrived = False
        self.departed = False
        self.stopped = False
        self.gate_center = None
        self.gate_slope = None
        self.gate_dx = None
        self.gate_dy = None
        self.gate_b = None
        self.upwards = None
        self.rightwards = None
        self.goals_completed = 0
        self.end_goals_completed = 0
        self.prev_steering = 0
        self.stop_counter = 0
        if self.name in ['Spot', 'Employee_1', 'Employee_2', 'Employee_3', 'Employee_4']:
            self.walking = True
        else:
            self.walking = False

        # Mesh initialization
        if self.walking:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Inspection.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()
        elif name in ['PCA_cart', 'GPU_cart']:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Free.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()
        elif name in ['Water', 'Water_auto']:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Water.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()
        elif name in ['Lavatory', 'Lavatory_auto']:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_Lavatory.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()
        else:
            mesh_df = pd.read_excel("assets/Meshes/Mesh_4.xlsx", header=None)
            self.mesh = mesh_df.to_numpy()

    def draw(self, screen):
        draw_rotated(self.image, self.location, self.rotation, screen)

        for trailer in self.trailers:
            trailer.draw(screen)
        if self.stopped:
            pg.draw.circle(screen, (255, 100, 0), self.location, 10)

    def update(self, time_step, simulation):
        if self.path:
            if simulation.speed <= simulation.speed_limit:
                stop = False
                # if self.full_reverse:
                #     heading = self.rotation - 180 if self.rotation > 0 else self.rotation + 180
                # else:
                #     heading = self.rotation
                # simulation.screen.blit(small_font.render(str(round(heading, 2)), True, (0, 255, 0)), (self.location[0], self.location[1]))

                # i = -1

                for truck in simulation.vehicles:
                    if not truck == self and len(truck.path) >= 1:
                        # i += 1
                        truck_n_trailers = [truck] + truck.trailers
                        for vehicle in truck_n_trailers:
                            distance = np.sqrt((vehicle.location[0] - self.location[0]) ** 2 + (vehicle.location[1] - self.location[1]) ** 2)

                            angle_difference = heading_angle(self, vehicle)
                            angle_difference_2 = heading_angle(vehicle, self)

                            if ((-60 < angle_difference < 60 and (-60 < angle_difference_2 < 60) and distance < 200 and not truck.stopped)
                                    or (-30 < angle_difference < 30 and (-30 < angle_difference_2 < 30) and distance < 400 and not truck.stopped)
                                    or (-25 < angle_difference < 25 and distance < 300 and not truck.stopped)):
                                stop = True
                                break
                        # simulation.screen.blit(small_font.render(str(round(distance, 2)), True, (0, 100, 255)), (self.location[0], self.location[1] + 40 + (60*i)))
                        # simulation.screen.blit(small_font.render(str(round(angle_difference, 2)), True, (0, 0, 0)), (self.location[0], self.location[1] + 60 + (60*i)))
                if stop:
                    self.stopped = True
                    self.stop_counter = 3
                elif self.stop_counter > 0:
                    self.stop_counter -= time_step
                else:
                    self.stopped = False

                dx = self.path[0][0] - self.location[0]
                dy = self.path[0][1] - self.location[1]
                angle = np.rad2deg(np.arctan2(dy, dx))
                travel_distance = time_step * self.speed * 25  # 25 pixels per meter

                # Displacement
                tx = np.cos(np.deg2rad(self.rotation)) * travel_distance
                ty = np.sin(np.deg2rad(self.rotation)) * travel_distance
                self.location[0] += tx
                self.location[1] += ty

                reverse = True if self.full_reverse else False
                angle_diff = angle - self.rotation
                if angle_diff < -180:
                    angle_diff += 360
                elif angle_diff > 180:
                    angle_diff -= 360
                if abs(angle_diff) > 178:
                    if self.name.startswith('Employee'):
                        self.rotation = angle
                    elif not self.name.startswith('Baggage'):
                        reverse = True
                if reverse:
                    reverse_rotation = self.rotation + 180
                    if reverse_rotation > 180:
                        reverse_rotation -= 360
                    angle_diff = angle - reverse_rotation
                    if angle_diff < -180:
                        angle_diff += 360
                    elif angle_diff > 180:
                        angle_diff -= 360

                # Steering
                if self.walking:
                    steering_factor = 1
                else:
                    steering_factor = min(1.0, abs(self.speed / 3))
                steering = np.clip(10 * angle_diff * steering_factor * time_step, -self.max_rotation * time_step, self.max_rotation * time_step)
                steering = np.clip(steering, self.prev_steering - 20 * time_step, self.prev_steering + 20 * time_step)
                self.rotation += steering

                # Accelerating + Braking
                dist_goal = np.sqrt(
                    (self.path[-1][0] - self.location[0]) ** 2 + (self.path[-1][1] - self.location[1]) ** 2)
                brake_speed = ((self.max_speed - 0.1) / 200) * dist_goal + 0.1

                if self.stopped:
                    if reverse:
                        self.speed = min(self.speed + self.acceleration * time_step, 0)
                    else:
                        self.speed = max(self.speed - self.acceleration * time_step, 0)
                elif (not reverse and self.speed > brake_speed) or (reverse and self.speed < -brake_speed):
                    if reverse:
                        self.speed = max(self.speed, -brake_speed)
                    else:
                        self.speed = min(self.speed, brake_speed)
                else:
                    if reverse:
                        if self.speed - self.acceleration * time_step > -self.max_speed / 2:
                            self.speed -= self.acceleration * time_step
                        else:
                            self.speed = -self.max_speed
                    else:
                        if self.speed + self.acceleration * time_step < self.max_speed:
                            self.speed += self.acceleration * time_step
                        else:
                            self.speed = self.max_speed

                # Trailers
                for trailer in self.trailers:
                    if trailer.connected:
                        if trailer.number == 0:
                            prev_trailer = self
                        else:
                            prev_trailer = self.trailers[trailer.number - 1]
                        trailer.update(prev_trailer, time_step, self.speed)

                # Gate crossing
                crossed_gate = self.has_crossed_gate()
                if crossed_gate and len(self.path) > 1:
                    self.path = self.path[1:]
                    if len(self.path) == 1:
                        self.create_gate(0)
                    elif not self.arrived and len(self.path) <= self.straighten + 1:
                        self.create_gate(min(80, len(self.path) * 7))
                    elif self.walking:
                        self.create_gate(20)
                    else:
                        self.create_gate()
                elif crossed_gate:
                    self.finish_path()
            else:  # Sim speed > speed limit
                if self.snap_list is not None and self.goals_completed < len(self.snap_list):
                    self.snap_list[self.goals_completed] = True
                self.finish_path()
        else:  # No path
            if len(self.trailers) > 0:
                for trailer in self.trailers:
                    if self.start_ops[0].name.startswith('Offload'):
                        if self.goals_completed == 1:
                            trailer.move(simulation)
                        elif self.goals_completed == 3:
                            trailer.loaded = True
                            trailer.move_back(simulation, self)
                    elif self.start_ops[0].name.startswith('Load'):
                        if self.goals_completed == 2:
                            trailer.move(simulation)
                        elif self.goals_completed == 4:
                            trailer.loaded = False
                            trailer.move_back(simulation, self)

            if self.arrived and self.wait_time > 0:
                self.wait_time -= time_step
            elif ((self.start_ops[self.goals_completed] is None or self.start_ops[self.goals_completed].is_ready())
                  and (self.end_ops[self.goals_completed] is None or self.end_ops[self.goals_completed].completed)):
                # Check for vehicles moving nearby
                if not any(np.sqrt((self.location[0] - vehicle.location[0]) ** 2 + (self.location[1] - vehicle.location[1]) ** 2) < 400
                           and len(vehicle.path) >= 1 for vehicle in simulation.vehicles):
                    self.find_path(simulation)

    def find_path(self, simulation):
        # Skip movement due to too high sim speed
        if simulation.speed > simulation.speed_limit:
            # Snap due to skipping of movement
            if self.goals_completed < len(self.snap_list):
                self.snap_list[self.goals_completed] = True
            self.finish_path()

        # Find path to goal
        else:
            self.arrived = False
            self.full_reverse = self.reverse_list[self.goals_completed]
            self.path = smooth_astar(self.mesh, (self.location[0], self.location[1]),
                                     self.goal_locs[self.goals_completed],
                                     self.goal_rotations[self.goals_completed],
                                     straighten=self.straighten, full_reverse=self.full_reverse)
            if self.path is None:
                raise ValueError(f'Pathfinding Error: Could not find path for truck {self.name}: start={(self.location[0], self.location[1])}, '
                                 f'goal={self.goal_locs[self.goals_completed]},\n straighten={self.straighten}, full_reverse={self.full_reverse}')

            if len(self.path) == 1:
                self.create_gate(0)
            elif self.walking:
                self.create_gate(10)
            else:
                self.create_gate()

    def finish_path(self):
        self.path = []
        self.speed = 0
        if self.snap_list[self.goals_completed]:
            self.location[0], self.location[1] = self.goal_locs[self.goals_completed][0], \
                self.goal_locs[self.goals_completed][1]
            if self.goal_rotations[self.goals_completed] is not None:
                self.rotation = self.goal_rotations[self.goals_completed]

        self.arrived = True
        self.wait_time = self.waiting_times[self.goals_completed]
        self.goals_completed += 1

        if self.goals_completed == len(self.goal_locs):
            self.departed = True

        for trailer in self.trailers:
            if trailer.connected:
                if trailer.number == 0:
                    prev_trailer = self
                else:
                    prev_trailer = self.trailers[trailer.number - 1]
                trailer.update(prev_trailer, 0, self.speed)
            if self.start_ops[0].name.startswith('Offload'):
                if self.goals_completed == 1:
                    trailer.connected = False
                elif self.goals_completed == 3:
                    trailer.connected = True
            elif self.start_ops[0].name.startswith('Load'):
                if self.goals_completed == 2:
                    trailer.connected = False
                elif self.goals_completed == 4:
                    trailer.connected = True

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
        if self.gate_slope == math.inf:
            self.gate_dy = 4000
        else:
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


class Trailer:
    def __init__(self, rotation, location, trailer_number, loaded, truck):
        self.rotation = rotation
        self.truck = truck

        self.image_empty = pg.image.load(f'assets\\Baggage_trailer_empty.png').convert_alpha()
        self.image_full = pg.image.load(f'assets\\Baggage_trailer_full.png').convert_alpha()
        self.number = trailer_number
        self.previous_rotation = self.rotation
        self.total_slip = 0.0

        tx = location[0] - (60 * np.cos(np.deg2rad(rotation))) * (trailer_number + 1)
        ty = location[1] - (60 * np.sin(np.deg2rad(rotation))) * (trailer_number + 1)
        self.location = (tx, ty)
        self.loaded = loaded

        self.connected = True
        self.move_start_time = None
        self.move_start_loc = None
        self.move_start_rotation = None
        action = 'Offload' if truck.start_ops[0].name.startswith('Offload') else 'Load'
        self.action = action
        location = 'Front' if truck.start_ops[0].name.endswith('Front') else 'Rear'
        if location == 'Front':
            if self.number == 0:
                self.goal = (689, 829, -90)
            elif self.number == 1:
                self.goal = (745, 874, 180)
            elif self.number == 2:
                self.goal = (805, 874, 180)
            else:
                self.goal = None
        else:
            if self.number == 0:
                self.goal = (689, 323, -90)
            elif self.number == 1:
                self.goal = (745, 374, 180)
            elif self.number == 2:
                self.goal = (805, 374, 180)
            else:
                self.goal = None
        self.move_dx = None
        self.move_dy = None
        self.move_dr = None

    def update(self, prev_trailer, time_step, truck_speed):
        expected_x = self.location[0] + truck_speed * 25 * time_step * np.cos(np.deg2rad(self.previous_rotation))
        expected_y = self.location[1] + truck_speed * 25 * time_step * np.sin(np.deg2rad(self.previous_rotation))

        angle_diff = (prev_trailer.rotation - self.rotation) % 360

        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360

        # Update the trailer's rotation with some lag
        speed_factor = truck_speed / 4
        scalar = 1.67 * angle_diff
        self.rotation += scalar * speed_factor * time_step

        tx = prev_trailer.location[0] - 30 * np.cos(np.deg2rad(prev_trailer.rotation)) - 30 * np.cos(
            np.deg2rad(self.rotation))
        ty = prev_trailer.location[1] - 30 * np.sin(np.deg2rad(prev_trailer.rotation)) - 30 * np.sin(
            np.deg2rad(self.rotation))

        self.location = (tx, ty)

        slip = np.sqrt((expected_x - tx) ** 2 + (expected_y - ty) ** 2)
        self.total_slip += slip * time_step

        self.previous_rotation = self.rotation

    def draw(self, screen):
        rect_surface = pg.Surface((64, 37), pg.SRCALPHA)
        if self.loaded:
            rect_surface.blit(self.image_full, (0, 0))
        else:
            rect_surface.blit(self.image_empty, (0, 0))
        rotated_surface = pg.transform.rotate(rect_surface, -self.rotation)
        rotated_rect = rotated_surface.get_rect(center=self.location)

        screen.blit(rotated_surface, rotated_rect.topleft)

        # string = f'Trailer {self.number}: {round(self.total_slip, 2)}'
        # screen.blit(small_font.render(string, True, white), (1700, 200 + self.number * 20))

    def move(self, simulation):
        if self.move_start_time is None:
            self.move_start_time = simulation.timer
            self.move_start_loc = self.location
            self.move_start_rotation = self.rotation
            self.move_dx = self.goal[0] - self.location[0]
            self.move_dy = self.goal[1] - self.location[1]
            self.move_dr = self.goal[2] - self.rotation
            if self.move_dr > 180:
                self.move_dr -= 360
            elif self.move_dr < -180:
                self.move_dr += 360

        duration = 30
        time_passed = simulation.timer - self.move_start_time
        perc_completed = time_passed / duration
        if time_passed > duration:
            self.move_start_time = None
            self.location = (self.goal[0], self.goal[1])
            self.rotation = self.goal[2]
        else:
            self.location = (self.move_start_loc[0] + self.move_dx * perc_completed, self.move_start_loc[1] + self.move_dy * perc_completed)
            self.rotation = self.move_start_rotation + self.move_dr * perc_completed

    def move_back(self, simulation, truck):
        if self.move_start_time is None:
            self.goal = (truck.location[0] - 30 * np.cos(np.deg2rad(truck.rotation)) - 30 * np.cos(np.deg2rad(-90)) - (60 * np.cos(np.deg2rad(-90))) * self.number,
                         truck.location[1] - 30 * np.sin(np.deg2rad(truck.rotation)) - 30 * np.sin(np.deg2rad(-90)) - (60 * np.sin(np.deg2rad(-90))) * self.number,
                         -90)

        self.move(simulation)


class Belt:
    def __init__(self, location):
        self.bags = []
        if location == 'Front':
            self.location = location
        elif location == 'Rear':
            self.location = location
        else:
            raise ValueError('location must be either Front or Rear')
        self.status = None
        self.delay_counter = np.random.randint(150, 200)

    def update(self, time_step, simulation):
        for bag in self.bags:
            bag.update(time_step, self.status)

        if self.status == 'Load' or self.status == 'Unload':
            if not self.bags or (self.bags[-1].location[0] < 870 and self.status == 'Unload'):
                if self.location == 'Front':
                    self.bags.append(Bag((920, 830)))
                else:
                    self.bags.append(Bag((920, 330)))
            elif not self.bags or (self.bags[-1].location[0] > 775 and self.status == 'Load'):
                if self.location == 'Front':
                    self.bags.append(Bag((725, 830)))
                else:
                    self.bags.append(Bag((725, 330)))

        if self.bags and ((self.bags[0].location[0] < 700 and self.status in ['Unload', 'Finish_Unload'] and simulation.new_sim)
                          or (self.bags[0].location[0] < 725 and self.status in ['Unload', 'Finish_Unload'] and not simulation.new_sim)
                          or (self.bags[0].location[0] > 920 and self.status in ['Load', 'Finish_Load'])):
            self.bags.pop(0)

    def draw(self, screen):
        for bag in self.bags:
            bag.draw(screen)

    def reset(self):
        self.bags = []
        self.status = None


class Bag:
    def __init__(self, location):
        self.location = location
        self.image = pg.image.load(f'assets\\Baggage\\Bag_{np.random.randint(0, 12)}.png').convert_alpha()
        self.rotation = np.random.randint(-180, 180)

    def update(self, time_step, activity):
        if activity == 'Unload' or activity == 'Finish_Unload':
            self.location = (self.location[0] - 25 * 0.4 * time_step, self.location[1])
        elif activity == 'Load'or activity == 'Finish_Load':
            self.location = (self.location[0] + 25 * 0.4 * time_step, self.location[1])

    def draw(self, screen):
        rect_surface = pg.Surface(self.image.get_size(), pg.SRCALPHA)
        rect_surface.blit(self.image, (0, 0))
        rotated_surface = pg.transform.rotate(rect_surface, -self.rotation)
        rotated_rect = rotated_surface.get_rect(center=self.location)

        screen.blit(rotated_surface, rotated_rect.topleft)


def draw_rotated(image, location, rotation, screen):
    image_rect = image.get_rect()
    rect_surface = pg.Surface((image_rect.width, image_rect.height), pg.SRCALPHA)
    rect_surface.blit(image, (0, 0))
    rotated_surface = pg.transform.rotate(rect_surface, -rotation)
    rotated_rect = rotated_surface.get_rect(center=location)
    screen.blit(rotated_surface, rotated_rect.topleft)


def heading_angle(vehicle_1, vehicle_2):
    if isinstance(vehicle_1, Trailer):
        reversing = vehicle_1.truck.full_reverse
    else:
        reversing = vehicle_1.full_reverse
    if reversing:
        heading = vehicle_1.rotation - 180 if vehicle_1.rotation > 0 else vehicle_1.rotation + 180
    else:
        heading = vehicle_1.rotation
    angle_to_vehicle = np.arctan2((vehicle_2.location[1] - vehicle_1.location[1]), (vehicle_2.location[0] - vehicle_1.location[0]))
    angle_to_vehicle = np.rad2deg(angle_to_vehicle)
    angle_diff = heading - angle_to_vehicle
    if angle_diff > 180:
        angle_diff -= 360
    elif angle_diff < -180:
        angle_diff += 360
    return angle_diff


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
