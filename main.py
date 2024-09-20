import os

import numpy as np
import pandas as pd
import pygame as pg
import time

pg.font.init()
small_font = pg.font.SysFont('arial', 20)
large_font = pg.font.SysFont('arial', 40)
white = (255, 255, 255)
black = (0, 0, 0)
klm_rgb = (0, 161, 228)


class Operation:
    def __init__(self, name, duration):
        self.name = name
        self.duration = duration
        self.dependencies = []
        self.completed = False
        self.completion_time = None
        self.start_time = None
        self.time_left = duration
        self.locations = []

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
            operation = Operation(row.iloc[0], row.iloc[1] * 60)
            for dep in row.iloc[2:5]:
                if pd.notna(dep):
                    operation.add_dependency(self.ops[dep])
            for i in range(3):
                if pd.notna(row.iloc[2 * i + 5]) and pd.notna(row.iloc[2 * i + 6]):
                    operation.locations.append((row.iloc[2 * i + 5], row.iloc[2 * i + 6]))
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
                if operation.time_left <= 0:
                    operation.completed = True
                    operation.completion_time = sim.timer
                    print(f'{operation} operation completed at time {sim.timer}!')
        if all(op.completed for op in self.ops.values()):
            self.finished = True


class Simulation:
    def __init__(self):
        self.screen = pg.display.set_mode((1920, 1080), pg.RESIZABLE, pg.HWSURFACE)
        self.images, self.rects = load_assets()
        current_df = pd.read_excel("data.xlsx")
        self.scheduler = Scheduler(current_df)
        self.timer = 0
        self.fps = 0
        self.speed = 1
        self.paused = False
        self.pause_menu = False
        self.running = True
        self.restart = False

        self.button_resume = Button("RESUME", (820, 280), (280, 50), self.button_resume_action)
        self.button_quit = Button("QUIT", (820, 730), (280, 50), self.button_quit_action)
        self.button_restart = Button("RESTART", (820, 360), (280, 50), self.button_restart_action)

        self.buttons = [self.button_resume, self.button_quit, self.button_restart]

    def draw(self):
        self.screen.fill('Black')
        self.screen.blit(self.images['apron'], self.rects['apron'])

        # Hydrant-truck rendering
        if self.scheduler.ops['Refuel'].is_ready() and not self.scheduler.ops['Refuel'].completed:
            self.screen.blit(self.images['Hydrant_Truck'], (717, 515))

        # Aircraft rendering
        if not self.scheduler.ops["Parking"].completed:
            self.screen.blit(self.images['737s'], (513, 17 - 1020 + 17 * self.timer))  # 17 pixels per second
        elif self.scheduler.ops["Pushback"].is_ready():
            self.screen.blit(self.images['737s'], (513, 17 - (17 / (self.scheduler.ops["Pushback"].duration / 60)) * (self.timer - self.scheduler.ops["Pushback"].start_time)))
        else:
            self.screen.blit(self.images['737s'], (513, 17))

        # Bridge rendering
        self.screen.blit(self.images['Bridge_1'], (1330, 924))
        if self.scheduler.ops["Connect_Bridge"].start_time is None or self.scheduler.ops["Remove_Bridge"].completed:
            self.screen.blit(self.images['Bridge_2'], (1233, 896))
        elif self.scheduler.ops["Connect_Bridge"].completed and self.scheduler.ops["Remove_Bridge"].start_time is None:
            self.screen.blit(self.images['Bridge_2'], (987, 854))
        elif self.scheduler.ops["Remove_Bridge"].start_time is not None:
            removing_bridge_time = self.timer - self.scheduler.ops["Remove_Bridge"].start_time
            self.screen.blit(self.images['Bridge_2'], (987 + (((1233 - 987) / self.scheduler.ops["Connect_Bridge"].duration) * removing_bridge_time),
                                                       854 + (((896 - 854) / self.scheduler.ops["Connect_Bridge"].duration) * removing_bridge_time)))
        else:
            connecting_bridge_time = self.timer - self.scheduler.ops["Connect_Bridge"].start_time
            self.screen.blit(self.images['Bridge_2'], (1233 - (((1233 - 987) / self.scheduler.ops["Connect_Bridge"].duration) * connecting_bridge_time),
                                                       896 - (((896 - 854) / self.scheduler.ops["Connect_Bridge"].duration) * connecting_bridge_time)))

        operation_count = -1
        for operation in self.scheduler.ops.values():
            if operation.is_ready() and not operation.completed:
                operation_count += 1
                for i in range(len(operation.locations)):
                    if operation.name not in ["Parking", "Connect_Bridge", "Remove_Bridge"]:
                        pg.draw.circle(self.screen, (255, 0, 0), operation.locations[i], 10)
                        self.screen.blit(small_font.render(operation.name, True, (0, 0, 0)),
                                         (operation.locations[i][0], operation.locations[i][1] + 10))
                self.screen.blit(small_font.render(f'{operation}', True, white), (10, 100 + operation_count*35))

        pg.draw.rect(self.screen, black, pg.Rect(0, 0, 100, 100))

        # Clock rendering - Minutes
        if int(self.timer / 60) < 10:
            self.screen.blit(large_font.render(f'0{int(self.timer / 60)}', True, white), (10, 10))
        else:
            self.screen.blit(large_font.render(f'{int(self.timer / 60)}', True, white), (10, 10))

        # Clock rendering - Seconds
        if self.timer % 60 < 10:
            self.screen.blit(large_font.render(f':0{int(self.timer % 60)}', True, white), (47, 10))
        else:
            self.screen.blit(large_font.render(f':{int(self.timer % 60)}', True, white), (47, 10))

        # Speed
        self.screen.blit(large_font.render(f'{self.speed}x', True, white), (10, 50))

        # FPS Counter
        self.screen.blit(small_font.render(f'{int(self.fps)}', True, white), (1880, 10))

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
                self.screen.blit(large_font.render(f'Simulation Finished', True, white), (960 - large_font.size('Simulation Finished')[0] / 2, 220))
            else:
                self.screen.blit(large_font.render(f'Simulation Paused', True, white), (960 - large_font.size('Simulation Paused')[0]/2, 220))
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
            elif event.type == pg.MOUSEBUTTONUP or event.type == pg.MOUSEBUTTONDOWN or event.type == pg.MOUSEMOTION:
                if event.type == pg.MOUSEMOTION:
                    if any([button.is_hovered for button in self.buttons]):
                        pg.mouse.set_cursor(pg.SYSTEM_CURSOR_HAND)
                    else:
                        pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)

                if self.pause_menu or self.scheduler.finished:
                    self.button_quit.handle_event(event)
                    self.button_restart.handle_event(event)
                    self.button_resume.handle_event(event)

    def update(self, duration):
        self.timer += duration * self.speed
        self.scheduler.update(self, duration * self.speed)

    def run(self):
        pg.init()
        pg.display.set_caption("ApronSim")
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
                self.timer = 0
                self.speed = 1
                self.paused = False
                self.pause_menu = False
                self.scheduler.reset()
                self.restart = False
        pg.quit()

    def button_resume_action(self):
        if not self.scheduler.finished:
            self.pause_menu = False

    def button_restart_action(self):
        self.restart = True

    def button_quit_action(self):
        self.running = False


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
        self.text_pos = (self.rect.x + size[0]/2 - self.font.size(text)[0]/2, self.rect.y + size[1]/2 - self.font.size(text)[1]/2)

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
