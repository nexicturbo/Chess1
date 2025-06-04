import multiprocess
from stockfish import Stockfish
import pyautogui
import time
import sys
import os
import chess
import re
import random
from grabbers.chesscom_grabber import ChesscomGrabber
from grabbers.lichess_grabber import LichessGrabber
from utilities import char_to_num
import keyboard

class StockfishBot(multiprocess.Process):
    def __init__(self, chrome_url, chrome_session_id, website, pipe, overlay_queue, stockfish_path, 
                 enable_manual_mode, enable_mouseless_mode, human_mode, enable_non_stop_puzzles, bongcloud, slow_mover,
                 skill_level, stockfish_depth, memory, cpu_threads, tournament_mode=False, premoves_mode=False):
        multiprocess.Process.__init__(self)
        self.chrome_url = chrome_url
        self.chrome_session_id = chrome_session_id
        self.website = website
        self.pipe = pipe
        self.overlay_queue = overlay_queue
        self.stockfish_path = stockfish_path
        self.enable_manual_mode = enable_manual_mode
        self.enable_mouseless_mode = enable_mouseless_mode
        self.human_mode = human_mode
        self.enable_non_stop_puzzles = enable_non_stop_puzzles
        self.bongcloud = bongcloud
        self.slow_mover = slow_mover
        self.skill_level = skill_level
        self.stockfish_depth = stockfish_depth
        self.memory = memory
        self.cpu_threads = cpu_threads
        self.tournament_mode = tournament_mode
        self.premoves_mode = premoves_mode
        self.grabber = None
        self.is_white = None
        self.board = None  # Add board as instance variable

        # Alias for clarity
        self.use_mouseless = enable_mouseless_mode

        # Initialize Stockfish engine with provided parameters
        self.stockfish = Stockfish(path=self.stockfish_path,
                                   depth=self.stockfish_depth,
                                   parameters={
                                       "Threads": self.cpu_threads,
                                       "Hash": self.memory,
                                   })
        self.stockfish.set_skill_level(self.skill_level)

        # Configure pyautogui for human-like movement
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

    def update_grabber(self):
        """Attach to the existing Chrome session and update helper info."""
        if self.website == "chesscom":
            self.grabber = ChesscomGrabber(self.chrome_url, self.chrome_session_id)
        else:
            self.grabber = LichessGrabber(self.chrome_url, self.chrome_session_id)
        self.grabber.update_board_elem()
        self.is_white = self.grabber.is_white()

    def get_stockfish_move(self):
        """Return the best move suggested by the Stockfish engine."""
        try:
            return self.stockfish.get_best_move()
        except Exception as e:  # pragma: no cover - just a safety net
            print(f"Error getting Stockfish move: {e}")
            return ""

    def wait_for_turn(self):
        """Block until it's our turn to move based on move count and color."""
        while True:
            try:
                moves = self.grabber.get_move_list() or []
                if (len(moves) % 2 == 0 and self.is_white) or (
                    len(moves) % 2 == 1 and not self.is_white
                ):
                    return
            except Exception:
                pass
            time.sleep(0.1)

    def move_to_screen_pos(self, square):
        """
        Completely rewritten method to convert chess square to screen coordinates
        Uses more reliable rect-based calculations
        """
        try:
            # Get board element
            board_elem = self.grabber._board_elem
            if not board_elem:
                print("Could not find board element")
                return None
                
            # Get board dimensions and position
            try:
                board_rect = board_elem.rect
            except:
                # If rect is not available, try getting location and size
                board_rect = {
                    'x': board_elem.location['x'],
                    'y': board_elem.location['y'],
                    'width': board_elem.size['width'],
                    'height': board_elem.size['height']
                }
            
            # For more reliable results, use JavaScript to calculate the exact square position
            try:
                js_coords = self.grabber.chrome.execute_script(f'''
                    try {{
                        // Find the board element
                        const boardElem = document.querySelector('.board-layout-chessboard, .board, .cg-wrap');
                        if (!boardElem) return null;
                        
                        // Get board dimensions
                        const rect = boardElem.getBoundingClientRect();
                        const boardWidth = rect.width;
                        const boardHeight = rect.height;
                        const squareSize = Math.min(boardWidth, boardHeight) / 8;
                        
                        // Get square position
                        const file = '{square[0]}'.charCodeAt(0) - 'a'.charCodeAt(0);  // 0-7
                        const rank = parseInt('{square[1]}') - 1;  // 0-7
                        
                        // Determine if we're playing as white or black
                        let orientation = 'white';
                        // Check multiple possible orientation attributes
                        const orientationAttr = boardElem.getAttribute('data-orientation') || 
                                               boardElem.getAttribute('data-board-orientation');
                        if (orientationAttr) orientation = orientationAttr;
                        
                        // Look for orientation classes
                        if (boardElem.classList.contains('orientation-black')) orientation = 'black';
                        
                        // Also check parent elements
                        const cgBoard = document.querySelector('cg-board');
                        if (cgBoard && cgBoard.classList.contains('orientation-black')) orientation = 'black';
                        
                        console.log("Board orientation detected:", orientation);
                        
                        // Calculate coordinates based on orientation
                        let x, y;
                        if (orientation === 'white') {{
                            // White's perspective
                            x = rect.left + (file * squareSize) + (squareSize / 2);
                            y = rect.top + (7 - rank) * squareSize + (squareSize / 2);
                        }} else {{
                            // Black's perspective
                            x = rect.left + (7 - file) * squareSize + (squareSize / 2);
                            y = rect.top + (rank * squareSize) + (squareSize / 2);
                        }}
                        
                        // Add small random offset
                        x += (Math.random() * 10) - 5;
                        y += (Math.random() * 10) - 5;
                        
                        return {{
                            x: x, 
                            y: y, 
                            boardWidth: boardWidth, 
                            boardHeight: boardHeight, 
                            squareSize: squareSize, 
                            orientation: orientation,
                            file: file,
                            rank: rank
                        }};
                    }} catch (e) {{
                        console.error("Error calculating square position:", e);
                        return null;
                    }}
                ''')
                
                if js_coords:
                    print(f"Square {square} JS coords: x={js_coords['x']}, y={js_coords['y']}, orientation={js_coords['orientation']} (file={js_coords['file']}, rank={js_coords['rank']})")
                    return (js_coords['x'], js_coords['y'])
            except Exception as e:
                print(f"JavaScript coordinate calculation failed: {e}")
            
            # Enhanced fallback to traditional calculation - run a different JS calculation first
            try:
                # Try a more direct approach to find squares by their attributes
                direct_coords = self.grabber.chrome.execute_script(f'''
                    try {{
                        // First try to find square directly - works on Lichess
                        const squareElement = document.querySelector('[data-key="{square}"]');
                        if (squareElement) {{
                            const rect = squareElement.getBoundingClientRect();
                            return {{
                                x: rect.left + rect.width/2,
                                y: rect.top + rect.height/2,
                                method: "direct"
                            }};
                        }}
                        
                        // Second approach - try to find by coordinates
                        const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
                        const file = files.indexOf('{square[0]}');
                        const rank = 8 - parseInt('{square[1]}');
                        
                        // Find all squares
                        const squares = document.querySelectorAll('.square');
                        for (const sq of squares) {{
                            const key = sq.getAttribute('data-key') || sq.getAttribute('data-square');
                            if (key === '{square}') {{
                                const rect = sq.getBoundingClientRect();
                                return {{
                                    x: rect.left + rect.width/2,
                                    y: rect.top + rect.height/2,
                                    method: "named"
                                }};
                            }}
                        }}
                        
                        // Find by coordinate
                        const board = document.querySelector('.cg-wrap, .board');
                        if (!board) return null;
                        
                        const boardRect = board.getBoundingClientRect();
                        const isFlipped = document.querySelector('.orientation-black') != null;
                        
                        const squareSize = boardRect.width / 8;
                        const x = isFlipped ? 
                            boardRect.left + squareSize * (7 - file) + squareSize/2 : 
                            boardRect.left + squareSize * file + squareSize/2;
                        const y = isFlipped ? 
                            boardRect.top + squareSize * (7 - rank) + squareSize/2 : 
                            boardRect.top + squareSize * rank + squareSize/2;
                        
                        return {{
                            x: x,
                            y: y,
                            method: "coordinates",
                            isFlipped: isFlipped
                        }};
                    }} catch (e) {{
                        console.error("Error in direct square finding:", e);
                        return null;
                    }}
                ''')
                
                if direct_coords:
                    print(f"Square {square} found directly: x={direct_coords['x']}, y={direct_coords['y']}, method={direct_coords.get('method', 'unknown')}")
                    return (direct_coords['x'], direct_coords['y'])
            except Exception as e:
                print(f"Direct square finding failed: {e}")
            
            # Fallback to traditional calculation
            board_width = board_rect['width']
            board_height = board_rect['height']
            
            # Calculate square size
            square_size = min(board_width, board_height) / 8
            
            # Convert square to coordinates (0-7)
            file = ord(square[0].lower()) - ord('a')
            rank = int(square[1]) - 1
            
            # Get accurate offset including scrolling
            x_offset = board_rect['x']
            y_offset = board_rect['y']
            
            # Adjust for player orientation
            if self.is_white:
                # White - a1 is at bottom left
                x = x_offset + (file * square_size) + (square_size / 2)
                y = y_offset + ((7 - rank) * square_size) + (square_size / 2)
            else:
                # Black - a1 is at top right
                x = x_offset + ((7 - file) * square_size) + (square_size / 2)
                y = y_offset + (rank * square_size) + (square_size / 2)
            
            # Add random offset to avoid clicking exact center
            x += random.uniform(-square_size/5, square_size/5)
            y += random.uniform(-square_size/5, square_size/5)
            
            print(f"Square {square} calculated coords: x={x}, y={y}")
            return (x, y)
            
        except Exception as e:
            print(f"Error calculating screen position: {e}")
            return None

    def get_move_pos(self, move):
        start_pos = self.move_to_screen_pos(move[0:2])
        end_pos = self.move_to_screen_pos(move[2:4])
        return start_pos, end_pos

    def human_move(self, start_pos, end_pos):
        # Add randomness for human-like movement
        time.sleep(random.uniform(0.1, 0.2))
        
        # Ensure our mouse is in the right state
        pyautogui.mouseUp()
        time.sleep(0.1)
        
        # Click piece - more robust clicking
        print(f"Clicking on start position: {start_pos}")
        pyautogui.moveTo(start_pos[0], start_pos[1], duration=0.1)
        time.sleep(0.2)
        pyautogui.click(start_pos[0], start_pos[1])
        time.sleep(0.3)
        
        # Move to destination with a smoother motion
        print(f"Moving to end position: {end_pos}")
        pyautogui.moveTo(end_pos[0], end_pos[1], duration=0.2)
        time.sleep(0.2)
        pyautogui.click(end_pos[0], end_pos[1])
        time.sleep(0.3)
        
        # If click-click didn't work, try a drag operation as fallback
        pyautogui.moveTo(start_pos[0], start_pos[1], duration=0.1)
        time.sleep(0.2)
        pyautogui.mouseDown(button='left')
        time.sleep(0.2)
        
        # Move in steps with slight randomness for more reliable drag
        steps = 7
        for i in range(1, steps + 1):
            t = i / steps
            x = start_pos[0] + (end_pos[0] - start_pos[0]) * t + random.uniform(-1, 1)
            y = start_pos[1] + (end_pos[1] - start_pos[1]) * t + random.uniform(-1, 1)
            pyautogui.moveTo(x, y, duration=0.03)
            
        # Release at destination
        time.sleep(0.1)
        pyautogui.mouseUp(button='left')
        time.sleep(0.2)

    def validate_move(self, move_str):
        """
        Validate a move before attempting to make it
        """
        try:
            # Check if it's a valid UCI move format
            if not re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', move_str):
                print(f"Invalid move format: {move_str}")
                return False
                
            # Check that it's legal in the current position
            chess_move = chess.Move.from_uci(move_str)
            if not self.board.is_legal(chess_move):
                print(f"Move {move_str} is not legal in current position")
                return False
                
            # Validate the coordinates - make sure we can find the squares
            from_pos = self.move_to_screen_pos(move_str[0:2])
            to_pos = self.move_to_screen_pos(move_str[2:4])
            
            if not from_pos or not to_pos:
                print(f"Could not find valid screen coordinates for {move_str}")
                return False
                
            return True
        except Exception as e:
            print(f"Error validating move {move_str}: {e}")
            return False

    def make_move(self, move_str):
        """
        Enhanced method to make a move with improved reliability
        """
        print(f"\nAttempting to make move: {move_str}")
        
        # First validate the move
        if not self.validate_move(move_str):
            print(f"Move validation failed for {move_str}, trying to get a new move")
            # If we're making an invalid move, try to get a new one from Stockfish
            try:
                legal_moves = list(self.board.legal_moves)
                if legal_moves:
                    random_move = random.choice(legal_moves).uci()
                    print(f"Selected alternative move: {random_move}")
                    move_str = random_move
                    # Revalidate the new move
                    if not self.validate_move(move_str):
                        return False
                else:
                    return False
            except Exception as e:
                print(f"Error selecting alternative move: {e}")
                return False
        
        # Check the current move count for later validation
        current_moves = self.grabber.get_move_list() or []
        current_move_count = len(current_moves)
            
        # For Lichess, first try the direct DOM manipulation method which is more reliable
        if self.website == "lichess":
            try:
                # Try direct DOM manipulation first
                if self.grabber.make_direct_dom_move(move_str):
                    # Sleep to allow the move to register
                    time.sleep(0.5)
                
                    # Check if move worked by counting moves
                    new_moves = self.grabber.get_move_list() or []
                    if len(new_moves) > current_move_count:
                        print("Direct DOM move successful!")
                        return True
                    
                # Try socket-based move as backup
                print("Direct DOM move failed, trying socket move...")
                if self.enable_mouseless_mode:
                    # Try mouseless mode using the socket
                    move_count = len(current_moves)
                    if self.grabber.make_mouseless_move(move_str, move_count, False):
                        time.sleep(0.5)
                        new_moves = self.grabber.get_move_list() or []
                        if len(new_moves) > current_move_count:
                            print("Socket-based move successful!")
                            return True
                else:
                    # Even if mouseless mode is not enabled, try it as a fallback
                    print("Trying mouseless move as fallback...")
                    if self.make_mouseless_move(move_str):
                        time.sleep(0.5)
                        new_moves = self.grabber.get_move_list() or []
                        if len(new_moves) > current_move_count:
                            print("Fallback mouseless move successful!")
                            return True
            except Exception as e:
                print(f"Lichess-specific move methods failed: {e}")
        
        # For Chess.com, try mouseless move first
        if self.website == "chesscom":
            try:
                print("Trying Chess.com mouseless move...")
                if self.make_mouseless_move(move_str):
                    time.sleep(0.5)
                    new_moves = self.grabber.get_move_list() or []
                    if len(new_moves) > current_move_count:
                        print("Chess.com mouseless move successful!")
                        return True
            except Exception as e:
                print(f"Chess.com mouseless move failed: {e}")
        
        # Get source and destination coordinates
        start_pos = self.move_to_screen_pos(move_str[0:2])
        end_pos = self.move_to_screen_pos(move_str[2:4])
            
        if not start_pos or not end_pos:
            print("Failed to get valid coordinates for move")
            return False
                
        print(f"Moving from {start_pos} to {end_pos}")
        
        # Try a new direct and reliable method - click exactly where Selenium says the pieces are
        try:
            # Try to directly click using Selenium-driven JavaScript which is more accurate than pyautogui
            js_piece_click = self.grabber.chrome.execute_script(f"""
                (function() {{
                    try {{
                        // Find the piece on starting square
                        const pieces = document.querySelectorAll('.piece');
                        let foundPiece = null;
                        for (const piece of pieces) {{
                            const square = piece.getAttribute('data-square') || piece.getAttribute('data-key');
                            if (square === '{move_str[0:2]}') {{
                                foundPiece = piece;
                                break;
                            }}
                        }}
                        
                        if (!foundPiece) {{
                            console.log('Could not find piece at {move_str[0:2]}');
                            return false;
                        }}
                        
                        // Find destination square
                        const destSquare = document.querySelector(`[data-square="{move_str[2:4]}"]`) || 
                                          document.querySelector(`[data-key="{move_str[2:4]}"]`);
                        if (!destSquare) {{
                            console.log('Could not find destination at {move_str[2:4]}');
                            return false;
                        }}
                        
                        // Get exact positions
                        const pieceRect = foundPiece.getBoundingClientRect();
                        const destRect = destSquare.getBoundingClientRect();
                        
                        return {{
                            pieceX: pieceRect.left + pieceRect.width/2,
                            pieceY: pieceRect.top + pieceRect.height/2,
                            destX: destRect.left + destRect.width/2,
                            destY: destRect.top + destRect.height/2
                        }};
                    }} catch (e) {{
                        console.error('Error getting exact piece position:', e);
                        return false;
                    }}
                }})();
            """)
            
            if js_piece_click:
                print(f"Found exact piece position: ({js_piece_click['pieceX']}, {js_piece_click['pieceY']}) to ({js_piece_click['destX']}, {js_piece_click['destY']})")
                
                # Click exactly where the piece is
                pyautogui.mouseUp() 
                time.sleep(0.2)
                
                # Move to and click on piece
                pyautogui.moveTo(js_piece_click['pieceX'], js_piece_click['pieceY'], duration=0.2)
                time.sleep(0.3)
                pyautogui.click(js_piece_click['pieceX'], js_piece_click['pieceY'])
                time.sleep(0.5)
                
                # Move to and click on destination
                pyautogui.moveTo(js_piece_click['destX'], js_piece_click['destY'], duration=0.2)
                time.sleep(0.3)
                pyautogui.click(js_piece_click['destX'], js_piece_click['destY'])
                time.sleep(0.5)
                
                # Check if move was successful
                new_moves = self.grabber.get_move_list() or []
                if len(new_moves) > current_move_count:
                    print("Direct piece click successful!")
                    return True
        except Exception as e:
            print(f"Error with direct piece clicking: {e}")
                
        # Try standard methods if the direct approach failed    
        try:
            # Try the old methods for maximum compatibility
            # First, use the human move method with reliability improvements
            self.human_move(start_pos, end_pos)
            
            # Check if move was successful
            time.sleep(0.5)
            new_moves = self.grabber.get_move_list() or []
            if len(new_moves) > current_move_count:
                print("Human move successful!")
                return True
                
            # Try simpler click-click method if human move failed
            print("Human move failed, trying simple method...")
            self.simple_move(start_pos, end_pos)
            
            # Check if move was successful
            time.sleep(0.5)
            new_moves = self.grabber.get_move_list() or []
            if len(new_moves) > current_move_count:
                print("Simple move successful!")
                return True
            
            # Handle promotion if needed
            if len(move_str) > 4:
                self.handle_promotion(move_str)
                time.sleep(1)
                
                # Check once more
                new_moves = self.grabber.get_move_list() or []
                if len(new_moves) > current_move_count:
                    print("Move with promotion successful!")
                    return True
            
            print("All move methods failed")
            return False
                
        except Exception as e:
            print(f"Error making move: {e}")
            return False

    def simple_move(self, start_pos, end_pos):
        """
        Simplified, more reliable movement sequence specifically for Chess.com
        """
        # Try the direct click-then-click method which works best on Chess.com
        try:
            # Clear any existing mouse state
            pyautogui.mouseUp()
            time.sleep(0.2)
            
            # Click on the starting position to select the piece
            pyautogui.click(start_pos[0], start_pos[1])
            time.sleep(0.3)
            
            # Now click on the destination to complete the move
            pyautogui.click(end_pos[0], end_pos[1])
            time.sleep(0.3)
            
            # If that doesn't work, try a direct drag operation
            pyautogui.click(start_pos[0], start_pos[1])
            time.sleep(0.2)
            pyautogui.dragTo(end_pos[0], end_pos[1], duration=0.3, button='left')
            time.sleep(0.3)
            
            return True
        except Exception as e:
            print(f"Simple move failed: {e}")
            return False

    def handle_promotion(self, move):
        """
        Handle piece promotion
        """
        time.sleep(0.8)  # Wait for promotion dialog
        
        promotion_piece = move[4]
        
        if self.website == "chesscom":
            try:
                # Try clicking on promotion piece
                end_pos = self.move_to_screen_pos(move[2:4])
                
                # First click on the square
                pyautogui.click(end_pos[0], end_pos[1])
                time.sleep(0.3)
                
                # Select piece based on promotion type
                if promotion_piece == 'q':  # Queen
                    pyautogui.click(end_pos[0], end_pos[1])  # Queen is usually default
                elif promotion_piece == 'r':  # Rook
                    pyautogui.click(end_pos[0], end_pos[1] + 70)
                elif promotion_piece == 'b':  # Bishop
                    pyautogui.click(end_pos[0], end_pos[1] + 140)
                elif promotion_piece == 'n':  # Knight
                    pyautogui.click(end_pos[0], end_pos[1] + 210)
            except Exception as e:
                print(f"Promotion handling failed: {e}")
        else:
            # Lichess handling
            if promotion_piece == "n":
                pos = self.move_to_screen_pos(move[2] + str(int(move[3]) - 1))
            elif promotion_piece == "r":
                pos = self.move_to_screen_pos(move[2] + str(int(move[3]) - 2))
            elif promotion_piece == "b":
                pos = self.move_to_screen_pos(move[2] + str(int(move[3]) - 3))
            else:  # Default to queen
                pos = self.move_to_screen_pos(move[2] + str(int(move[3])))
                
            if pos:
                pyautogui.moveTo(x=pos[0], y=pos[1])
                pyautogui.click(button='left')

    def wait_for_gui_to_delete(self):
        while self.pipe.recv() != "DELETE":
            pass

    def run(self):
        """
        Run the bot loop to play the game
        """
        # Initialize session recovery counters
        session_recovery_attempts = 0
        max_session_recovery_attempts = 3
        
        # Track move attempts for illegal move detection
        consecutive_failed_moves = 0
        max_failed_moves = 5
        last_attempted_move = None
        repeated_move_count = 0
        
        try:
            # Get initial board state
            self.update_grabber()
            
            # Wait for our turn if we're not white
            self.wait_for_turn()
            
            # Main game loop
            while True:
                try:
                    # Check if game is over
                    if self.grabber.is_game_over():
                        print("Game is over!")
                        # Notify the GUI that the game is over
                        if self.gui:
                            self.gui.on_game_over()
                        break
                    
                    # Check for connection issues
                    if self.detect_connection_issues():
                        print("Connection issues detected and handled, continuing...")
                        continue
                    
                    # Check for game abort or timeout conditions specific to Lichess
                    if self.website == "lichess":
                        try:
                            # Execute JS to check for game abort messages in DOM
                            abort_check_script = """
                            (function() {
                                // Check common abort messages
                                const body = document.body.innerText.toLowerCase();
                                if (body.includes('game aborted') || 
                                    body.includes('game over') ||
                                    body.includes('abandoned') ||
                                    body.includes('connection lost')) {
                                    return true;
                                }
                                
                                // Check abort elements
                                const abortElems = document.querySelectorAll('.game-abort, .game-over, .result-wrap');
                                if (abortElems.length > 0) {
                                    return true;
                                }
                                
                                return false;
                            })();
                            """
                            
                            is_aborted = self.grabber.chrome.execute_script(abort_check_script)
                            if is_aborted:
                                print("Game aborted detected via DOM check")
                                if self.gui:
                                    self.gui.on_game_over()
                                break
                        except Exception as e:
                            print(f"Error checking for game abort: {e}")
                    
                    # Get the current board state
                    moves = self.grabber.get_move_list()
                    
                    # Check for puzzle next button (if we're doing puzzles)
                    if self.grabber.is_game_puzzles():
                        print("Puzzle detected, clicking next...")
                        self.grabber.click_puzzle_next()
                    
                    # Wait for our turn
                    self.wait_for_turn()
                    
                    # Generate a move using stockfish
                    best_move = self.get_stockfish_move()
                    
                    # Skip if we couldn't get a move
                    if not best_move:
                        print("No valid move found, waiting...")
                        time.sleep(0.5)
                        continue
                    
                    print(f"Best move: {best_move}")
                    
                    # Check if we're trying the same move repeatedly
                    if best_move == last_attempted_move:
                        repeated_move_count += 1
                        print(f"Repeated move attempt {repeated_move_count} times: {best_move}")
                        
                        if repeated_move_count >= 3:
                            print("Detected move repetition, trying alternative move...")
                            # Force a different move by temporarily reducing search depth
                            backup_depth = self.stockfish.depth
                            self.stockfish.set_depth(2)  # Use shallow search for variety
                            alt_move = self.get_stockfish_move()
                            self.stockfish.set_depth(backup_depth)  # Restore depth
                            
                            if alt_move and alt_move != best_move:
                                print(f"Using alternative move: {alt_move}")
                                best_move = alt_move
                                repeated_move_count = 0
                    else:
                        repeated_move_count = 0
                    
                    last_attempted_move = best_move
                    
                    # Make the move
                    move_success = False
                    
                    # First try direct mouseless move
                    if self.use_mouseless and self.grabber.make_mouseless_move(best_move):
                        print("Made mouseless move successfully")
                        move_success = True
                    # Then try direct DOM move if mouseless failed
                    elif self.grabber.make_direct_dom_move(best_move):
                        print("Made direct DOM move successfully")
                        move_success = True
                    # Finally fall back to traditional mouse move method
                    else:
                        print("Falling back to traditional mouse moves")
                        self.make_move(best_move)
                        move_success = True  # Assume it worked for now
                    
                    # Check if the move was actually executed
                    time.sleep(0.5)  # Wait a bit for the move to be registered
                    new_moves = self.grabber.get_move_list()
                    
                    # If the move list hasn't changed, the move might have failed
                    if moves and new_moves and len(moves) == len(new_moves):
                        consecutive_failed_moves += 1
                        print(f"Move may have failed. Consecutive failures: {consecutive_failed_moves}")
                        
                        if consecutive_failed_moves >= max_failed_moves:
                            print("Too many failed moves. Checking if we can continue...")
                            
                            # Check if we're stuck in an illegal move loop
                            try:
                                # Execute JS to check if there are any error messages
                                error_check_script = """
                                (function() {
                                    // Check for common error messages
                                    const errorElems = document.querySelectorAll('.error, .bad, .nope');
                                    for (const elem of errorElems) {
                                        if (elem.innerText.toLowerCase().includes('illegal') || 
                                            elem.innerText.toLowerCase().includes('invalid') ||
                                            elem.innerText.toLowerCase().includes('not your turn')) {
                                            return {
                                                found: true,
                                                message: elem.innerText
                                            };
                                        }
                                    }
                                    
                                    // Check for toast notifications
                                    const toasts = document.querySelectorAll('.toast, .notification, .notify-app');
                                    for (const toast of toasts) {
                                        if (toast.innerText.toLowerCase().includes('illegal') || 
                                            toast.innerText.toLowerCase().includes('invalid') ||
                                            toast.innerText.toLowerCase().includes('not your turn')) {
                                            return {
                                                found: true,
                                                message: toast.innerText
                                            };
                                        }
                                    }
                                    
                                    // Check page text for error messages (broader approach)
                                    const bodyText = document.body.innerText.toLowerCase();
                                    const errorPhrases = [
                                        'illegal move', 
                                        'invalid move', 
                                        'not your turn', 
                                        'illegal position',
                                        'cannot move'
                                    ];
                                    
                                    for (const phrase of errorPhrases) {
                                        if (bodyText.includes(phrase)) {
                                            return {
                                                found: true,
                                                message: 'Found in page: ' + phrase
                                            };
                                        }
                                    }
                                    
                                    return {
                                        found: false
                                    };
                                })();
                                """
                                
                                error_result = self.grabber.chrome.execute_script(error_check_script)
                                if error_result and error_result.get('found'):
                                    print(f"Error message found: {error_result.get('message')}")
                                    print("Detected illegal move issue, resynchronizing board position")
                                    # Reset the board in Stockfish to match the website's actual state
                                    if self.reset_stockfish_to_current_position():
                                        print("Successfully resynchronized board position")
                                        consecutive_failed_moves = 0
                                        time.sleep(1)  # Wait a bit before continuing
                                        continue
                                    else:
                                        print("Failed to resynchronize board position")
                            except Exception as e:
                                print(f"Error checking for error messages: {e}")
                            
                            # If we reached this point, try clicking elsewhere to clear any dialogs
                            try:
                                print("Trying to clear any dialogs...")
                                js_clear_script = """
                                (function() {
                                    // Try to click at an empty area of the page
                                    const event = new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window,
                                        clientX: 10,
                                        clientY: 10
                                    });
                                    document.body.dispatchEvent(event);
                                    
                                    // Try to find and click any close buttons
                                    const closeButtons = document.querySelectorAll('.close, .cancel, .dismiss');
                                    for (const button of closeButtons) {
                                        button.click();
                                    }
                                    
                                    return true;
                                })();
                                """
                                self.grabber.chrome.execute_script(js_clear_script)
                                time.sleep(0.5)
                            except Exception as clear_error:
                                print(f"Error clearing dialogs: {clear_error}")
                            
                            # Try to refresh the page as a last resort
                            print("Attempting to refresh the page...")
                            try:
                                self.grabber.chrome.refresh()
                                time.sleep(3)  # Wait for page to reload
                                self.update_grabber()
                                consecutive_failed_moves = 0
                            except Exception as refresh_error:
                                print(f"Error refreshing page: {refresh_error}")
                                break  # Break out of the main loop if refresh fails
                    else:
                        consecutive_failed_moves = 0  # Reset counter on successful move
                    
                    # Wait a bit before looping
                    time.sleep(0.5)
                    
                except Exception as e:
                    error_message = str(e)
                    print(f"Error during game: {error_message}")
                    
                    # Check if this is a session related error
                    if "session id" in error_message.lower() or "no such session" in error_message.lower():
                        session_recovery_attempts += 1
                        print(f"Session error detected. Recovery attempt {session_recovery_attempts} of {max_session_recovery_attempts}")
                        
                        if session_recovery_attempts <= max_session_recovery_attempts:
                            # First try to detect and handle connection issues
                            try:
                                print("Checking for connection issues first...")
                                if self.detect_connection_issues():
                                    print("Connection issues detected and handled successfully")
                                    time.sleep(1)
                                    continue
                            except Exception as connection_error:
                                print(f"Error checking for connection issues: {connection_error}")
                            
                            # If connection recovery failed, try to reconnect to the Chrome session
                            try:
                                print("Attempting to reconnect to Chrome session...")
                                self.grabber = self.create_grabber()
                                self.update_grabber()
                                print("Successfully reconnected to Chrome session!")
                                time.sleep(1)
                                continue  # Skip to the next iteration
                            except Exception as reconnect_error:
                                print(f"Failed to reconnect: {reconnect_error}")
                        else:
                            print("Maximum session recovery attempts reached. Stopping.")
                            if self.gui:
                                self.gui.on_error("Session recovery failed after multiple attempts.")
                            break
                    else:
                        # For non-session errors, try connection recovery anyway
                        try:
                            if self.detect_connection_issues():
                                print("Connection issues detected and handled for non-session error")
                                time.sleep(1)
                                continue
                        except Exception:
                            pass
                            
                        # Log and continue
                        print("Non-session error. Continuing...")
                        time.sleep(1)
                        
        except Exception as e:
            print(f"Error in main loop: {e}")
            if self.gui:
                self.gui.on_error(f"Error: {str(e)}")
                
    def reset_stockfish_to_current_position(self):
        """
        Resets the Stockfish board to match the current position on the website
        Useful when desynchronization happens due to illegal moves
        """
        try:
            # Get the FEN from the website via JavaScript
            fen_script = """
            (function() {
                // Try different methods to get the FEN from the page
                
                // Method 1: Check if lichess chess object is available
                if (window.lichess && window.lichess.analyse && window.lichess.analyse.getFen) {
                    return window.lichess.analyse.getFen();
                }
                
                // Method 2: Try to get it from the board data attribute
                const board = document.querySelector('cg-board');
                if (board && board.getAttribute('data-fen')) {
                    return board.getAttribute('data-fen');
                }
                
                // Method 3: Check if it's in a hidden input (some sites do this)
                const fenInput = document.querySelector('input[data-fen]');
                if (fenInput) {
                    return fenInput.getAttribute('data-fen');
                }
                
                // Method 4: For Lichess, try to get it from the game state
                if (window.lichess && window.lichess.socket && window.lichess.socket.ws) {
                    // Try to get the game state
                    const gameState = document.querySelector('chess-board')?.getAttribute('fen');
                    if (gameState) {
                        return gameState;
                    }
                }
                
                // Return null if we can't find it
                return null;
            })();
            """
            
            fen = self.grabber.chrome.execute_script(fen_script)
            
            if fen:
                print(f"Found position FEN: {fen}")
                # Reset Stockfish with this position
                self.stockfish.set_position(fen=fen)
                print("Stockfish position reset to match the board")
                return True
            else:
                print("Couldn't find FEN position from the website")
                
                # Fallback to using the move list
                moves = self.grabber.get_move_list()
                if moves:
                    print(f"Using move list to reset position: {moves}")
                    # Reset Stockfish to starting position
                    self.stockfish.reset_board()
                    # Apply each move
                    for move in moves:
                        try:
                            # Check if move is in the right format for Stockfish
                            if re.match(r'^[a-h][1-8][a-h][1-8][qrbnQRBN]?$', move):
                                self.stockfish.make_moves_from_current_position([move])
                            else:
                                # Try to convert algebraic notation (e.g. "e4") to UCI format
                                # This is a simplified conversion - only works for basic moves
                                print(f"Converting algebraic move: {move}")
                                # Get current position as a chess.Board
                                board = chess.Board(self.stockfish.get_fen_position())
                                
                                # Try to parse the move
                                try:
                                    uci_move = None
                                    # Try parsing as SAN
                                    try:
                                        chess_move = board.parse_san(move)
                                        uci_move = chess_move.uci()
                                    except ValueError:
                                        # If not SAN, try as UCI
                                        try:
                                            chess_move = board.parse_uci(move)
                                            uci_move = move
                                        except ValueError:
                                            print(f"Could not parse move: {move}")
                                            continue
                                    
                                    print(f"Converted to UCI: {uci_move}")
                                    self.stockfish.make_moves_from_current_position([uci_move])
                                except Exception as parse_error:
                                    print(f"Error parsing move {move}: {parse_error}")
                        except Exception as move_error:
                            print(f"Error applying move {move}: {move_error}")
                    return True
                
                return False
        except Exception as e:
            print(f"Error resetting Stockfish position: {e}")
            return False

    def make_mouseless_move(self, move_str, pre_move=False):
        """
        Enhanced helper method to make mouseless moves on both platforms
        """
        try:
            # For Chess.com
            if self.website == "chesscom":
                # Try a more direct approach via JavaScript
                print("Attempting mouseless move on Chess.com...")
                
                # Parse the move and convert to Chess.com format
                from_square = move_str[0:2]
                to_square = move_str[2:4]
                promotion = move_str[4] if len(move_str) > 4 else None
                
                # Construct JS code to make the move directly
                js_code = f"""
                (function() {{
                    try {{
                        // Try to use Chess.com's official move API
                        if (window.chesscom && window.chesscom.gameClient) {{
                            const move = {{
                                from: '{from_square}',
                                to: '{to_square}'
                            }};
                            
                            // Add promotion if needed
                            if ('{promotion}') {{
                                move.promotion = '{promotion}';
                            }}
                            
                            // Make the move using Chess.com's API
                            window.chesscom.gameClient.makeMove(move);
                            return true;
                        }}
                        
                        // Fallback to direct DOM interaction
                        const fromSquare = document.querySelector('[data-square="{from_square}"]');
                        const toSquare = document.querySelector('[data-square="{to_square}"]');
                        
                        if (!fromSquare || !toSquare) return false;
                        
                        // Create and dispatch click events
                        fromSquare.click();
                        setTimeout(() => {{
                            toSquare.click();
                            
                            // Handle promotion if needed
                            if ('{promotion}') {{
                                setTimeout(() => {{
                                    const promotionPieces = document.querySelectorAll('.promotion-piece');
                                    if (promotionPieces.length > 0) {{
                                        let index = 0; // Default to queen
                                        switch ('{promotion}') {{
                                            case 'q': index = 0; break;
                                            case 'r': index = 1; break;
                                            case 'b': index = 2; break;
                                            case 'n': index = 3; break;
                                        }}
                                        if (promotionPieces[index]) {{
                                            promotionPieces[index].click();
                                        }}
                                    }}
                                }}, 200);
                            }}
                        }}, 200);
                        
                        return true;
                    }} catch (e) {{
                        console.error("Error in mouseless move:", e);
                        return false;
                    }}
                }})();
                """
                
                # Execute the JS directly
                try:
                    js_result = self.grabber.chrome.execute_script(js_code)
                    print(f"Chess.com mouseless move result: {js_result}")
                    return js_result
                except Exception as e:
                    print(f"Error executing Chess.com mouseless move: {e}")
                    return False
            else:  # lichess
                # First try the regular Lichess socket method
                try:
                    move_count = len(self.grabber.get_move_list() or [])
                    result = self.grabber.make_mouseless_move(move_str, move_count, pre_move)
                    if result:
                        return True
                except Exception as e:
                    print(f"Error in Lichess socket move: {e}")
                
                # If socket method fails, try with direct move approach
                print("Socket move failed, trying direct move via JavaScript")
                try:
                    # Parse the move
                    from_square = move_str[0:2]
                    to_square = move_str[2:4]
                    promotion = move_str[4] if len(move_str) > 4 else None
                    
                    # Try a direct approach with JavaScript
                    js_code = f"""
                    (function() {{
                        try {{
                            // Try direct method
                            if (window.lichess && window.lichess.socket) {{
                                // Try standard method
                                const move = {{
                                    from: '{from_square}',
                                    to: '{to_square}',
                                    promotion: '{promotion}'
                                }};
                                
                                // Try various methods, starting with newer ones
                                if (window.lichess.socket.send) {{
                                    window.lichess.socket.send('move', move);
                                    return true;
                                }}
                                
                                return false;
                            }}
                            
                            // Try to find the board and make the move
                            const cg = document.querySelector('cg-board');
                            if (cg && cg.makeMove) {{
                                cg.makeMove('{from_square}', '{to_square}', '{promotion}');
                                return true;
                            }}
                            
                            // Fallback to direct DOM interaction
                            const fromSquare = document.querySelector(`[data-key="{from_square}"]`);
                            const toSquare = document.querySelector(`[data-key="{to_square}"]`);
                            
                            if (!fromSquare || !toSquare) return false;
                            
                            // Create and dispatch click events
                            fromSquare.click();
                            setTimeout(() => {{
                                toSquare.click();
                            }}, 100);
                            
                            return true;
                        }} catch (e) {{
                            console.error("Error in direct JS move:", e);
                            return false;
                        }}
                    }})();
                    """
                    
                    js_result = self.grabber.chrome.execute_script(js_code)
                    print(f"Direct Lichess move result: {js_result}")
                    return js_result
                except Exception as e:
                    print(f"Error in direct Lichess move: {e}")
                
                return False
        except Exception as e:
            print(f"Error in make_mouseless_move: {e}")
            return False

    def detect_connection_issues(self):
        """
        Detects and handles connection issues with Lichess
        Returns True if connection issues were detected and handled
        """
        try:
            # Check for common browser error pages first (these happen regardless of website)
            browser_error_check = """
            (function() {
                // Check for common Chrome error pages
                
                // Check for "No internet" error page
                if (document.querySelector('.error-code') && 
                    (document.body.innerText.includes('ERR_INTERNET_DISCONNECTED') || 
                     document.body.innerText.includes('ERR_CONNECTION_RESET') ||
                     document.body.innerText.includes('ERR_CONNECTION_REFUSED') ||
                     document.body.innerText.includes('ERR_NAME_NOT_RESOLVED'))) {
                    return {
                        found: true,
                        action: "chrome_error",
                        message: "Chrome error page detected"
                    };
                }
                
                // Check for "Page not available" or similar error pages
                if (document.querySelector('.icon-offline') || 
                    document.querySelector('.offline-content')) {
                    return {
                        found: true,
                        action: "chrome_offline",
                        message: "Chrome offline page detected"
                    };
                }
                
                return {
                    found: false
                };
            })();
            """
            
            browser_result = self.grabber.chrome.execute_script(browser_error_check)
            if browser_result and browser_result.get('found'):
                print(f"Browser error detected: {browser_result.get('message')}")
                print("Attempting to refresh the page...")
                self.grabber.chrome.refresh()
                time.sleep(3)  # Wait for page to reload
                self.update_grabber()
                return True
                
            # Only check Lichess-specific issues if we're on Lichess
            if self.website != "lichess":
                return False
                
            # Execute JavaScript to check for connection issues
            connection_check = """
            (function() {
                // Check for common connection issue indicators
                
                // 1. Check for the reconnect button
                const reconnectBtn = document.querySelector('.reconnect');
                if (reconnectBtn) {
                    console.log("Found reconnect button, clicking it");
                    reconnectBtn.click();
                    return {
                        found: true,
                        action: "clicked_reconnect",
                        message: "Found and clicked reconnect button"
                    };
                }
                
                // 2. Check for the connection lost message
                const connectionLostMsg = document.querySelector('.connection-lost');
                if (connectionLostMsg) {
                    // Try to find any buttons to click
                    const buttons = connectionLostMsg.querySelectorAll('button');
                    if (buttons.length > 0) {
                        console.log("Found connection lost message with button, clicking it");
                        buttons[0].click();
                        return {
                            found: true,
                            action: "clicked_connection_lost_button",
                            message: "Found and clicked connection lost button"
                        };
                    }
                    
                    return {
                        found: true,
                        action: "found_connection_lost",
                        message:
                            "Found connection lost message but no button to click"
                    };
                }
                
                // 3. Check for the reload button (shown when server is down)
                const reloadBtn = document.querySelector('.reload-button');
                if (reloadBtn) {
                    console.log("Found reload button, clicking it");
                    reloadBtn.click();
                    return {
                        found: true,
                        action: "clicked_reload",
                        message: "Found and clicked reload button"
                    };
                }
                
                // 4. Check for lag indicator (severe lag might require a page
                // refresh)
                const lagIndicator = document.querySelector('.lag');
                if (
                    lagIndicator &&
                    lagIndicator.classList.contains('severe')
                ) {
                    return {
                        found: true,
                        action: "severe_lag",
                        message: "Detected severe lag"
                    };
                }
                
                // 5. Check for socket disconnected message in console or page
                const socketDisconnected = (
                    document.body.innerText
                        .toLowerCase()
                        .includes('socket disconnected') ||
                    document.body.innerText
                        .toLowerCase()
                        .includes('connection lost')
                );
                if (socketDisconnected) {
                    return {
                        found: true,
                        action: "socket_disconnected",
                        message: "Detected socket disconnected message"
                    };
                }
                
                return {
                    found: false
                };
            })();
            """
            
            result = self.grabber.chrome.execute_script(connection_check)
            
            if result and result.get('found'):
                print(f"Connection issue detected: {result.get('message')}")
                action = result.get('action')
                
                # Handle different types of connection issues
                if action in [
                    "clicked_reconnect",
                    "clicked_connection_lost_button",
                    "clicked_reload",
                ]:
                    print(
                        "Clicked button to address connection issue, waiting for reconnection..."
                    )
                    time.sleep(3)  # Wait for reconnection
                    return True
                elif action in [
                    "found_connection_lost",
                    "socket_disconnected",
                    "severe_lag",
                ]:
                    print("Detected connection issue requiring page refresh...")
                    self.grabber.chrome.refresh()
                    time.sleep(3)  # Wait for page to reload
                    self.update_grabber()
                    return True
                    
            return False
        except Exception as e:
            print(f"Error in detect_connection_issues: {e}")
            return False
