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
            operation = Operation(row[0], row[1] * 60)
            for dep in row[2:5]:
                if pd.notna(dep):
                    operation.add_dependency(self.operations[dep])
            for i in range(3):
                if pd.notna(row[2*i + 5]) and pd.notna(row[2*i + 6]):
                    operation.locations.append((row[2*i + 5], row[2*i + 6]))
            self.operations[row[0]] = operation
        self.finished = False

    def update(self, sim, duration):
        for operation in self.operations.values():
            if operation.is_ready() and not operation.completed:
                operation.time_left -= duration
                if operation.time_left <= 0:
                    operation.completed = True
                    print(f'{operation} operation completed at time {sim.timer}!')
        if all(op.completed for op in self.operations.values()):
            self.finished = True


class Simulation:
    def __init__(self):
        self.images, self.rects = load_assets()
        self.screen = pg.display.set_mode((1920, 1080), pg.RESIZABLE, pg.HWSURFACE)
        current_df = pd.read_excel("data.xlsx")
        self.scheduler = Scheduler(current_df)
        self.timer = 0
        self.fps = 0
        self.speed = 1
        self.paused = False

    def draw(self):
        self.screen.fill('Black')
        self.screen.blit(self.images['apron'], self.rects['apron'])
        if self.scheduler.operations["Parking"].completed:
            self.screen.blit(self.images['737s'], self.rects['737s'].move(513, 17))
        else:
            self.screen.blit(self.images['737s'], self.rects['737s'].move(513, 17)) # 17 pixels per second

        for operation in self.scheduler.operations.values():
            if operation.is_ready() and not operation.completed:
                for i in range(len(operation.locations)):
                    pg.draw.circle(self.screen, (255, 0, 0), operation.locations[i], 10)
                    self.screen.blit(small_font.render(operation.name, True, (0, 0, 0)),
                                     (operation.locations[i][0], operation.locations[i][1] + 10))

        pg.draw.rect(self.screen, black, pg.Rect(0, 0, 100, 100))

        # Clock rendering - Minutes
        if int(self.timer / 60) < 10:
            self.screen.blit(large_font.render(f'0{int(self.timer / 60)}', True, white), (10, 10))
        else:
            self.screen.blit(large_font.render(f'{int(self.timer / 60)}', True, white), (10, 10))

        # Clock rendering - Seconds
        if self.timer % 60 < 10:
            self.screen.blit(large_font.render(f':0{self.timer % 60}', True, white), (47, 10))
        else:
            self.screen.blit(large_font.render(f':{self.timer % 60}', True, white), (47, 10))

        # Speed
        self.screen.blit(large_font.render(f'{self.speed}x', True, white), (10, 50))

        # FPS Counter
        self.screen.blit(small_font.render(f'{int(self.fps)}', True, white), (1880, 10))

        if self.paused:
            pg.draw.rect(self.screen, black, pg.Rect(816, 0, 288, 60))
            self.screen.blit(large_font.render(f'Simulation Paused', True, white), (826, 10))

        pg.display.flip()

    def event_handler(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
            elif event.type == pg.KEYUP:
                if event.key == 27:  # Escape
                    pg.quit()
                elif event.unicode == " ":
                    self.paused = not self.paused
                elif event.unicode == "=" and self.speed <= 128:
                    self.speed = int(self.speed * 2)
                elif event.unicode == "-" and self.speed >= 2:
                    self.speed = int(self.speed / 2)

    def update(self):
        adjusted_speed = int(max(1, self.speed / 8))
        self.timer += adjusted_speed
        self.scheduler.update(self, adjusted_speed)

    def run(self):
        pg.init()
        pg.display.set_caption("ApronSim")
        print("Running...")
        last_frame = time.perf_counter()
        tick_start = time.perf_counter()
        running = True
        while running:
            self.event_handler()
            self.draw()

            current_time = time.perf_counter()
            frame_duration = current_time - last_frame
            last_frame = current_time

            if current_time - tick_start >= 1 / self.speed and not self.paused:
                tick_start = current_time
                self.update()

            self.fps = 1 / frame_duration


def load_assets():
    images = {}
    rects = {}
    for file in os.listdir('assets'):
        if file.endswith('.png'):
            image = pg.image.load(f'assets\\{file}')
            images[file[:-4]] = image
            rects[file[:-4]] = image.get_rect()
    return images, rects


if __name__ == "__main__":
    sim = Simulation()
    sim.run()
