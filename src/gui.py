import multiprocessing
import multiprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import chromedriver_autoinstaller
import keyboard
from overlay import run  # Ensure overlay.py exists and defines run()
from stockfish_bot import StockfishBot  # Ensure stockfish_bot.py exists and defines StockfishBot

class GUI:
    def __init__(self, master):
        self.master = master

        # Used for closing the threads
        self.exit = False

        # The Selenium Chrome driver
        self.chrome = None

        # Stockfish Bot process details
        self.chrome_url = None
        self.chrome_session_id = None

        # Communication channels between GUI and Stockfish Bot process
        self.stockfish_bot_pipe = None
        self.overlay_screen_pipe = None

        # The Stockfish Bot and Overlay processes
        self.stockfish_bot_process = None
        self.overlay_screen_process = None
        self.restart_after_stopping = False

        # Store match moves
        self.match_moves = []

        # Flag to prevent repeated end-of-game pop-ups
        self.game_over_shown = False
        
        # Flag to track if we're in tournament mode
        self.is_tournament_mode = False

        # Set window properties
        master.title("Chess")
        master.geometry("")
        master.iconphoto(True, tk.PhotoImage(file="src/assets/pawn_32x32.png"))
        master.resizable(False, False)
        master.attributes("-topmost", True)
        master.protocol("WM_DELETE_WINDOW", self.on_close_listener)

        # Change the style
        style = ttk.Style()
        style.theme_use("clam")

        # Left frame
        left_frame = tk.Frame(master)

        # Status text
        status_label = tk.Frame(left_frame)
        tk.Label(status_label, text="Status:").pack(side=tk.LEFT)
        self.status_text = tk.Label(status_label, text="Inactive", fg="red")
        self.status_text.pack()
        status_label.pack(anchor=tk.NW)

        # Website chooser radio buttons
        self.website = tk.StringVar(value="chesscom")
        self.chesscom_radio_button = tk.Radiobutton(
            left_frame, text="Chess.com", variable=self.website, value="chesscom",
            command=self.on_website_change
        )
        self.chesscom_radio_button.pack(anchor=tk.NW)
        self.lichess_radio_button = tk.Radiobutton(
            left_frame, text="Lichess.org", variable=self.website, value="lichess",
            command=self.on_website_change
        )
        self.lichess_radio_button.pack(anchor=tk.NW)

        # Tournament mode checkbox (only visible for Lichess)
        self.tournament_mode_frame = tk.Frame(left_frame)
        self.enable_tournament_mode = tk.BooleanVar(value=False)
        self.tournament_mode_checkbox = tk.Checkbutton(
            self.tournament_mode_frame, 
            text="Tournament Mode", 
            variable=self.enable_tournament_mode,
            command=self.on_tournament_mode_change
        )
        self.tournament_mode_checkbox.pack(anchor=tk.NW)
        self.tournament_mode_frame.pack_forget()  # Initially hidden

        # Open Browser button
        self.opening_browser = False
        self.opened_browser = False
        self.open_browser_button = tk.Button(
            left_frame, text="Open Browser", command=self.on_open_browser_button_listener
        )
        self.open_browser_button.pack(anchor=tk.NW)

        # Start button
        self.running = False
        self.start_button = tk.Button(
            left_frame, text="Start", command=self.on_start_button_listener
        )
        self.start_button["state"] = "disabled"
        self.start_button.pack(anchor=tk.NW, pady=5)

        # Manual mode checkbox
        self.enable_manual_mode = tk.BooleanVar(value=False)
        self.manual_mode_checkbox = tk.Checkbutton(
            left_frame,
            text="Manual Mode",
            variable=self.enable_manual_mode,
            command=self.on_manual_mode_checkbox_listener,
        )
        self.manual_mode_checkbox.pack(anchor=tk.NW)

        # Manual mode instructions
        self.manual_mode_frame = tk.Frame(left_frame)
        self.manual_mode_label = tk.Label(
            self.manual_mode_frame, text="\u2022 Press 3 to make a move"
        )
        self.manual_mode_label.pack(anchor=tk.NW)

        # Mouseless mode checkbox
        self.enable_mouseless_mode = tk.BooleanVar(value=False)
        self.mouseless_mode_checkbox = tk.Checkbutton(
            left_frame, text="Mouseless Mode", variable=self.enable_mouseless_mode,
            command=self.on_mouseless_mode_change
        )
        self.mouseless_mode_checkbox.pack(anchor=tk.NW)

        # Human Mode checkbox
        self.enable_human_mode = tk.BooleanVar(value=False)
        self.human_mode_checkbox = tk.Checkbutton(
            left_frame, text="Human Mode", variable=self.enable_human_mode
        )
        self.human_mode_checkbox.pack(anchor=tk.NW)

        # Only PreMoves Mode checkbox
        self.enable_premoves_mode = tk.BooleanVar(value=False)
        self.premoves_mode_checkbox = tk.Checkbutton(
            left_frame, text="Only PreMoves Mode", variable=self.enable_premoves_mode,
            command=self.on_premoves_mode_change
        )
        self.premoves_mode_checkbox.pack(anchor=tk.NW)

        # Non-stop puzzles checkbox
        self.enable_non_stop_puzzles = tk.IntVar(value=0)
        self.non_stop_puzzles_check_button = tk.Checkbutton(
            left_frame, text="Non-stop puzzles", variable=self.enable_non_stop_puzzles
        )
        self.non_stop_puzzles_check_button.pack(anchor=tk.NW)

        # Bongcloud checkbox
        self.enable_bongcloud = tk.IntVar()
        self.bongcloud_check_button = tk.Checkbutton(
            left_frame, text="Bongcloud", variable=self.enable_bongcloud
        )
        self.bongcloud_check_button.pack(anchor=tk.NW)

        # Separator for Stockfish parameters
        separator_frame = tk.Frame(left_frame)
        separator = ttk.Separator(separator_frame, orient="horizontal")
        separator.grid(row=0, column=0, sticky="ew")
        label = tk.Label(separator_frame, text="Stockfish parameters")
        label.grid(row=0, column=0, padx=40)
        separator_frame.pack(anchor=tk.NW, pady=10, expand=True, fill=tk.X)

        # Slow Mover entry field
        slow_mover_frame = tk.Frame(left_frame)
        self.slow_mover_label = tk.Label(slow_mover_frame, text="Slow Mover")
        self.slow_mover_label.pack(side=tk.LEFT)
        self.slow_mover = tk.IntVar(value=100)
        self.slow_mover_entry = tk.Entry(
            slow_mover_frame, textvariable=self.slow_mover, justify="center", width=8
        )
        self.slow_mover_entry.pack()
        slow_mover_frame.pack(anchor=tk.NW)

        # Skill Level scale
        skill_level_frame = tk.Frame(left_frame)
        tk.Label(skill_level_frame, text="Skill Level").pack(side=tk.LEFT, pady=(19, 0))
        self.skill_level = tk.IntVar(value=20)
        self.skill_level_scale = tk.Scale(
            skill_level_frame, from_=0, to=20, orient=tk.HORIZONTAL, variable=self.skill_level
        )
        self.skill_level_scale.pack()
        skill_level_frame.pack(anchor=tk.NW)

        # Stockfish Depth scale
        stockfish_depth_frame = tk.Frame(left_frame)
        tk.Label(stockfish_depth_frame, text="Depth").pack(side=tk.LEFT, pady=19)
        self.stockfish_depth = tk.IntVar(value=15)
        self.stockfish_depth_scale = tk.Scale(
            stockfish_depth_frame, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.stockfish_depth
        )
        self.stockfish_depth_scale.pack()
        stockfish_depth_frame.pack(anchor=tk.NW)

        # Memory entry field
        memory_frame = tk.Frame(left_frame)
        tk.Label(memory_frame, text="Memory").pack(side=tk.LEFT)
        self.memory = tk.IntVar(value=512)
        self.memory_entry = tk.Entry(
            memory_frame, textvariable=self.memory, justify="center", width=9
        )
        self.memory_entry.pack(side=tk.LEFT)
        tk.Label(memory_frame, text="MB").pack()
        memory_frame.pack(anchor=tk.NW, pady=(0, 15))

        # CPU Threads entry field
        cpu_threads_frame = tk.Frame(left_frame)
        tk.Label(cpu_threads_frame, text="CPU Threads").pack(side=tk.LEFT)
        self.cpu_threads = tk.IntVar(value=1)
        self.cpu_threads_entry = tk.Entry(
            cpu_threads_frame, textvariable=self.cpu_threads, justify="center", width=7
        )
        self.cpu_threads_entry.pack()
        cpu_threads_frame.pack(anchor=tk.NW)

        # Separator for Miscellaneous options
        separator_frame = tk.Frame(left_frame)
        separator = ttk.Separator(separator_frame, orient="horizontal")
        separator.grid(row=0, column=0, sticky="ew")
        label = tk.Label(separator_frame, text="Misc")
        label.grid(row=0, column=0, padx=82)
        separator_frame.pack(anchor=tk.NW, pady=10, expand=True, fill=tk.X)

        # Topmost window checkbox
        self.enable_topmost = tk.IntVar(value=1)
        self.topmost_check_button = tk.Checkbutton(
            left_frame,
            text="Window stays on top",
            variable=self.enable_topmost,
            onvalue=1,
            offvalue=0,
            command=self.on_topmost_check_button_listener,
        )
        self.topmost_check_button.pack(anchor=tk.NW)

        # Select Stockfish button
        self.stockfish_path = ""
        self.select_stockfish_button = tk.Button(
            left_frame, text="Select Stockfish", command=self.on_select_stockfish_button_listener
        )
        self.select_stockfish_button.pack(anchor=tk.NW)

        # Stockfish path display
        self.stockfish_path_text = tk.Label(left_frame, text="", wraplength=180)
        self.stockfish_path_text.pack(anchor=tk.NW)

        left_frame.grid(row=0, column=0, padx=5, sticky=tk.NW)

        # Right frame for moves Treeview
        right_frame = tk.Frame(master)
        treeview_frame = tk.Frame(right_frame)
        self.tree = ttk.Treeview(
            treeview_frame, column=("#", "White", "Black"),
            show="headings", height=23, selectmode="browse"
        )
        self.tree.pack(anchor=tk.NW, side=tk.LEFT)
        self.vsb = ttk.Scrollbar(treeview_frame, orient="vertical", command=self.tree.yview)
        self.vsb.pack(fill=tk.Y, expand=True)
        self.tree.configure(yscrollcommand=self.vsb.set)
        self.tree.column("# 1", anchor=tk.CENTER, width=35)
        self.tree.heading("# 1", text="#")
        self.tree.column("# 2", anchor=tk.CENTER, width=60)
        self.tree.heading("# 2", text="White")
        self.tree.column("# 3", anchor=tk.CENTER, width=60)
        self.tree.heading("# 3", text="Black")
        treeview_frame.pack(anchor=tk.NW)
        self.export_pgn_button = tk.Button(
            right_frame, text="Export PGN", command=self.on_export_pgn_button_listener
        )
        self.export_pgn_button.pack(anchor=tk.NW, fill=tk.X)
        right_frame.grid(row=0, column=1, sticky=tk.NW)

        # Start background threads
        threading.Thread(target=self.process_checker_thread).start()
        threading.Thread(target=self.browser_checker_thread).start()
        threading.Thread(target=self.process_communicator_thread).start()
        threading.Thread(target=self.keypress_listener_thread).start()

    def on_website_change(self):
        # Show or hide tournament mode checkbox based on website selection
        if self.website.get() == "lichess":
            self.tournament_mode_frame.pack(after=self.lichess_radio_button)
        else:
            self.tournament_mode_frame.pack_forget()
            self.enable_tournament_mode.set(False)
            self.is_tournament_mode = False

    def on_tournament_mode_change(self):
        self.is_tournament_mode = self.enable_tournament_mode.get()

    def on_mouseless_mode_change(self):
        # Disable premoves mode if mouseless mode is enabled
        if self.enable_mouseless_mode.get() and self.enable_premoves_mode.get():
            messagebox.showinfo("Mode Conflict", "Mouseless Mode and PreMoves Mode cannot be used together. PreMoves Mode has been disabled.")
            self.enable_premoves_mode.set(False)

    def on_premoves_mode_change(self):
        # Disable mouseless mode if premoves mode is enabled
        if self.enable_premoves_mode.get() and self.enable_mouseless_mode.get():
            messagebox.showinfo("Mode Conflict", "PreMoves Mode and Mouseless Mode cannot be used together. Mouseless Mode has been disabled.")
            self.enable_mouseless_mode.set(False)

    def on_close_listener(self):
        self.exit = True
        self.master.destroy()

    def process_checker_thread(self):
        # Don't monitor or restart the process in tournament mode
        while not self.exit:
            if not self.is_tournament_mode:
                if self.running and self.stockfish_bot_process is not None and not self.stockfish_bot_process.is_alive():
                    self.on_stop_button_listener()
                    if self.restart_after_stopping:
                        self.restart_after_stopping = False
                        self.on_start_button_listener()
            time.sleep(0.05)

    def browser_checker_thread(self):
        while not self.exit:
            try:
                if (self.opened_browser and self.chrome is not None and
                    "target window already closed" in self.chrome.get_log("driver")[-1]["message"]):
                    self.opened_browser = False
                    self.open_browser_button["text"] = "Open Browser"
                    self.open_browser_button["state"] = "normal"
                    self.open_browser_button.update()
                    self.on_stop_button_listener()
                    self.chrome = None
            except IndexError:
                pass
            time.sleep(0.1)

    def process_communicator_thread(self):
        while not self.exit:
            try:
                if self.stockfish_bot_pipe is not None and self.stockfish_bot_pipe.poll():
                    data = self.stockfish_bot_pipe.recv()
                    
                    # For tournament mode, we always want to process these messages
                    if data.startswith("START"):
                        self.clear_tree()
                        self.match_moves = []
                        self.game_over_shown = False
                        self.status_text["text"] = "Running"
                        self.status_text["fg"] = "green"
                        self.status_text.update()
                        self.start_button["text"] = "Stop"
                        self.start_button["state"] = "normal"
                        self.start_button["command"] = self.on_stop_button_listener
                        self.start_button.update()
                    elif data.startswith("S_MOVE"):
                        move = data[6:]
                        self.match_moves.append(move)
                        self.insert_move(move)
                        self.tree.yview_moveto(1)
                    elif data.startswith("M_MOVE"):
                        moves = data[6:].split(",")
                        self.match_moves += moves
                        self.set_moves(moves)
                        self.tree.yview_moveto(1)
                    # Only process error and restart messages if NOT in tournament mode
                    elif not self.is_tournament_mode:
                        if data.startswith("RESTART"):
                            self.restart_after_stopping = True
                            self.stockfish_bot_pipe.send("DELETE")
                        elif data.startswith("ERR_"):
                            if data.startswith("ERR_EXE"):
                                messagebox.showerror("Error", "Stockfish path provided is not valid!")
                            elif data.startswith("ERR_PERM"):
                                messagebox.showerror("Error", "Stockfish path provided is not executable!")
                            elif data.startswith("ERR_BOARD"):
                                messagebox.showerror("Error", "Cant find board!")
                            elif data.startswith("ERR_COLOR"):
                                messagebox.showerror("Error", "Cant find player color!")
                            elif data.startswith("ERR_MOVES"):
                                messagebox.showerror("Error", "Cant find moves list!")
                            elif data.startswith("ERR_GAMEOVER"):
                                if not self.game_over_shown:
                                    messagebox.showerror("Error", "Game has already finished!")
                                    self.game_over_shown = True
                                self.on_stop_button_listener()
            except (BrokenPipeError, OSError):
                self.stockfish_bot_pipe = None
            time.sleep(0.1)

    def keypress_listener_thread(self):
        while not self.exit:
            time.sleep(0.1)
            if not self.opened_browser:
                continue
            if keyboard.is_pressed("1"):
                self.on_start_button_listener()
            elif keyboard.is_pressed("2"):
                self.on_stop_button_listener()
            elif keyboard.is_pressed("3") and self.enable_manual_mode.get() and self.running:
                # Send manual move command to the bot
                if self.stockfish_bot_pipe is not None:
                    self.stockfish_bot_pipe.send("MANUAL")

    def on_open_browser_button_listener(self):
        self.opening_browser = True
        self.open_browser_button["text"] = "Opening Browser..."
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        try:
            driver_path = chromedriver_autoinstaller.install()
            service = Service(driver_path)
        except Exception:
            try:
                service = Service(ChromeDriverManager().install())
            except Exception:
                self.opening_browser = False
                self.open_browser_button["text"] = "Open Browser"
                self.open_browser_button["state"] = "normal"
                self.open_browser_button.update()
                messagebox.showerror(
                    "Error",
                    "Chrome could not be found or the driver failed to install."
                )
                return
        try:
            self.chrome = webdriver.Chrome(service=service, options=options)
        except WebDriverException:
            self.opening_browser = False
            self.open_browser_button["text"] = "Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            messagebox.showerror(
                "Error",
                "Failed to launch Chrome. Make sure Chrome is installed."
            )
            return
        if self.website.get() == "chesscom":
            self.chrome.get("https://www.chess.com")
        else:
            self.chrome.get("https://www.lichess.org")
        self.chrome_url = self.chrome.service.service_url
        self.chrome_session_id = self.chrome.session_id
        self.opening_browser = False
        self.opened_browser = True
        self.open_browser_button["text"] = "Browser is open"
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()
        self.start_button["state"] = "normal"
        self.start_button.update()

    def on_start_button_listener(self):
        slow_mover = self.slow_mover.get()
        if slow_mover < 10 or slow_mover > 1000:
            messagebox.showerror("Error", "Slow Mover must be between 10 and 1000")
            return
        if self.stockfish_path == "":
            messagebox.showerror("Error", "Stockfish path is empty")
            return
        if self.enable_mouseless_mode.get() and self.website.get() == "chesscom":
            messagebox.showerror("Error", "Mouseless mode is only supported on lichess.org")
            return
        if self.enable_premoves_mode.get() and self.enable_mouseless_mode.get():
            messagebox.showerror("Error", "PreMoves Mode and Mouseless Mode cannot be used together")
            return
            
        # Set tournament mode flag based on current state
        self.is_tournament_mode = self.website.get() == "lichess" and self.enable_tournament_mode.get()
            
        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn
        st_ov_queue = multiprocess.Queue()
        
        # Pass tournament mode flag to StockfishBot
        self.stockfish_bot_process = StockfishBot(
            self.chrome_url,
            self.chrome_session_id,
            self.website.get(),
            child_conn,
            st_ov_queue,
            self.stockfish_path,
            self.enable_manual_mode.get(),
            self.enable_mouseless_mode.get(),
            self.enable_human_mode.get(),
            self.enable_non_stop_puzzles.get(),
            self.enable_bongcloud.get(),
            self.slow_mover.get(),
            self.skill_level.get(),
            self.stockfish_depth.get(),
            self.memory.get(),
            self.cpu_threads.get(),
            tournament_mode=self.is_tournament_mode,
            premoves_mode=self.enable_premoves_mode.get()  # Add PreMoves mode parameter
        )
        self.stockfish_bot_process.start()
        self.overlay_screen_process = multiprocess.Process(
            target=run, args=(st_ov_queue,)
        )
        self.overlay_screen_process.start()
        self.running = True
        self.start_button["text"] = "Starting..."
        self.start_button["state"] = "disabled"
        self.start_button.update()

    def on_stop_button_listener(self):
        if self.stockfish_bot_process is not None:
            self.stockfish_bot_process.kill()
            self.stockfish_bot_process = None
        if self.stockfish_bot_pipe is not None:
            self.stockfish_bot_pipe.close()
            self.stockfish_bot_pipe = None
        if self.overlay_screen_process is not None:
            self.overlay_screen_process.kill()
            self.overlay_screen_process = None
        if self.overlay_screen_pipe is not None:
            self.overlay_screen_pipe.close()
            self.overlay_screen_pipe = None
        self.running = False
        self.status_text["text"] = "Inactive"
        self.status_text["fg"] = "red"
        self.status_text.update()
        self.start_button["text"] = "Start"
        self.start_button["state"] = "normal"
        self.start_button["command"] = self.on_start_button_listener
        self.start_button.update()

    def on_topmost_check_button_listener(self):
        if self.enable_topmost.get() == 1:
            self.master.attributes("-topmost", True)
        else:
            self.master.attributes("-topmost", False)

    def on_export_pgn_button_listener(self):
        f = filedialog.asksaveasfile(
            initialfile="match.pgn",
            defaultextension=".pgn",
            filetypes=[("Portable Game Notation", "*.pgn"), ("All Files", "*.*")]
        )
        if f is None:
            return
        data = ""
        for i in range(len(self.match_moves) // 2 + 1):
            if len(self.match_moves) % 2 == 0 and i == len(self.match_moves) // 2:
                continue
            data += str(i + 1) + ". "
            data += self.match_moves[i * 2] + " "
            if (i * 2) + 1 < len(self.match_moves):
                data += self.match_moves[i * 2 + 1] + " "
        f.write(data)
        f.close()

    def on_select_stockfish_button_listener(self):
        f = filedialog.askopenfilename()
        if f is None or f == "":
            return
        self.stockfish_path = f
        self.stockfish_path_text["text"] = self.stockfish_path
        self.stockfish_path_text.update()

    def on_manual_mode_checkbox_listener(self):
        if self.enable_manual_mode.get() == 1:
            self.manual_mode_frame.pack(after=self.manual_mode_checkbox)
            self.manual_mode_frame.update()
        else:
            self.manual_mode_frame.pack_forget()
            self.manual_mode_checkbox.update()

    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.update()

    def insert_move(self, move):
        cells_num = sum([len(self.tree.item(i)["values"]) - 1 for i in self.tree.get_children()])
        if (cells_num % 2) == 0:
            rows_num = len(self.tree.get_children())
            self.tree.insert("", "end", text="1", values=(rows_num + 1, move))
        else:
            self.tree.set(self.tree.get_children()[-1], column=2, value=move)
        self.tree.update()

    def set_moves(self, moves):
        self.clear_tree()
        pairs = list(zip(*[iter(moves)] * 2))
        for i, pair in enumerate(pairs):
            self.tree.insert("", "end", text="1", values=(str(i + 1), pair[0], pair[1]))
        if len(moves) % 2 == 1:
            self.tree.insert("", "end", text="1", values=(len(pairs) + 1, moves[-1]))
        self.tree.update()

if __name__ == "__main__":
    window = tk.Tk()
    my_gui = GUI(window)
    window.mainloop()
