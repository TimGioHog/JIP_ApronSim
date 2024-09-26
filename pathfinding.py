import numpy as np
import heapq


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


def line_of_sight_smooth(path, array):
    smooth_path = [path[0]]  # Start with the first point

    for i in range(len(path) - 2):
        if not has_obstacle(smooth_path[-1], path[i+2], array):
            continue
        smooth_path.append(path[i+1])

    smooth_path.append(path[-1])  # Add the last point
    return smooth_path


# Check if there’s an obstacle between two points
def has_obstacle(start, end, array):
    x1, y1 = start
    x2, y2 = end

    # Bresenham's Line Algorithm to check if there's a straight line path
    steep = abs(y2 - y1) > abs(x2 - x1)
    if steep:
        x1, y1 = y1, x1
        x2, y2 = y2, x2

    if x1 > x2:
        x1, x2 = x2, x1
        y1, y2 = y2, y1

    dx = x2 - x1
    dy = abs(y2 - y1)
    error = dx / 2
    ystep = 1 if y1 < y2 else -1

    y = y1
    for x in range(x1, x2 + 1):
        coord = (y, x) if steep else (x, y)
        if array[coord[0], coord[1]] == 0:  # Check for obstacles
            return True
        error -= dy
        if error < 0:
            y += ystep
            error += dx

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
    smoothed_path = line_of_sight_smooth(example_path, example_array)
    print("Smoothed path:", smoothed_path)
