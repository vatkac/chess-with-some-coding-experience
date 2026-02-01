from enum import Enum
from abc import ABC, abstractmethod
import pygame
import sys
from tkinter import Tk
from tkinter import messagebox


class Color(Enum):
    WHITE = 0
    BLACK = 1

# Constants:
WINDOW_SIDE = 600
COLORS = [(184, 134, 99), (133, 87, 54)]
SQUARE_SIDE = WINDOW_SIDE // 8
PIECE_SIZE = SQUARE_SIDE * 0.9

board = [[None for _ in range(8)] for _ in range(8)]
move = 1
flipped = False

class InvalidNotationError(Exception): 
    def __init__(self, notation: str):
        super().__init__(f"Notation {notation} is invalid. Check it and try again.")

class CoordinatesHelper:
    @staticmethod
    def is_valid_notation(notation: str, raise_error=False) -> bool:
        is_valid = len(notation) == 2 \
                   and notation[1].isdigit() \
                   and int(notation[1]) <= 8 \
                   and notation[0] in "abcdefgh"
        if not is_valid and raise_error: raise InvalidNotationError(notation)
        return is_valid
    
    @staticmethod
    def notation_to_board(notation: str):
        CoordinatesHelper.is_valid_notation(notation, raise_error=True)

        row: int = 8 - int(notation[1])
        column: int = "abcdefgh".index(notation[0])

        return row, column
    
    @staticmethod
    def board_to_notation(coordinates: tuple[int, int]):
        row: int = str(8 - coordinates[0])
        column: int = "abcdefgh"[coordinates[1]]

        return column + row
    
    @staticmethod
    def board_to_real(board_coordinates: tuple[int, int]) -> tuple[int, int]:
        x = board_coordinates[1] * SQUARE_SIDE + SQUARE_SIDE // 2
        y = board_coordinates[0] * SQUARE_SIDE + SQUARE_SIDE // 2

        return x, y
    
    @staticmethod
    def real_to_board(real_coordinates: tuple[int, int]) -> tuple[int, int]:
        x = real_coordinates[1] // SQUARE_SIDE
        y = real_coordinates[0] // SQUARE_SIDE

        return x, y

# Common piece logic:
class Piece(ABC, pygame.sprite.Sprite):
    def __init__(self, color: Color, notation: str, short_name: str, king: pygame.sprite.Sprite):
        super().__init__()
        image: pygame.Surface = pygame.image.load(f"pieces/{color.name.lower()}/{short_name}.png")
        
        self.image: pygame.Surface = pygame.transform.smoothscale(image, (PIECE_SIZE, PIECE_SIZE))
        self.rect: pygame.Rect = self.image.get_rect()
        
        self.color = color
        self.position: tuple[int, int] | None = None
        self.real_position: tuple[int, int] | None = None
        self.first_move: int = None
        self.king = king

        self.move_to(CoordinatesHelper.notation_to_board(notation))
    
    def move_to(self, coordinates: tuple[int, int], check_legality=True) -> bool:
        if self.position and check_legality:
            is_legal, killed = self.is_legal_move(coordinates)
            if not is_legal: return False
            if not self.first_move: self.first_move = move
        elif not self.position:
            self.position = coordinates
            board[self.position[0]][self.position[1]] = None
            board[self.position[0]][self.position[1]] = self
            self.real_position = self.rect.center
            self.rect.center = CoordinatesHelper.board_to_real(coordinates)
            return True
        else:
            killed = None
        
        virtual_board = board
        virtual_board[self.position[0]][self.position[1]] = None
        virtual_board[coordinates[0]][coordinates[1]] = self

        tmp = self.position
        self.position = coordinates
        
        if ChessHelper.is_king_checked(self.king, virtual_board):
            self.position = tmp
            return False

        if killed: killed.kill()
        board[self.position[0]][self.position[1]] = None
        board[self.position[0]][self.position[1]] = self
        self.real_position = self.rect.center
        self.rect.center = CoordinatesHelper.board_to_real(coordinates)

        return True
    
    def get_info_for_checking(self, coordinates: tuple[int, int]) -> tuple[int, int, int, int, None | pygame.sprite.Sprite, bool, int, int]:
        new_row, new_column = coordinates
        cur_row, cur_column = self.position
        
        new_place = board[new_row][new_column]
        row_diff = new_row - cur_row
        col_diff = new_column - cur_column

        return new_row, new_column, cur_row, cur_column, new_place, row_diff, col_diff
    @abstractmethod
    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        raise NotImplementedError()
    
    def __repr__(self):
        return self.__class__.__name__ + " at " + CoordinatesHelper.board_to_notation(self.position)

class Pawn(Piece):
    def __init__(self, color, notation, short_name, king, pieces: pygame.sprite.Group):
        super().__init__(color, notation, short_name, king)
        self._dir = -1 if color is Color.WHITE else 1  # dir = direction
        self._pieces = pieces
    
    def move_to(self, coordinates):
        result = super().move_to(coordinates)
        if self.position[0] in {0, 7}:
            queen = Queen(self.color, CoordinatesHelper.board_to_notation(self.position), "Q")
            self._pieces.add(queen)
            board[self.position[0]][self.position[1]] = queen
            self.kill()
        return result

    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        _, new_column, cur_row, _, new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)

        # Normal move
        if not new_place and col_diff == 0:
            if row_diff == 1 * self._dir:
                return True, None
            if row_diff == 2 * self._dir and not self.first_move:
                return True, None
        
        # Eating
        if abs(col_diff) == 1 and row_diff == 1 * self._dir:
            # Normal eating
            if new_place and new_place.color != self.color:
                return True, new_place
            # En passant
            possible = board[cur_row][new_column]
            if cur_row in {3, 4} and isinstance(possible, Pawn) and possible.color != self.color and possible.first_move == move - 1:
                return True, possible
        return False, None

class Knight(Piece):
    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)[-3:]
        if {abs(row_diff), abs(col_diff)} == {1, 2} and (new_place is None or new_place.color != self.color):
            return True, new_place
        return False, None

class Rook(Piece):
    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        new_row, new_column, cur_row, cur_column, new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)
        if new_place is not None and new_place.color == self.color: return False, None

        if row_diff == 0 and col_diff != 0:
            direction = (0, -1) if new_column < cur_column else (0, 1)
        elif row_diff != 0 and col_diff == 0:
            direction = (-1, 0) if new_row < cur_row else (1, 0)
        else: return False, None

        if ChessHelper.check_way(self.position, direction, abs(row_diff + col_diff) - 1): return True, new_place
        return False, None

class Bishop(Piece):
    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        new_row, new_column, cur_row, cur_column, new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)
        if new_place is not None and new_place.color == self.color: return False, None

        if row_diff == col_diff and row_diff != 0:
            direction = (-1, -1) if new_column < cur_column and new_row < cur_row else (1, 1)
        elif abs(row_diff) == abs(col_diff):
            direction = (1, -1) if new_column < cur_column else (-1, 1)
        else: return False, None

        if ChessHelper.check_way(self.position, direction, abs(row_diff) - 1): return True, new_place
        return False, None

class Queen(Piece):
    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        new_row, new_column, cur_row, cur_column, new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)
        if new_place is not None and new_place.color == self.color: return False, None

        if row_diff == col_diff and row_diff != 0:
            direction = (-1, -1) if new_column < cur_column and new_row < cur_row else (1, 1)
        elif abs(row_diff) == abs(col_diff):
            direction = (1, -1) if new_column < cur_column else (-1, 1)
        elif row_diff == 0 and col_diff != 0:
            direction = (0, -1) if new_column < cur_column else (0, 1)
        elif row_diff != 0 and col_diff == 0:
            direction = (-1, 0) if new_row < cur_row else (1, 0)
        else: return False, None

        iterations = abs(row_diff) - 1 if abs(row_diff) == abs(col_diff) else abs(row_diff + col_diff) - 1
        if ChessHelper.check_way(self.position, direction, iterations): return True, new_place
        return False, None

class King(Piece):
    def __init__(self, color, notation, short_name):
        self._castled = False
        self._castled_rook_position: tuple[Rook | None, tuple[int, int] | None] = (None, None)
        super().__init__(color, notation, short_name, self)

    def move_to(self, coordinates):
        result = super().move_to(coordinates)
        if self._castled == False and self._castled_rook_position[0] is not None:
            self._castled = True
            rook, position = self._castled_rook_position
            rook.move_to(position, check_legality=False)
        return result

    def is_legal_move(self, coordinates: tuple[int, int]) -> tuple[bool, pygame.sprite.Sprite | None]:
        _, new_column, _, _, new_place, row_diff, col_diff = self.get_info_for_checking(coordinates)
        if new_place is not None and new_place.color == self.color: return False, None
        
        # Normal move
        if abs(max((row_diff, col_diff), key=abs)) == 1:
            return True, new_place
        
        # Castling
        is_castling = self.first_move == None and abs(col_diff) == 2 \
                      and ChessHelper.check_way((0, col_diff // 2), 2 + (col_diff < 0)) \
                      and isinstance(possible_rook := board[self.position[0]][0 if col_diff < 0 else 7], Rook) \
                      and possible_rook.first_move == None
        
        if is_castling:
            rook_pos = (self.position[0], new_column + (1 if col_diff < 0 else -1))
            self._castled_rook_position = (possible_rook, rook_pos)
            return True, new_place
        return False, None

class ChessHelper:
    @staticmethod
    def check_way(pos: tuple[int, int], direction: tuple[int, int], iterations: int=7, additional_info: bool=False, board: list[list[None]]=board) -> bool | tuple[bool, Piece]:
        try:
            counter = 0
            for _ in range(iterations):
                pos = (pos[0] + direction[0], pos[1] + direction[1])
                if -1 in pos: break
                counter += 1
                if board[pos[0]][pos[1]]: return (False, board[pos[0]][pos[1]], counter) if additional_info else False
        except IndexError: pass
        return (True, None, counter) if additional_info else True
    
    @staticmethod
    def _knights_around_point(position: tuple[int, int], color: Color, board: list[list[None | Piece]]=board) -> bool:
        y, x = position
        possible_knight_positions = set()

        if y < 6 and x < 7: possible_knight_positions.add((y + 2, x + 1))
        if y < 6 and x > 0: possible_knight_positions.add((y + 2, x - 1))
        if y > 1 and x < 7: possible_knight_positions.add((y - 2, x + 1))
        if y > 1 and x > 0: possible_knight_positions.add((y - 2, x - 1))
        if x < 6 and y < 7: possible_knight_positions.add((y + 1, x + 2))
        if x > 1 and y < 7: possible_knight_positions.add((y + 1, x - 2))
        if x < 6 and y > 0: possible_knight_positions.add((y - 1, x + 2))
        if x > 1 and y > 0: possible_knight_positions.add((y - 1, x - 2))
        
        for y, x in possible_knight_positions:
            cell = board[y][x]
            if isinstance(cell, Knight) and cell.color is color:
                return True
        return False

    @staticmethod
    def is_king_checked(king: King, board: list[list[None | Piece]]=board):
        position = king.position
        enemy_color = Color.BLACK if king.color is Color.WHITE else Color.WHITE
        
        for direction in {(-1, -1), (1, 1), (1, -1), (-1, 1)}:
            is_free, piece, checked_cells = ChessHelper.check_way(position, direction, additional_info=True, board=board)
            if not is_free and piece.color == enemy_color \
            and (isinstance(piece, (Bishop, Queen)) or isinstance(piece, Pawn) \
            and checked_cells == 1 and direction in {(1, 1), (-1, 1)}):
                return True
        
        for direction in {(0, 1), (0, -1), (1, 0), (-1, 0)}:
            is_free, piece, _ = ChessHelper.check_way(position, direction, additional_info=True, board=board)
            if not is_free and piece.color == enemy_color and isinstance(piece, (Rook, Queen)):
                return True
        return ChessHelper._knights_around_point(position, enemy_color, board)

def draw_board(surface: pygame.surface.Surface) -> list[pygame.Rect]:
    for i in range(8):
        for j in range(8):
            cur_color = j % 2 != i % 2
            x, y = SQUARE_SIDE * j, SQUARE_SIDE * i
    
            square = pygame.Rect(x, y, SQUARE_SIDE, SQUARE_SIDE)
            pygame.draw.rect(surface, COLORS[cur_color], square, 0)

def recalculate_to_flip(piece: pygame.sprite.Sprite) -> tuple[int, int]:
    x, y = piece.rect.center
    return (WINDOW_SIDE - x, WINDOW_SIDE - y) if not flipped else piece.real_position

def flip_board(pieces: pygame.sprite.Group):  # Note: flipping is just a visual effect, it doesn't affect anything else
    global flipped
    for piece in pieces:
        piece.rect.center = recalculate_to_flip(piece)
    flipped = not flipped


Tk().wm_withdraw()
need_to_flip_board = messagebox.askyesno(message="Flip the board after the moves?")

pygame.init()
screen = pygame.display.set_mode((WINDOW_SIDE, WINDOW_SIDE))
pygame.display.set_caption("Chess")
background = pygame.surface.Surface((WINDOW_SIDE, WINDOW_SIDE))


# --- SETUP BOARD ---
draw_board(background)
pieces_group = pygame.sprite.Group()

wk = King(color=Color.WHITE, notation="e1", short_name="K")
bk = King(color=Color.BLACK, notation="e8", short_name="K")
wq = Queen(color=Color.WHITE, notation="d1", king=wk, short_name="Q")
bq = Queen(color=Color.BLACK, notation="d8", king=bk, short_name="Q")
pieces_group.add(wq, bq, wk, bk)

for i in "abcdefgh":
    pawn = Pawn(color=Color.WHITE, notation=i + "2", short_name="P", king=wk, pieces=pieces_group)
    pieces_group.add(pawn)
    pawn = Pawn(color=Color.BLACK, notation=i + "7", short_name="P", king=bk, pieces=pieces_group)
    pieces_group.add(pawn)
pygame.display.set_icon(pawn.image)

wn1 = Knight(color=Color.WHITE, notation="b1", king=wk, short_name="N")
wn2 = Knight(color=Color.WHITE, notation="g1", king=wk, short_name="N")
bn1 = Knight(color=Color.BLACK, notation="b8", king=bk, short_name="N")
bn2 = Knight(color=Color.BLACK, notation="g8", king=bk, short_name="N")
pieces_group.add(wn1, wn2, bn1, bn2)

wr1 = Rook(color=Color.WHITE, notation="a1", king=wk, short_name="R")
wr2 = Rook(color=Color.WHITE, notation="h1", king=wk, short_name="R")
br1 = Rook(color=Color.BLACK, notation="a8", king=bk, short_name="R")
br2 = Rook(color=Color.BLACK, notation="h8", king=bk, short_name="R")
pieces_group.add(wr1, wr2, br1, br2)

wb1 = Bishop(color=Color.WHITE, notation="c1", king=wk, short_name="B")
wb2 = Bishop(color=Color.WHITE, notation="f1", king=wk, short_name="B")
bb1 = Bishop(color=Color.BLACK, notation="c8", king=bk, short_name="B")
bb2 = Bishop(color=Color.BLACK, notation="f8", king=bk, short_name="B")
pieces_group.add(wb1, wb2, bb1, bb2)

selected_piece = None
turn = Color.WHITE


# --- GAME ---
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if e.type == pygame.MOUSEBUTTONDOWN:
            coordinates = CoordinatesHelper.real_to_board(e.pos if not flipped else (WINDOW_SIDE - e.pos[0], WINDOW_SIDE - e.pos[1]))
            cell: Pawn = board[coordinates[0]][coordinates[1]]
            if selected_piece and selected_piece.move_to(coordinates):
                selected_piece = None
                turn = Color.BLACK if turn is Color.WHITE else Color.WHITE
                move += 1
                print(ChessHelper.is_king_checked(wk))
                if need_to_flip_board: flip_board(pieces_group)
            elif cell and cell.color == turn:
                selected_piece = cell
    
    screen.blit(background, (0, 0))
    pieces_group.draw(screen)
    pieces_group.update()
    pygame.display.flip()
