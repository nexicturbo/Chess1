import re
import time  # Added for delays
from selenium.common import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from grabbers.grabber import Grabber


class ChesscomGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)
        self.tag_name = None
        self.moves_list = {}
        self.color_cache = None  # Cache player color once determined
        self.board_size = None   # Store board size for more accurate piece movement
        self.website = "chesscom"  # Add website attribute

    def update_board_elem(self):
        try:
            # Enhanced board detection for Chess.com
            selectors = [
                ".board-layout-chessboard",
                ".board-render",
                ".board-play",
                ".board-container",
                ".board",
                ".chessboard",
                ".game-board",
                ".board-modal",
                "#board-single",
                "#board-layout-chessboard",
                "[data-board]",
                "[data-game-container]",
                "[data-boardname]"
            ]
            
            # Try class selectors first - most reliable
            for selector in selectors:
                try:
                    elements = self.chrome.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.size["width"] > 200:
                            self._board_elem = elem
                            self.board_size = elem.size["width"]
                            print(f"Found board via {selector}: {elem.tag_name}, size: {elem.size}")
                            return
                except:
                    continue
                    
            # Try by XPath for elements with board-related classes
            try:
                xpath_elements = self.chrome.find_elements(By.XPATH, "//*[contains(@class, 'board')]")
                for elem in xpath_elements:
                    if elem.is_displayed() and elem.size["width"] > 200:
                        self._board_elem = elem
                        self.board_size = elem.size["width"]
                        print(f"Found board via XPath: {elem.tag_name}, size: {elem.size}")
                        return
            except:
                pass
                
            # Try JavaScript detection as a last resort
            try:
                js_board = self.chrome.execute_script("""
                    // Try to find the board using various strategies
                    try {
                        // Strategy 1: Look for elements with board-related classes
                        const boardSelectors = [
                            '.board', '.chessboard', '.game-board', '.board-container',
                            '[data-board]', '[data-boardname]'
                        ];
                        
                        for (const selector of boardSelectors) {
                            const elements = document.querySelectorAll(selector);
                            for (const elem of elements) {
                                const rect = elem.getBoundingClientRect();
                                if (rect.width > 200 && rect.height > 200 && elem.offsetParent !== null) {
                                    return elem;
                                }
                            }
                        }
                        
                        // Strategy 2: Look for elements containing piece images
                        const pieceElements = document.querySelectorAll('.piece, [class*="piece-"], [class*="-piece"]');
                        if (pieceElements.length > 0) {
                            // Find the closest common parent that might be the board
                            let commonParent = pieceElements[0].parentElement;
                            while (commonParent && 
                                   commonParent.tagName !== 'BODY' && 
                                   commonParent.getBoundingClientRect().width < 400) {
                                commonParent = commonParent.parentElement;
                            }
                            
                            if (commonParent && commonParent.tagName !== 'BODY') {
                                return commonParent;
                            }
                        }
                        
                        // Strategy 3: Look for the main game container in Chess.com's structure
                        const possibleContainers = [
                            document.querySelector('#board-layout-main'),
                            document.querySelector('#board-layout-chessboard'),
                            document.querySelector('.board-layout-container'),
                            document.querySelector('.board-modal-container'),
                            document.querySelector('.vertical-board-container')
                        ];
                        
                        for (const container of possibleContainers) {
                            if (container && container.offsetParent !== null) {
                                const rect = container.getBoundingClientRect();
                                if (rect.width > 200 && rect.height > 200) {
                                    return container;
                                }
                            }
                        }
                    } catch (e) {
                        console.error("Error finding board:", e);
                    }
                    
                    return null;
                """)
                
                if js_board:
                    self._board_elem = js_board
                    self.board_size = js_board.size["width"] if hasattr(js_board, "size") else 400
                    print(f"Found board via JavaScript: size {self.board_size}")
                    return
            except Exception as e:
                print(f"JavaScript board detection failed: {e}")
                
            # If we got here, we couldn't find the board
            print("Failed to find chess board element")
            self._board_elem = None
        except Exception as e:
            print(f"Error finding board: {e}")
            self._board_elem = None

    def is_white(self):
        """
        Improved method to determine if the player is playing white or black pieces
        """
        try:
            # This is the most reliable method for Chess.com
            result = self.chrome.execute_script('''
                try {
                    // Try to find the orientation directly from the board
                    const boardOrientation = document.querySelector('.board-layout-chessboard').getAttribute('data-board-orientation');
                    if (boardOrientation) {
                        return boardOrientation === 'white';
                    }
                    
                    // Try the clock method as fallback
                    var bottomClock = document.querySelector('.clock-bottom');
                    var topClock = document.querySelector('.clock-top');
                    
                    if (bottomClock && bottomClock.classList.contains('clock-white')) {
                        return true;
                    } else if (bottomClock && bottomClock.classList.contains('clock-black')) {
                        return false;
                    } else if (topClock && topClock.classList.contains('clock-white')) {
                        return false;
                    } else if (topClock && topClock.classList.contains('clock-black')) {
                        return true;
                    }
                    
                    // Check if there are any pieces and their positions
                    const whitePawns = document.querySelectorAll('.piece.wp');
                    const blackPawns = document.querySelectorAll('.piece.bp');
                    
                    if (whitePawns.length > 0 && blackPawns.length > 0) {
                        // Get positions of white and black pawns
                        const whitePawnY = parseInt(whitePawns[0].style.top);
                        const blackPawnY = parseInt(blackPawns[0].style.top);
                        
                        // If white pawns are at the bottom (larger Y value), player is white
                        return whitePawnY > blackPawnY;
                    }
                    
                    // Default to white if we can't determine
                    return true;
                } catch (e) {
                    console.error('Error determining color:', e);
                    return null;
                }
            ''')
            
            if result is not None:
                print(f"Bottom clock is {'white' if result else 'black'} - player is {'white' if result else 'black'}")
            else:
                print("Could not determine player color")
                
            return result
        except Exception as e:
            print(f"Error in is_white: {e}")
            return None

    def is_game_over(self):
        try:
            # Only detect clear game over indicators, not absence of moves
            game_over_selectors = [
                ".game-over-modal",
                ".game-result-component",
                ".result-wrap",
                ".game-over-header"
            ]
            
            for selector in game_over_selectors:
                try:
                    element = self.chrome.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        print(f"Game over detected: found {selector}")
                        return True
                except NoSuchElementException:
                    continue
                    
            # Check for text indicating game over
            try:
                result_texts = self.chrome.find_elements(By.XPATH, "//*[contains(text(), 'Checkmate') or contains(text(), 'Resignation') or contains(text(), 'Timeout') or contains(text(), 'Draw offered')]")
                for result in result_texts:
                    if result.is_displayed():
                        print(f"Game over detected via text: {result.text}")
                        return True
            except:
                pass
                
            # Don't use JavaScript detection as it's unreliable
            # If no clear game over indicator is found, assume game is ongoing
            return False
        except Exception as e:
            print(f"Error checking if game is over: {e}")
            return False

    def get_move_list(self):
        """
        Improved method to extract the list of moves from Chess.com's move list
        """
        try:
            # First check if there are any moves yet
            has_moves = self.chrome.execute_script('''
                return document.querySelectorAll('.move').length > 0;
            ''')
            
            if not has_moves:
                # Alternative method to detect first move when move elements aren't found
                try:
                    first_move = self.chrome.execute_script('''
                        // Check if any pieces have moved from their starting positions
                        const pieces = document.querySelectorAll('.piece');
                        for (const piece of pieces) {
                            const square = piece.getAttribute('data-square');
                            if (square) {
                                // For white's moves (e.g., e4)
                                if (square === 'e4' && piece.classList.contains('wp')) {
                                    return ['e4'];
                                }
                                // For other common opening moves
                                if (square === 'd4' && piece.classList.contains('wp')) {
                                    return ['d4'];
                                }
                                if (square === 'c4' && piece.classList.contains('wp')) {
                                    return ['c4'];
                                }
                                if (square === 'e5' && piece.classList.contains('bp')) {
                                    return ['e4', 'e5'];
                                }
                            }
                        }
                        
                        // Check move history object if available
                        if (window.chesscom && window.chesscom.gameClient) {
                            try {
                                const gameData = window.chesscom.gameClient.getGameData();
                                if (gameData && gameData.moveList && gameData.moveList.length > 0) {
                                    return gameData.moveList.map(m => m.san);
                                }
                            } catch (e) {
                                console.error("Error accessing game data:", e);
                            }
                        }
                        
                        return null;
                    ''')
                    
                    if first_move:
                        print(f"Detected first move(s) via piece positions: {first_move}")
                        return first_move
                except Exception as e:
                    print(f"Error detecting first move: {e}")
                
                print("No moves found, treating as a new game or waiting for first move")
                return []
            
            # More reliable method to extract moves from Chess.com
            moves = self.chrome.execute_script('''
                try {
                    // Try different methods to get moves
                    
                    // Method 1: Direct API access
                    if (window.chesscom && window.chesscom.gameClient) {
                        try {
                            const gameData = window.chesscom.gameClient.getGameData();
                            if (gameData && gameData.moveList && gameData.moveList.length > 0) {
                                return gameData.moveList.map(m => m.san);
                            }
                        } catch (e) {
                            console.error("Error accessing game data:", e);
                        }
                    }
                    
                    // Method 2: Parse move elements
                    const moveElements = document.querySelectorAll('.move');
                    console.log('Found ' + moveElements.length + ' move elements in DOM');
                    
                    if (moveElements.length === 0) {
                        return [];
                    }
                    
                    let extractedMoves = [];
                    
                    // Process each move element
                    moveElements.forEach(moveElement => {
                        // Extract white's move
                        const whiteMove = moveElement.querySelector('.white');
                        if (whiteMove && whiteMove.textContent.trim() !== '') {
                            extractedMoves.push(whiteMove.textContent.trim());
                        }
                        
                        // Extract black's move
                        const blackMove = moveElement.querySelector('.black');
                        if (blackMove && blackMove.textContent.trim() !== '') {
                            extractedMoves.push(blackMove.textContent.trim());
                        }
                    });
                    
                    console.log('Extracted ' + extractedMoves.length + ' moves from DOM elements');
                    return extractedMoves;
                } catch (e) {
                    console.error('Error extracting moves:', e);
                    return null;
                }
            ''')
            
            return moves
        except Exception as e:
            print(f"Error in get_move_list: {e}")
            return None

    def is_game_puzzles(self):
        try:
            # Check for puzzle indicators in URL
            current_url = self.chrome.current_url.lower()
            if "/puzzles/" in current_url or "/puzzle/" in current_url or "/tactics/" in current_url:
                return True
                
            # Try JavaScript detection - most reliable
            try:
                js_result = self.chrome.execute_script("""
                    // Check for puzzle-specific objects or properties
                    if (window.puzzleControls || window.tacticsControls || window.puzzleId) {
                        return true;
                    }
                    
                    // Check for puzzle wrapper elements
                    return Boolean(
                        document.querySelector('.daily-puzzle') || 
                        document.querySelector('.puzzle-container') || 
                        document.querySelector('.puzzles-container') ||
                        document.querySelector('.tactics-board')
                    );
                """)
                
                if js_result:
                    return True
            except:
                pass
                
            # Check for puzzle page elements
            puzzle_selectors = [
                ".daily-puzzle-container",
                ".puzzles-container",
                ".puzzle-container",
                ".puzzle-board",
                ".tactics-board",
                ".puzzle-dashboard"
            ]
            
            for selector in puzzle_selectors:
                try:
                    element = self.chrome.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        return True
                except NoSuchElementException:
                    continue
                
            return False
        except Exception as e:
            print(f"Error checking if game is puzzles: {e}")
            return False

    def click_puzzle_next(self):
        try:
            # Try JavaScript approach first
            js_result = self.chrome.execute_script("""
                // Try to find and click the next button using JavaScript
                function findAndClickNextButton() {
                    // Look for buttons with specific text
                    const buttonTexts = ['Next', 'Continue', 'Try Again', 'Next Puzzle'];
                    
                    for (const text of buttonTexts) {
                        const buttons = Array.from(document.querySelectorAll('button')).filter(btn => 
                            btn.textContent.includes(text) && btn.offsetParent !== null
                        );
                        
                        if (buttons.length > 0) {
                            buttons[0].click();
                            return true;
                        }
                    }
                    
                    // Look for buttons with specific classes
                    const buttonSelectors = [
                        '.next-puzzle-button', 
                        '.puzzle-next', 
                        '.next-button',
                        '.continue-button',
                        '.primary-action',
                        '[data-cy="next-puzzle"]'
                    ];
                    
                    for (const selector of buttonSelectors) {
                        const button = document.querySelector(selector);
                        if (button && button.offsetParent !== null) {
                            button.click();
                            return true;
                        }
                    }
                    
                    return false;
                }
                
                return findAndClickNextButton();
            """)
            
            if js_result:
                return True
                
            # Fallback to Selenium methods
            next_button_selectors = [
                ".next-puzzle-button",
                ".puzzle-next",
                ".next-button",
                ".continue-button",
                ".primary-action",
                "button[data-cy='next-puzzle']"
            ]
            
            for selector in next_button_selectors:
                try:
                    next_button = WebDriverWait(self.chrome, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self.chrome.execute_script("arguments[0].click();", next_button)
                    return True
                except:
                    continue
                    
            # Try using XPath with text content
            try:
                xpath_expression = "//button[contains(text(), 'Next') or contains(text(), 'Continue') or contains(text(), 'Try Again')]"
                next_button = WebDriverWait(self.chrome, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath_expression))
                )
                self.chrome.execute_script("arguments[0].click();", next_button)
                return True
            except:
                pass
                
            print("Could not find next puzzle button")
            return False
        except Exception as e:
            print(f"Error clicking puzzle next: {e}")
            return False

    def get_player_time(self):
        """
        Get player's remaining time in seconds on Chess.com
        Returns: Float representing seconds remaining, or None if couldn't extract time
        """
        try:
            self.update_board_elem()
            is_white_player = self.is_white()
            
            # Try JavaScript first - most reliable method
            try:
                js_time = self.chrome.execute_script(f"""
                    // Try to access time directly from Chess.com's objects
                    let playerColor = {str(is_white_player).lower()} ? 'white' : 'black';
                    
                    try {{
                        if (window.chessBasic && window.chessBasic.mainGame) {{
                            return window.chessBasic.mainGame.getPlayerClock(playerColor);
                        }} else if (window.chessController && window.chessController.userGame) {{
                            return window.chessController.userGame.getPlayerClock(playerColor);
                        }} else if (window.gameStateController) {{
                            return window.gameStateController.getPlayerClock(playerColor);
                        }}
                        
                        // Fallback to finding clock elements in the DOM
                        const clockSelector = playerColor === 'white' ? 
                            '.clock-white .clock-time, .white-clock, .clock-component.white .time' :
                            '.clock-black .clock-time, .black-clock, .clock-component.black .time';
                        
                        const clockElem = document.querySelector(clockSelector);
                        return clockElem ? clockElem.textContent : null;
                    }} catch (e) {{
                        return null;
                    }}
                """)
                
                if js_time is not None:
                    # If it's a number, return it directly
                    if isinstance(js_time, (int, float)):
                        return float(js_time)
                    
                    # If it's a string, parse it
                    time_text = str(js_time).strip()
                    
                    # Handle different time formats
                    if ":" in time_text:
                        parts = time_text.split(":")
                        if len(parts) == 2:
                            minutes, seconds = int(parts[0]), float(parts[1])
                            return minutes * 60 + seconds
                        elif len(parts) == 3:
                            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
                            return hours * 3600 + minutes * 60 + seconds
                    else:
                        # Try to parse as a float
                        try:
                            return float(time_text)
                        except:
                            pass
            except Exception as e:
                print(f"JS time detection failed: {e}")
            
            # Fallback to traditional method
            clock_selectors = [
                (".clock-white .clock-time", ".clock-black .clock-time"),
                (".clock-player-white .time", ".clock-player-black .time"),
                (".clock-component.white .time", ".clock-component.black .time"),
                (".player-clock-white", ".player-clock-black"),
                (".white-clock", ".black-clock")
            ]
            
            time_element = None
            for white_selector, black_selector in clock_selectors:
                try:
                    if is_white_player:
                        time_element = WebDriverWait(self.chrome, 1).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, white_selector))
                        )
                    else:
                        time_element = WebDriverWait(self.chrome, 1).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, black_selector))
                        )
                        
                    if time_element:
                        break
                except:
                    continue
            
            if not time_element:
                return None
                
            # Get time text and convert to seconds
            time_text = time_element.text
            
            # Handle different time formats
            if ":" in time_text:
                # Format: MM:SS or H:MM:SS
                parts = time_text.split(":")
                if len(parts) == 2:
                    # MM:SS format
                    minutes, seconds = int(parts[0]), float(parts[1])
                    return minutes * 60 + seconds
                elif len(parts) == 3:
                    # H:MM:SS format
                    hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
            else:
                # Just seconds
                return float(time_text)
        except Exception as e:
            print(f"Error getting player time: {e}")
            return None

    def make_mouseless_move(self, move_str, pre_move=False):
        """
        Enhanced method to make a move using JavaScript for Chess.com
        """
        # Parse the move
        from_square = move_str[0:2].lower()
        to_square = move_str[2:4].lower()
        promotion = move_str[4].lower() if len(move_str) > 4 else ''
        
        try:
            # Execute on Chess.com with improved reliability
            result = self.chrome.execute_script(f'''
                try {{
                    console.log("Making mouseless move from {from_square} to {to_square}");
                    
                    // Look for a better way to make moves directly with Chess.com's API
                    if (window.chesscom && window.chesscom.gameClient) {{
                        console.log("Using Chess.com gameClient API");
                        // This is the official API - should be most reliable
                        const fromSquare = "{from_square}";
                        const toSquare = "{to_square}";
                        const promotionPiece = "{promotion}";
                        
                        const move = {{
                            from: fromSquare,
                            to: toSquare
                        }};
                        
                        if (promotionPiece) {{
                            move.promotion = promotionPiece;
                        }}
                        
                        // Make the move using Chess.com's API
                        window.chesscom.gameClient.makeMove(move);
                        return true;
                    }}
                    
                    // Fallback to simulating dragging with mouse events
                    const fromSquare = document.querySelector('[data-square="{from_square}"]');
                    const toSquare = document.querySelector('[data-square="{to_square}"]');
                    
                    if (!fromSquare || !toSquare) {{
                        console.log("Could not find squares");
                        return false;
                    }}
                    
                    // Highlight the squares to provide visual feedback
                    fromSquare.style.backgroundColor = 'rgba(255, 255, 0, 0.5)';
                    toSquare.style.backgroundColor = 'rgba(0, 255, 255, 0.5)';
                    
                    // Create a mousedown event
                    let mouseDownEvent = new MouseEvent('mousedown', {{
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }});
                    
                    // Create a mouseup event
                    let mouseUpEvent = new MouseEvent('mouseup', {{
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }});
                    
                    // Dispatch the events
                    fromSquare.dispatchEvent(mouseDownEvent);
                    setTimeout(() => {{
                        toSquare.dispatchEvent(mouseUpEvent);
                        
                        // Handle promotion if needed
                        if ("{promotion}" !== "") {{
                            setTimeout(() => {{
                                const promotionPieces = document.querySelectorAll('.promotion-piece');
                                if (promotionPieces.length > 0) {{
                                    let index = 0; // Default to queen
                                    
                                    switch ("{promotion}") {{
                                        case "q": index = 0; break;
                                        case "r": index = 1; break;
                                        case "b": index = 2; break;
                                        case "n": index = 3; break;
                                    }}
                                    
                                    promotionPieces[index].click();
                                }}
                            }}, 300);
                        }}
                        
                        // Reset square colors after a delay
                        setTimeout(() => {{
                            fromSquare.style.backgroundColor = '';
                            toSquare.style.backgroundColor = '';
                        }}, 500);
                    }}, 300);
                    
                    return true;
                }} catch (e) {{
                    console.error("Error making mouseless move:", e);
                    return false;
                }}
            ''')
            
            return result
        except Exception as e:
            print(f"Error in make_mouseless_move: {e}")
            return False