import glob
import math
import random
import pygame
from dataclasses import dataclass
from matplotlib import image as mpimg
from matplotlib import pyplot as plt
from unified_planning.model import Object
from unified_planning.shortcuts import Problem
from util.constants import *
from util.problem_generator import ProblemGenerator
from util.tile import Tile


@dataclass
class Maze:
    tiles: list[Tile]
    start: Tile
    goal: Tile


class _MazeProblemGenerator(ProblemGenerator):

    def __init__(self, problem_count: int, auto: bool = False):
        super().__init__(problem_count)

        self._mazes = []
        self._tile_object_mapping = {}

        for p in range(problem_count):
            curr_maze = self._generate_maze() if not auto else self._generate_maze_auto()
            self._mazes.append(curr_maze)
            self._problems.append(self._generate_problem(curr_maze))

    @staticmethod
    def _change_special_tile(screen: pygame.Surface, special_tile: Tile, conflict_tile: Tile, new_tile: Tile,
                             colour: tuple) -> tuple:

        # If the special tile is already on the maze
        if special_tile is not None:
            old_special_tile = special_tile.get_rect()
            pygame.draw.rect(screen, FILLED_TILE, old_special_tile)
            special_tile.set_position(tile=new_tile)
        else:
            special_tile = new_tile

        # If the new tile is the same as the conflict tile, override
        if conflict_tile is not None:
            if new_tile == conflict_tile:
                conflict_tile = None

        # Draw the new tile
        pygame.draw.rect(screen, colour, new_tile.get_rect())
        return special_tile, conflict_tile

    def _generate_maze(self) -> Maze:

        # Display set-up
        pygame.init()
        screen = pygame.display.set_mode(SCREEN_SIZE)
        clock = pygame.time.Clock()
        screen.fill(BACKGROUND)
        maze_generated = False

        # maze set-up
        maze = []
        goal = None
        start = None
        to_change = START

        while not maze_generated:
            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    maze_generated = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        maze_generated = True

                if event.type == pygame.MOUSEBUTTONDOWN:
                    current_tile = Tile(pygame_position=pygame.mouse.get_pos())
                    if pygame.mouse.get_pressed()[0]:
                        if current_tile not in maze:
                            maze.append(current_tile)
                            pygame.draw.rect(screen, FILLED_TILE, current_tile.get_rect())
                        else:
                            maze.remove(current_tile)
                            if start is not None:
                                if current_tile == start:
                                    start = None
                            if goal is not None:
                                if current_tile == goal:
                                    goal = None
                            pygame.draw.rect(screen, BACKGROUND, current_tile.get_rect())
                    if pygame.mouse.get_pressed()[2]:
                        if current_tile in maze:
                            if to_change == START:
                                start, goal = self._change_special_tile(screen, start, goal, current_tile, START_TILE)
                                to_change = GOAL
                            elif to_change == GOAL:
                                goal, start = self._change_special_tile(screen, goal, start, current_tile, GOAL_TILE)
                                to_change = START

            pygame.display.flip()
            clock.tick(60)

        # Ensure start and goal has been set
        if start is None or goal is None:
            raise Exception("You must set a start [red] and a goal [green] by left clicking tiles.")

        pygame.image.save(screen, f"{MAZE_DIRECTORY}/maze{len(self._mazes)}.jpg")
        print("[DEBUG] maze generated successfully")
        pygame.quit()
        return Maze(maze, start, goal)

    def _generate_maze_auto(self):

        # maze set-up
        maze = []
        screen = pygame.display.set_mode(SCREEN_SIZE)
        screen.fill(BACKGROUND)
        available_locations = [(x, y) for x in range(TILE_COUNT) for y in range(TILE_COUNT)]

        start_location, goal_location = random.sample(available_locations, 2)
        start = Tile(tile_position=start_location)
        goal = Tile(tile_position=goal_location)
        maze.extend([start, goal])
        pygame.draw.rect(screen, START_TILE, start.get_rect())
        pygame.draw.rect(screen, GOAL_TILE, goal.get_rect())
        pygame.display.flip()

        current_tile = start
        while True:
            current_tile = Tile(tile_position=random.choice(current_tile.get_neighbours()))
            if current_tile == goal:
                break
            if current_tile not in maze:
                maze.append(current_tile)
                pygame.draw.rect(screen, FILLED_TILE, current_tile.get_rect())
                pygame.display.flip()

        pygame.image.save(screen, f"{MAZE_DIRECTORY}/maze{len(self._mazes)}.jpg")
        print("[DEBUG] maze generated successfully")
        pygame.quit()

        return Maze(maze, start, goal)

    def _add_mapping(self, tile: Tile, *pddl_objects: Object) -> None:
        tile_hash = hash(tile)
        pddl_objects = list(pddl_objects)
        observed_mapping = self._tile_object_mapping.get(tile_hash)
        if observed_mapping:
            self._tile_object_mapping[tile_hash].extend(pddl_objects)
        else:
            self._tile_object_mapping[tile_hash] = pddl_objects

    def _get_mapping(self, tile: Tile) -> list[Object]:
        tile_hash = hash(tile)
        return self._tile_object_mapping[tile_hash] if self._tile_object_mapping.get(tile_hash) else []

    def _generate_problem(self, maze: Maze) -> Problem:
        raise NotImplementedError

    @classmethod
    def display_maze_images(cls) -> None:
        images = []
        for img_path in glob.glob(f"{MAZE_DIRECTORY}/*.jpg"):
            images.append(mpimg.imread(img_path))
        plt.figure(figsize=(20, 10))
        columns = math.floor(math.sqrt(len(images)))
        for i, image in enumerate(images):
            plt.subplot(len(images) // columns + 1, columns, i + 1)
            plt.imshow(image)
            plt.axis("off")


class ComplexProblemGenerator(_MazeProblemGenerator):
    def __init__(self, problem_count: int, auto: bool = False):
        super().__init__(problem_count, auto)

    # @override
    def _generate_problem(self, maze: Maze) -> Problem:
        problem = self._reader.parse_problem("domains/maze.pddl")
        problem.name = "maze_problem"

        # Create objects
        x_objects = [Object(f"x{i}", problem.user_type(POSITION)) for i in range(TILE_COUNT)]
        y_objects = [Object(f"y{i}", problem.user_type(POSITION)) for i in range(TILE_COUNT)]
        direction_objects = [Object(direction, problem.user_type("direction")) for direction in DIRECTIONS]
        problem.add_objects(x_objects + y_objects + direction_objects)

        # Set initial value for fluents
        # inc(?a ?b) from x0->x9, y0->y9 := true
        for i in range(1, TILE_COUNT):
            problem.set_initial_value(problem.fluent(INC)(x_objects[i - 1], x_objects[i]), True)
            problem.set_initial_value(problem.fluent(INC)(y_objects[i - 1], y_objects[i]), True)

        # dec(?a ?b) from x9->x0 y9->y0 := true
        for i in range(1, TILE_COUNT):
            problem.set_initial_value(problem.fluent(DEC)(x_objects[i], x_objects[i - 1]), True)
            problem.set_initial_value(problem.fluent(DEC)(y_objects[i], y_objects[i - 1]), True)

        # path(?x ?y) for all tiles in maze := true
        for tile in maze.tiles:
            x, y = tile.get_position()
            problem.set_initial_value(problem.fluent(PATH)(x_objects[x], y_objects[y]), True)

        # is-{d}(?d) for all directions := true
        for i in range(len(DIRECTIONS)):
            problem.set_initial_value(problem.fluent(DIRECTION_CONDITIONS[i])(direction_objects[i]), True)

        # right-rot(?d ?dn) for all directions, where dn is the direction to the right := true
        for i in range(len(DIRECTIONS)):
            problem.set_initial_value(problem.fluent(RIGHT_ROT)(
                direction_objects[i],
                direction_objects[i + 1 if i + 1 < len(DIRECTIONS) else 0]
            ), True)

        # left-rot(?d ?dn) for all directions, where dn is the direction to the left := true
        for i in range(len(DIRECTIONS)):
            problem.set_initial_value(problem.fluent(LEFT_ROT)(
                direction_objects[i],
                direction_objects[i - 1 if i - 1 >= 0 else len(DIRECTIONS) - 1]
            ), True)

        # facing(?d) ?d = north := true
        problem.set_initial_value(problem.fluent(FACING)(direction_objects[0]), True)

        # start: at(?s_x ?s_y) := true
        s_x, s_y = maze.start.get_position()
        problem.set_initial_value(problem.fluent(AT)(x_objects[s_x], y_objects[s_y]), True)

        # goal: at(g_x g_y)
        g_x, g_y = maze.goal.get_position()
        problem.add_goal(problem.fluent(AT)(x_objects[g_x], y_objects[g_y]))

        return problem


class PartiallySolvedProblemGenerator(_MazeProblemGenerator):
    def __init__(self, problem_count: int, auto: bool = False):
        super().__init__(problem_count, auto)

    # @override
    def _generate_problem(self, maze: Maze) -> Problem:
        self._tile_object_mapping = {}
        self._maze = maze
        self._pointer = 0

        # Problem set-up
        self._problem = self._reader.parse_problem("domains/flattened_maze.pddl")
        self._problem.name = "maze_problem"

        self._start_object = Object("start", self._problem.user_type(POSITION))
        self._goal_object = Object("goal", self._problem.user_type(POSITION))

        self._problem.add_object(self._start_object)
        self._problem.add_object(self._goal_object)

        self._problem.set_initial_value(self._problem.fluent(AT)(self._start_object), True)
        self._problem.add_goal(self._problem.fluent(AT)(self._goal_object))

        self._dfs(self._maze.start, self._start_object)
        return self._problem

    # Performs depth-first search to locate paths along the maze
    def _dfs(self, current_tile: Tile, current_object: Object):

        # Ensure no tile is visited twice
        self._add_mapping(current_tile, current_object)
        current_position = current_tile.get_position()

        # Mapping of potential neighbour positions to maze tiles
        neighbour_map = {
            f"u{self._pointer}": self._find_tile((current_position[0], current_position[1] - 1)),
            f"d{self._pointer}": self._find_tile((current_position[0], current_position[1] + 1)),
            f"l{self._pointer}": self._find_tile((current_position[0] - 1, current_position[1])),
            f"r{self._pointer}": self._find_tile((current_position[0] + 1, current_position[1])),
        }

        for direction, neighbour in neighbour_map.items():
            if neighbour is not None:
                existing_mapping = [
                    obj for obj in self._get_mapping(neighbour)
                    if obj.name[0] == direction[0] or obj == self._start_object or obj == self._goal_object
                ]
                if existing_mapping:
                    self._problem.set_initial_value(
                        self._problem.fluent(PATH)(current_object, existing_mapping[0]), True
                    )
                    continue

                # Create object for neighbour tile
                if neighbour == self._maze.start:
                    neighbour_object = self._start_object
                elif neighbour == self._maze.goal:
                    neighbour_object = self._goal_object
                else:
                    neighbour_object = Object(direction, self._problem.user_type(POSITION))
                    self._problem.add_object(neighbour_object)

                # path(?x ?xn) to neighbour tile (xn) := true
                self._problem.set_initial_value(
                    self._problem.fluent(PATH)(current_object, neighbour_object), True
                )

                # Avoid repeating object names
                self._pointer += 1
                self._dfs(neighbour, neighbour_object)

    # Locates the tile object given its position in the maze
    def _find_tile(self, neighbour_position):
        signal = [p for p in self._maze.tiles if p.get_position() == neighbour_position]
        return signal[0] if signal else None
