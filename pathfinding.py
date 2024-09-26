import numpy as np
import heapq


def smooth_astar(mesh: np.ndarray, start: tuple, goal: tuple):
    if type(start) == list:
        start = (start[0], start[1])
    service_start = True if start == (655, 1370) else False
    service_end = True if goal == (535, 1370) else False

    start = (int(start[1] / 10) + 20, int(start[0] / 10))
    goal = (int(goal[1] / 10) + 20, int(goal[0] / 10))

    if 0 > start[0] >= mesh.shape[0] or 0 > start[1] >= mesh.shape[1]:
        raise ValueError(f'Pathfinding Error: inserted start value invalid. start = {start}')
    if 0 > goal[0] >= mesh.shape[0] or 0 > goal[1] >= mesh.shape[1]:
        raise ValueError(f'Pathfinding Error: inserted goal value invalid. goal = {goal}')

    path = astar(mesh, start, goal)
    smoothed_path = los_smooth_bwrd(path, mesh)

    if service_end:
        temp = smoothed_path[:-1]
        temp.append((122, 53))
        temp.append(smoothed_path[-1])
        smoothed_path = los_smooth_fwrd(temp, mesh)
    if service_start:
        temp = [smoothed_path[0], (122, 65)]
        temp.extend(smoothed_path[1:])
        smoothed_path = los_smooth_fwrd(temp, mesh)

    final_path = []
    for point in smoothed_path:
        final_path.append((point[1] * 10, (point[0] - 20) * 10))
    return final_path


def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(mesh: np.ndarray, start: tuple, goal: tuple):
    """
    :param mesh: np.array with 1s and 0s, where 0s are walls
    :type mesh: np.array
    :param start: (y, x)
    :type start: tuple
    :param goal: (y, x)
    :type goal: tuple
    :return: path in form of [(y, x), ... (y,x)]
    :rtype: list
    """
    # Directions: up, down, left, right
    neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    # Priority queue for A*
    queue = []
    heapq.heappush(queue, (0, start))

    # Dictionaries to store cost and path information
    came_from = {start: None}
    cost_so_far = {start: 0}

    while queue:
        _, current = heapq.heappop(queue)

        if current == goal:
            break

        for dx, dy in neighbors:
            next_node = (current[0] + dx, current[1] + dy)

            # Check if the next move is within bounds and not an obstacle
            if 0 <= next_node[0] < mesh.shape[0] and 0 <= next_node[1] < mesh.shape[1]:
                if mesh[next_node[0], next_node[1]] == 1:  # 1 means it's traversable
                    new_cost = cost_so_far[current] + 1

                    # If this path to next_node is better than previous ones
                    if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                        cost_so_far[next_node] = new_cost
                        priority = new_cost + heuristic(goal, next_node)
                        heapq.heappush(queue, (priority, next_node))
                        came_from[next_node] = current

    # Reconstruct the path
    path = []
    current = goal
    while current:
        path.append(current)
        current = came_from.get(current)

    path.reverse()  # Reverse the path to get it from start to goal
    return path


def los_smooth_bwrd(path, mesh):
    smooth_path = [path[0]]  # Add start
    current_node = 0
    while current_node != len(path) -1:
        for i in range(len(path) - current_node):
            i2 = -i - 1
            if not has_obstacle(smooth_path[-1], path[i2], mesh):
                smooth_path.append(path[i2])
                current_node = len(path) + i2
                break
    return smooth_path


def los_smooth_fwrd(path, mesh):
    smooth_path = [path[0]]  # Add start

    for i in range(len(path) - 2):
        if not has_obstacle(smooth_path[-1], path[i+2], mesh):  # Check if it can skip the next node, by looking if it can see the one after it
            continue
        smooth_path.append(path[i+1])  # if not, add the next node to the smooth path list

    smooth_path.append(path[-1])  # Add goal
    return smooth_path


def has_obstacle(start, end, array):
    y1, x1 = start
    y2, x2 = end

    # Bresenham's Line Algorithm
    steep = abs(x2 - x1) > abs(y2 - y1)

    # Swap x and y if steep, to make traversal simpler (swapped back when checking)
    if steep:
        y1, x1 = x1, y1
        y2, x2 = x2, y2

    if y1 > y2:  # Always traverse left to right
        y1, y2 = y2, y1
        x1, x2 = x2, x1

    dy = y2 - y1
    dx = abs(x2 - x1)
    error = dy / 2
    ystep = 1 if x1 < x2 else -1

    y = x1
    for x in range(y1, y2 + 1):
        coord = (y, x) if steep else (x, y)
        if array[coord[0], coord[1]] == 0:  # Check for obstacles
            return True
        error -= dx
        if error < 0:
            y += ystep
            error += dy

    return False


if __name__ == "__main__":
    print("Performing example A* path finding")
    example_start = (1, 0)  # Starting point
    example_goal = (5, 5)  # Target point
    example_array = np.array([
        [1, 1, 1, 0, 1, 1],
        [1, 0, 1, 0, 1, 1],
        [1, 0, 1, 1, 1, 1],
        [1, 1, 1, 0, 0, 0],
        [0, 0, 1, 1, 1, 1],
        [1, 1, 1, 1, 0, 1]
    ])
    print(f"mesh = \n{example_array}")
    example_path = astar(example_array, example_start, example_goal)
    print("Path found:", example_path)
    example_smoothed_path = los_smooth_bwrd(example_path, example_array)
    print("Smoothed path:", example_smoothed_path)
