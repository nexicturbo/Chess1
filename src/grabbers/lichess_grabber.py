import re
import time

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class LichessGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)
        self.tag_name = None
        self.moves_list = {}

    def update_board_elem(self):
        try:
            # Try finding the normal board
            self._board_elem = self.chrome.find_element(By.XPATH,
                                                        '//*[@id="main-wrap"]/main/div[1]/div[1]/div/cg-container')
        except NoSuchElementException:
            try:
                # Try finding the board in the puzzles page
                self._board_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[1]/div/cg-container')
            except NoSuchElementException:
                self._board_elem = None

    def is_white(self):
        # sourcery skip: assign-if-exp, boolean-if-exp-identity, remove-unnecessary-cast
        # Get "ranks" child
        children = self._board_elem.find_elements(By.XPATH, "./*")
        child = [x for x in children if "ranks" in x.get_attribute("class")][0]
        if child.get_attribute("class") == "ranks":
            return True
        else:
            return False

    def is_game_over(self):
        # sourcery skip: assign-if-exp, boolean-if-exp-identity, reintroduce-else, remove-unnecessary-cast
        try:
            # Find the game over window
            game_over_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/aside/div/section[2]')
            
            # Check if it contains any game over messages
            over_text = game_over_elem.text.lower()
            if any(x in over_text for x in ["aborted", "victory", "defeat", "draw", "checkmate", "stalemate", "time"]):
                print(f"Game over detected with text: {over_text}")
                return True

            # If we don't have an exception at this point, we have found the game over window
            return True
        except NoSuchElementException:
            # Try finding the puzzles game over window and checking its class
            try:
                # The game over window
                game_over_window = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[3]/div[1]')

                if game_over_window.get_attribute("class") == "complete":
                    return True
                    
                # Check common game over messages in the document
                page_text = self.chrome.find_element(By.TAG_NAME, 'body').text.lower()
                if any(x in page_text for x in ['game aborted', 'game over', 'victory', 'defeat', 'draw']):
                    print(f"Game over detected in page text")
                    return True

                # If we don't have an exception at this point and the window's class is not "complete",
                # then the game is still going
                return False
            except NoSuchElementException:
                # Try checking for game over elements on the page as a last resort
                try:
                    # Check common game over messages in the document
                    page_text = self.chrome.find_element(By.TAG_NAME, 'body').text.lower()
                    if any(x in page_text for x in ['game aborted', 'game over', 'victory', 'defeat', 'draw']):
                        print(f"Game over detected in page text")
                        return True
                except:
                    pass
                return False

    def set_moves_tag_name(self):
        if self.is_game_puzzles():
            return False

        move_list_elem = self.get_normal_move_list_elem()

        if move_list_elem is None or move_list_elem == []:
            return False

        try:
            last_child = move_list_elem.find_element(By.XPATH, "*[last()]")
            self.tag_name = last_child.tag_name

            return True
        except NoSuchElementException:
            return False

    def get_move_list(self):
        # sourcery skip: assign-if-exp, merge-else-if-into-elif, use-fstring-for-concatenation
        is_puzzles = self.is_game_puzzles()

        # Find the move list element
        if is_puzzles:
            move_list_elem = self.get_puzzles_move_list_elem()

            if move_list_elem is None:
                return None
        else:
            move_list_elem = self.get_normal_move_list_elem()

            if move_list_elem is None:
                return None
            if (not move_list_elem) or (self.tag_name is None and self.set_moves_tag_name() is False):
                return []

        # Get the move elements (children of the move list element)
        try:
            if not is_puzzles:
                if not self.moves_list:
                    # If the moves list is empty, find all moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, self.tag_name)
                else:
                    # If the moves list is not empty, find only the new moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, self.tag_name + ":not([data-processed])")
            else:
                if not self.moves_list:
                    # If the moves list is empty, find all moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, "move")
                else:
                    # If the moves list is not empty, find only the new moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, "move:not([data-processed])")
        except NoSuchElementException:
            return None

        # Get the moves from the elements
        for move_element in children:
            # Sanitize the move
            move = re.sub(r"[^a-zA-Z0-9+-]", "", move_element.text)
            
            # Skip non-chess move messages like "Gameaborted"
            if move != "" and re.match(r'^[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]=?[NBRQ]?[+#]?$|^O-O(-O)?[+#]?$', move):
                self.moves_list[move_element.id] = move
            elif move != "":
                print(f"Skipping non-standard move text: {move}")

            # Mark the move as processed
            self.chrome.execute_script("arguments[0].setAttribute('data-processed', 'true')", move_element)

        return [val for val in self.moves_list.values()]

    def get_puzzles_move_list_elem(self):
        try:
            # Try finding the move list in the puzzles page
            move_list_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[2]/div')

            return move_list_elem
        except NoSuchElementException:
            return None

    def get_normal_move_list_elem(self):
        try:
            # Try finding the normal move list
            move_list_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6/l4x')

            return move_list_elem
        except NoSuchElementException:
            try:
                # Try finding the normal move list when there are no moves yet
                self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6')

                # If we don't have an exception at this point, we don't have any moves yet
                return []
            except NoSuchElementException:
                return None

    def is_game_puzzles(self):
        try:
            # Try finding the puzzles text
            self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/aside/div[1]/div[1]/div/p[1]")

            # If we don't have an exception at this point, the game is a puzzle
            return True
        except NoSuchElementException:
            return False

    def click_puzzle_next(self):
        # Find the next continue training button
        try:
            next_button = self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/div[2]/div[3]/a")
        except NoSuchElementException:
            try:
                next_button = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[2]/div[3]/div[3]/a[2]')
            except NoSuchElementException:
                return

        # Click the continue training button
        self.chrome.execute_script("arguments[0].click();", next_button)

    def make_mouseless_move(self, move, move_count=0, pre_move=False):
        """
        Make a move without using the mouse
        If pre_move is True, it sets a premove instead
        """
        try:
            if pre_move:
                # Set a premove using the Lichess socket API
                script = f"""
                const startSq = '{move[0:2]}';
                const endSq = '{move[2:4]}';
                // Try to use the lichess API directly if available
                if (window.lichess && window.lichess.socket && window.lichess.socket.ws) {{
                    const premoveMsg = {{"t":"premove","d":{{"orig":startSq,"dest":endSq}}}};
                    lichess.socket.ws.send(JSON.stringify(premoveMsg));
                    return true;
                }}
                return false;
                """
                success = self.chrome.execute_script(script)
                
                if not success:
                    # Alternative method using direct message format
                    message = '{"t":"premove","d":{"orig":"' + move[0:2] + '","dest":"' + move[2:4] + '"}}'
                    script = 'lichess.socket.ws.send(' + message + ')'
                    try:
                        self.chrome.execute_script(script)
                        success = True
                    except Exception as e:
                        print(f"Error in alternative premove method: {e}")
                        success = False
                    
                print(f"Set JavaScript premove: {move}, success: {success}")
                return success
            else:
                # Make a regular move
                # Check if there's a promotion
                promotion = ""
                if len(move) > 4:
                    promotion = move[4]
                
                # Include promotion in the move if present
                if promotion:
                    message = '{"t":"move","d":{"u":"' + move + '","b":1,"a":' + str(move_count) + ',"p":"' + promotion + '"}}'
                else:
                    message = '{"t":"move","d":{"u":"' + move + '","b":1,"a":' + str(move_count) + '}}'
                
                try:
                    # First try with JSON.stringify
                    script = 'lichess.socket.ws.send(JSON.stringify(' + message + '))'
                    self.chrome.execute_script(script)
                    return True
                except Exception as e:
                    print(f"Primary socket method failed: {e}")
                    
                    try:
                        # Try an alternative direct socket approach
                        script = 'lichess.socket.ws.send(' + message + ')'
                        self.chrome.execute_script(script)
                        return True
                    except Exception as e:
                        print(f"Alternative socket method failed too: {e}")
                        return False
        except Exception as e:
            print(f"Error in make_mouseless_move: {e}")
            # Fall back to mouse-based approach if JavaScript fails
            return False
        
    def make_direct_dom_move(self, move):
        """
        Makes a move by directly interacting with the DOM elements
        This is another approach that works well with Lichess
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Parse move data
                from_square = move[0:2]
                to_square = move[2:4]
                promotion = move[4] if len(move) > 4 else None
                
                script = f"""
                (function() {{
                    // Get the start and end squares
                    const fromSquare = '{from_square}';
                    const toSquare = '{to_square}';
                    const promotion = '{promotion if promotion else ""}';
                    
                    // Function to find a square element by its key
                    function findSquare(key) {{
                        // Try all possible selectors
                        const selectors = [
                            `[data-key="${{key}}"]`,           // Lichess primary
                            `[data-square="${{key}}"]`,        // Chess.com and others
                            `.square-${{key}}`                 // Another common format
                        ];
                        
                        for (const selector of selectors) {{
                            const square = document.querySelector(selector);
                            if (square) return square;
                        }}
                        
                        // Try to find it in a piece's attributes
                        const pieces = document.querySelectorAll('.piece');
                        for (const piece of pieces) {{
                            if (piece.getAttribute('data-square') === key || 
                                piece.getAttribute('data-key') === key) {{
                                return piece;
                            }}
                        }}
                        
                        return null;
                    }}
                    
                    // Find the square elements
                    const fromElem = findSquare(fromSquare);
                    const toElem = findSquare(toSquare);
                    
                    if (!fromElem || !toElem) {{
                        console.log(`Could not find squares: ${{fromSquare}} -> ${{toSquare}}`);
                        return {{success: false, error: 'Could not find squares'}};
                    }}
                    
                    console.log(`Found squares: ${{fromSquare}} -> ${{toSquare}}`);
                    
                    // First try the Lichess API if available
                    if (window.lichess && window.lichess.socket) {{
                        try {{
                            const moveObj = {{
                                from: fromSquare,
                                to: toSquare
                            }};
                            
                            if (promotion) {{
                                moveObj.promotion = promotion;
                            }}
                            
                            // Try the move API if available
                            if (window.lichess.move) {{
                                window.lichess.move(moveObj);
                                return {{success: true, method: 'lichess.move'}};
                            }}
                            
                            // Try the socket API if available
                            if (window.lichess.socket.send) {{
                                window.lichess.socket.send('move', moveObj);
                                return {{success: true, method: 'lichess.socket.send'}};
                            }}
                        }} catch (e) {{
                            console.error("Error in Lichess API move:", e);
                        }}
                    }}
                    
                    // Try Lichess-specific method with precise coordinates
                    try {{
                        // Find the piece on the from square if it exists
                        let piece = null;
                        const pieceSelectors = [
                            `piece[data-key="${{fromSquare}}"]`,
                            `.piece[data-square="${{fromSquare}}"]`,
                            `[data-key="${{fromSquare}}"] .piece`,
                            `[data-square="${{fromSquare}}"] .piece`
                        ];
                        
                        for (const selector of pieceSelectors) {{
                            piece = document.querySelector(selector);
                            if (piece) break;
                        }}
                        
                        // If we found the piece or the square, use it
                        const elemToClick = piece || fromElem;
                        
                        // Calculate center coordinates
                        const fromRect = fromElem.getBoundingClientRect();
                        const toRect = toElem.getBoundingClientRect();
                        
                        const fromX = fromRect.left + (fromRect.width / 2);
                        const fromY = fromRect.top + (fromRect.height / 2);
                        const toX = toRect.left + (toRect.width / 2);
                        const toY = toRect.top + (toRect.height / 2);
                        
                        // Create and dispatch mousedown event
                        const downEvent = new MouseEvent('mousedown', {{
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            clientX: fromX,
                            clientY: fromY
                        }});
                        elemToClick.dispatchEvent(downEvent);
                        
                        // Now dispatch mouseup event on destination
                        setTimeout(() => {{
                            const upEvent = new MouseEvent('mouseup', {{
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: toX,
                                clientY: toY
                            }});
                            toElem.dispatchEvent(upEvent);
                            
                            // Handle promotion if needed
                            if (promotion) {{
                                setTimeout(() => {{
                                    const promotionPieces = document.querySelectorAll('.promotion-piece');
                                    if (promotionPieces.length > 0) {{
                                        let index = 0; // Default to queen
                                        switch (promotion) {{
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
                        }}, 50);
                        
                        return {{success: true, method: 'precise DOM events'}};
                    }} catch (e) {{
                        console.error("Error in precise DOM move:", e);
                    }}
                    
                    // General approach - click on the from square, then the to square
                    try {{
                        // Create and dispatch click event on from square
                        fromElem.click();
                        
                        // Short delay, then click destination
                        setTimeout(() => {{
                            toElem.click();
                            
                            // Handle promotion if needed
                            if (promotion) {{
                                setTimeout(() => {{
                                    const promotionPieces = document.querySelectorAll('.promotion-piece');
                                    if (promotionPieces.length > 0) {{
                                        let index = 0; // Default to queen
                                        switch (promotion) {{
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
                        }}, 100);
                        
                        return {{success: true, method: 'standard click'}};
                    }} catch (e) {{
                        console.error("Error in general click approach:", e);
                        return {{success: false, error: e.toString()}};
                    }}
                }})();
                """
                
                result = self.chrome.execute_script(script)
                print(f"Direct DOM move result: {result}")
                
                if isinstance(result, dict) and result.get('success') is True:
                    print(f"Move successful using method: {result.get('method')}")
                    return True
                else:
                    error_msg = result.get('error') if isinstance(result, dict) else "Unknown error"
                    print(f"Move failed: {error_msg}")
                    
                    # If we still have retries left, try again
                    if retry_count < max_retries:
                        retry_count += 1
                        print(f"Retrying... (attempt {retry_count} of {max_retries})")
                        # Wait a bit before retrying
                        time.sleep(0.5)
                        continue
                    return False
                    
            except Exception as e:
                print(f"Error in make_direct_dom_move: {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    print(f"Retrying after exception... (attempt {retry_count} of {max_retries})")
                    time.sleep(0.5)
                    continue
                return False
                
        return False
