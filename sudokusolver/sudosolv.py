import os

def solve_sudoku(board):
    """
    Solves a Sudoku puzzle using backtracking
    
    Args:
        board: 9x9 list of lists with 0 representing empty cells
        
    Returns:
        True if solved, False if no solution exists
    """
    # Find the next empty cell (represented by 0)
    empty_cell = find_empty(board)
    
    # If no empty cell is found, the puzzle is solved
    if not empty_cell:
        return True
    
    row, col = empty_cell
    
    # Try numbers 1-9
    for num in range(1, 10):
        # Check if the number is valid in this position
        if is_valid(board, num, (row, col)):
            # Place the number if valid
            board[row][col] = num
            
            # Recursively try to solve the rest of the puzzle
            if solve_sudoku(board):
                return True
            
            # If placing this number didn't lead to a solution, backtrack
            board[row][col] = 0
    
    # No number works in this position, so return False
    return False


def find_empty(board):
    """
    Finds the next empty cell in the board
    
    Args:
        board: 9x9 list of lists
        
    Returns:
        Tuple (row, col) of empty cell, or None if no empty cells
    """
    for i in range(9):
        for j in range(9):
            if board[i][j] == 0:
                return (i, j)
    return None


def is_valid(board, num, pos):
    """
    Checks if placing num at pos is valid according to Sudoku rules
    
    Args:
        board: 9x9 list of lists
        num: Number to check
        pos: Tuple (row, col) of the position to check
        
    Returns:
        True if valid, False otherwise
    """
    row, col = pos
    
    # Check row
    for i in range(9):
        if board[row][i] == num and i != col:
            return False
    
    # Check column
    for i in range(9):
        if board[i][col] == num and i != row:
            return False
    
    # Check 3x3 box
    box_row = row // 3
    box_col = col // 3
    
    for i in range(box_row * 3, box_row * 3 + 3):
        for j in range(box_col * 3, box_col * 3 + 3):
            if board[i][j] == num and (i, j) != pos:
                return False
    
    return True


def read_puzzle_from_file(filename):
    """
    Reads a Sudoku puzzle from a text file with 9 rows of 9 digits (0 for empty).
    
    Args:
        filename: Path to the file containing the puzzle
        
    Returns:
        9x9 list of lists representing the puzzle, or None if file doesn't exist
    """
    try:
        board = []
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if len(line) == 9 and line.isdigit():
                    row = [int(digit) for digit in line]
                    board.append(row)
                else:
                    # Skip lines that don't match the expected format
                    continue
                    
        # Ensure we have exactly 9 rows
        if len(board) == 9:
            return board
        else:
            return None
            
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading puzzle from file: {e}")
        return None


def print_board(board):
    """
    Prints the Sudoku board in a readable format
    """
    for i in range(9):
        if i % 3 == 0 and i != 0:
            print("-" * 21)
        
        for j in range(9):
            if j % 3 == 0 and j != 0:
                print("|", end=" ")
            
            if j == 8:
                print(board[i][j])
            else:
                print(board[i][j], end=" ")


def main():
    # Default puzzle (used if file doesn't exist or is invalid)
    default_puzzle = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9]
    ]
    
    # Try to read puzzle from file
    puzzle_file = "sd0.txt"
    if os.path.exists(puzzle_file):
        print(f"Reading puzzle from {puzzle_file}...")
        puzzle = read_puzzle_from_file(puzzle_file)
        
        if puzzle is None:
            print(f"Could not read puzzle from {puzzle_file}. Using default puzzle.")
            puzzle = [row[:] for row in default_puzzle]  # Create a copy
        else:
            print(f"Successfully read puzzle from {puzzle_file}.")
    else:
        print(f"{puzzle_file} not found. Using default puzzle.")
        puzzle = [row[:] for row in default_puzzle]  # Create a copy
    
    print("\nOriginal Puzzle:")
    print_board(puzzle)
    
    if solve_sudoku(puzzle):
        print("\nSolved Puzzle:")
        print_board(puzzle)
    else:
        print("No solution exists for this puzzle.")


if __name__ == "__main__":
    main()

