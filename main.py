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
        self.operations = {}
        for index, row in df.iterrows():  # for each operation:
            operation = Operation(row.iloc[0], row.iloc[1] * 60)
            for dep in row.iloc[2:5]:
                if pd.notna(dep):
                    operation.add_dependency(self.operations[dep])
            for i in range(3):
                if pd.notna(row.iloc[2 * i + 5]) and pd.notna(row.iloc[2 * i + 6]):
                    operation.locations.append((row.iloc[2 * i + 5], row.iloc[2 * i + 6]))
            self.operations[row.iloc[0]] = operation
        self.finished = False

    def update(self, sim, duration):
        for operation in self.operations.values():
            if operation.is_ready() and not operation.completed:
                if operation.start_time is None:
                    operation.start_time = sim.timer
                operation.time_left -= duration
                if operation.time_left <= 0:
                    operation.completed = True
                    operation.completion_time = sim.timer
                    print(f'{operation} operation completed at time {sim.timer}!')
        if all(op.completed for op in self.operations.values()):
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

    def draw(self):
        self.screen.fill('Black')
        self.screen.blit(self.images['apron'], self.rects['apron'])
        if not self.scheduler.operations["Parking"].completed:
            self.screen.blit(self.images['737s'], (513, 17 - 1020 + 17 * self.timer))  # 17 pixels per second
        elif self.scheduler.operations["Pushback"].is_ready():
            self.screen.blit(self.images['737s'], (513, 17 - 17 * (self.timer - self.scheduler.operations["Pushback"].start_time)))  # 17 pixels per second
        else:
            self.screen.blit(self.images['737s'], (513, 17))

        operation_count = -1
        for operation in self.scheduler.operations.values():
            if operation.is_ready() and not operation.completed:
                operation_count += 1
                for i in range(len(operation.locations)):
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

        if self.paused and not self.pause_menu:
            pg.draw.rect(self.screen, black, pg.Rect(816, 0, 288, 60))
            self.screen.blit(large_font.render(f'Simulation Paused', True, white), (826, 10))
        elif self.pause_menu:
            rect_surface = pg.Surface((288, 600), pg.SRCALPHA)
            rect_surface.fill(pg.Color(0, 0, 0, 150))
            self.screen.blit(rect_surface, (816, 200))

        pg.display.flip()

    def event_handler(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
            elif event.type == pg.KEYUP:
                if event.key == 27:  # Escape
                    self.pause_menu = not self.pause_menu
                elif event.unicode == " " and not self.pause_menu:
                    self.paused = not self.paused
                elif event.unicode == "=":
                    self.speed = int(self.speed * 2)
                elif event.unicode == "-" and self.speed >= 2:
                    self.speed = int(self.speed / 2)

    def update(self, duration):
        self.timer += duration * self.speed
        self.scheduler.update(self, duration * self.speed)

    def run(self):
        pg.init()
        pg.display.set_caption("ApronSim")
        print("Running...")
        last_frame = time.perf_counter()
        running = True
        # for image in self.images:
        #     print(image)
        #     self.images[image] = pg.image.load(f'assets/{image}.png').convert_alpha()
        while running:
            self.event_handler()
            self.draw()

            current_time = time.perf_counter()
            frame_duration = current_time - last_frame
            last_frame = current_time

            if not self.paused and not self.pause_menu:
                self.update(frame_duration)

            self.fps = 1 / frame_duration


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
